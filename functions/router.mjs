// Application routes: register / login / logout / me / sync / shared class board.
// Identity always comes from this app's own session validation (DB session digest);
// never ctx.user, platform identity, Host header, or a browser-supplied owner id.
import { AppError, applicationPath, errorJson, json, readJson, requireTrustedOrigin, rows } from './http.mjs';
import { canonicalUsername, validateAvatar, validateCounter, validateDisplayName, validateGrade, validatePassword } from './validate.mjs';
import { hashPassword, verifyPassword, verifyPasswordAgainstDummy } from './passwords.mjs';
import { SESSION_TTL_MS, clearSessionCookie, createSession, revokeSession, sessionCookie, validateSession } from './sessions.mjs';
import { consume } from './limiter.mjs';

const SESSION_TTL_SECONDS = Math.floor(SESSION_TTL_MS / 1000);
const encoder = new TextEncoder();
const BOARD_LIMIT = 500;

const USER_COLS = 'id,username,display_name,grade,avatar,solved,total_pets,best_combo';
const BOARD_COLS = 'id,display_name,grade,avatar,solved,total_pets,best_combo';

class SessionRequired extends Error {
  constructor(state) {
    super('login_required');
    this.state = state;
  }
}

const retryAfter = (result) => ({ 'retry-after': String(Math.max(1, Math.ceil(result.retryAfterMs / 1000))) });

function unauthorized(state) {
  return state === 'invalid'
    ? errorJson('login_required', 401, { 'set-cookie': clearSessionCookie() })
    : errorJson('login_required', 401);
}

async function requireSession(db, request) {
  const result = await validateSession(db, request);
  if (result.state !== 'valid') throw new SessionRequired(result.state);
  return result.session;
}

async function loadUser(db, userId) {
  const found = rows(await db.from('users').select(USER_COLS).eq('id', userId).limit(1));
  if (found.length !== 1 || typeof found[0]?.username !== 'string') throw new SessionRequired('invalid');
  return found[0];
}

const publicUser = (r) => ({
  id: r.id, username: r.username, name: r.display_name, grade: r.grade, avatar: r.avatar,
  solved: r.solved, totalPets: r.total_pets, bestCombo: r.best_combo,
});
const boardScore = (solved, totalPets) => solved * 10 + Math.floor(totalPets / 100);
const boardEntry = (r) => ({
  id: r.id, name: r.display_name, grade: r.grade, avatar: r.avatar,
  solved: r.solved, totalPets: r.total_pets, bestCombo: r.best_combo,
  score: boardScore(r.solved, r.total_pets),
});

function boundedPassword(raw) {
  if (typeof raw !== 'string' || raw.length === 0 || encoder.encode(raw).length > 256) {
    throw new AppError('invalid_input', 400);
  }
  return raw;
}

async function register(db, request) {
  const body = await readJson(request);
  const username = canonicalUsername(body?.username);
  const password = validatePassword(body?.password);
  const displayName = validateDisplayName(body?.displayName);
  const grade = validateGrade(body?.grade);
  const avatar = validateAvatar(body?.avatar);
  const limit = await consume(db, 'register', username);
  if (!limit.allowed) return errorJson('rate_limited', 429, retryAfter(limit));

  const existing = rows(await db.from('users').select('id').eq('username', username).limit(1));
  if (existing.length > 0) return errorJson('username_taken', 409);

  const derived = await hashPassword(password);
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  const created = rows(await db.from('users').insertIfAbsent({
    id, username,
    password_salt: derived.salt, password_hash: derived.hash, password_iterations: derived.iterations,
    created_at: now, updated_at: now,
    display_name: displayName, grade, avatar,
    solved: 0, total_pets: 0, best_combo: 0,
  }, { onConflict: 'username' }).select(USER_COLS));

  if (created.length !== 1) {
    const winner = rows(await db.from('users').select('id').eq('username', username).limit(1));
    if (winner.length === 1) return errorJson('username_taken', 409);
    return errorJson('registration_unconfirmed', 503);
  }

  const { token } = await createSession(db, id);
  return json({ user: publicUser(created[0]) }, 201, { 'set-cookie': sessionCookie(token, SESSION_TTL_SECONDS) });
}

async function login(db, request) {
  const body = await readJson(request);
  const username = canonicalUsername(body?.username);
  const limit = await consume(db, 'login', username);
  if (!limit.allowed) return errorJson('rate_limited', 429, retryAfter(limit));

  const password = boundedPassword(body?.password);
  const found = rows(await db.from('users')
    .select('id,username,password_salt,password_hash,password_iterations').eq('username', username).limit(1));

  if (found.length !== 1) {
    await verifyPasswordAgainstDummy(password);
    return errorJson('invalid_credentials', 401);
  }

  const user = found[0];
  const ok = await verifyPassword(password, {
    salt: user.password_salt, hash: user.password_hash, iterations: user.password_iterations,
  });
  if (!ok) return errorJson('invalid_credentials', 401);

  const { token } = await createSession(db, user.id);
  const full = await loadUser(db, user.id);
  return json({ user: publicUser(full) }, 200, { 'set-cookie': sessionCookie(token, SESSION_TTL_SECONDS) });
}

async function logout(db, request) {
  const result = await validateSession(db, request);
  if (result.state === 'valid' && result.session) {
    try {
      await revokeSession(db, result.session.digest);
    } catch {
      return errorJson('logout_unconfirmed', 503);
    }
  }
  return json({ ok: true }, 200, { 'set-cookie': clearSessionCookie() });
}

// Owner-scoped progress push. Scores are monotonic (max) so a stale device never regresses
// progress; grade follows the same one-way ladder as the client (no downgrade / no mix after commit).
async function sync(db, request) {
  const session = await requireSession(db, request);
  const body = await readJson(request);
  const solved = validateCounter(body?.solved);
  const totalPets = validateCounter(body?.totalPets);
  const bestCombo = validateCounter(body?.bestCombo);
  const cur = await loadUser(db, session.userId);

  const grade = body?.grade === undefined ? cur.grade : validateGrade(body.grade);
  const committed = cur.grade >= 1 && cur.grade <= 11;
  const nextGrade = (committed && (grade === 0 || grade < cur.grade)) ? cur.grade : grade;
  const displayName = body?.displayName === undefined ? cur.display_name : validateDisplayName(body.displayName);
  const avatar = body?.avatar === undefined ? cur.avatar : validateAvatar(body.avatar);

  const updated = rows(await db.from('users').update({
    display_name: displayName,
    grade: nextGrade,
    avatar,
    solved: Math.max(cur.solved, solved),
    total_pets: Math.max(cur.total_pets, totalPets),
    best_combo: Math.max(cur.best_combo, bestCombo),
    updated_at: new Date().toISOString(),
  }).eq('id', session.userId).select(USER_COLS));

  if (updated.length !== 1) return errorJson('sync_unconfirmed', 503);
  return json({ user: publicUser(updated[0]) });
}

// Shared class board: anonymous read of public display fields only (no usernames, no secrets).
async function board(db) {
  const list = rows(await db.from('users').select(BOARD_COLS).limit(BOARD_LIMIT));
  const players = list.map(boardEntry).sort((a, b) =>
    b.score - a.score || b.solved - a.solved || b.totalPets - a.totalPets || a.name.localeCompare(b.name, 'ru'));
  return json({ players });
}

async function route(db, request, origin) {
  requireTrustedOrigin(request, origin);
  const path = applicationPath(request);

  if (path === '/api/health' && request.method === 'GET') return json({ ok: true });
  if (path === '/api/register' && request.method === 'POST') return register(db, request);
  if (path === '/api/login' && request.method === 'POST') return login(db, request);
  if (path === '/api/logout' && request.method === 'POST') return logout(db, request);
  if (path === '/api/board' && request.method === 'GET') return board(db);

  if (path === '/api/me' && request.method === 'GET') {
    const session = await requireSession(db, request);
    return json({ user: publicUser(await loadUser(db, session.userId)) });
  }

  if (path === '/api/sync' && request.method === 'POST') return sync(db, request);

  if (['/api/me', '/api/sync', '/api/logout', '/api/register', '/api/login', '/api/board', '/api/health'].includes(path)) {
    throw new AppError('method_not_allowed', 405);
  }
  throw new AppError('not_found', 404);
}

// Dependency injection is for local tests only; ctx supplies the request, never platform identity.
export function createApplication({ db, origin }) {
  return async function handle(ctx) {
    try {
      return await route(db, ctx.request, typeof origin === 'function' ? origin() : origin);
    } catch (error) {
      if (error instanceof SessionRequired) return unauthorized(error.state);
      if (error instanceof AppError) return errorJson(error.code, error.status);
      return errorJson('service_unavailable', 503);
    }
  };
}