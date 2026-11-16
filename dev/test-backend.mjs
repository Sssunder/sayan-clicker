// Local exercise of the real application routes with a credential-free fake DB.
// Run: node --test dev/test-backend.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { createApplication } from '../functions/router.mjs';
import { createFakeDb } from './fake-db.mjs';

const ORIGIN = 'https://sayan.example';
const CAT = '\u{1F431}';

function makeDb() { return createFakeDb(); }
function app(db) { return createApplication({ db, origin: ORIGIN }); }
function req(method, path, { body, origin = ORIGIN, cookie } = {}) {
  const headers = { origin };
  if (body !== undefined) headers['content-type'] = 'application/json';
  if (cookie) headers.cookie = cookie;
  return new Request(ORIGIN + '/functions/v1/app' + path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
}
async function call(handle, method, path, opts) {
  const res = await handle({ request: req(method, path, opts) });
  let data = null;
  try { data = await res.json(); } catch {}
  return { status: res.status, data, cookie: res.headers.get('set-cookie') };
}
const sessionCookie = (setCookie) => (setCookie || '').split(';')[0];
const reg = (over = {}) => ({ username: 'alice', password: 'secret123', displayName: 'Алиса', grade: 3, avatar: CAT, ...over });

test('health is anonymous', async () => {
  const r = await call(app(makeDb()), 'GET', '/api/health');
  assert.equal(r.status, 200); assert.equal(r.data.ok, true);
});

test('register creates profile + session, rejects dup/bad input', async () => {
  const db = makeDb(); const h = app(db);
  const ok = await call(h, 'POST', '/api/register', { body: reg() });
  assert.equal(ok.status, 201);
  assert.equal(ok.data.user.name, 'Алиса');
  assert.equal(ok.data.user.grade, 3);
  assert.ok(ok.cookie.includes('__Host-app_auth.session='));
  assert.equal((await call(h, 'POST', '/api/register', { body: reg() })).status, 409);
  assert.equal((await call(h, 'POST', '/api/register', { body: reg({ username: 'bob', displayName: '  ' }) })).status, 400);
  assert.equal((await call(h, 'POST', '/api/register', { body: reg({ username: 'bob', password: '123' }) })).status, 400);
  assert.equal((await call(h, 'POST', '/api/register', { body: reg({ username: 'bob', avatar: 'x' }) })).status, 400);
  assert.equal((await call(h, 'POST', '/api/register', { body: reg({ username: 'bob', grade: 12 }) })).status, 400);
  // no plaintext password stored
  const stored = db.dump('users')[0];
  assert.notEqual(stored.password_hash, 'secret123');
  assert.ok(!('password' in stored));
});

test('login verifies password, me requires session', async () => {
  const db = makeDb(); const h = app(db);
  const ok = await call(h, 'POST', '/api/register', { body: reg() });
  const cookie = sessionCookie(ok.cookie);
  assert.equal((await call(h, 'POST', '/api/login', { body: { username: 'alice', password: 'wrong123' } })).status, 401);
  const li = await call(h, 'POST', '/api/login', { body: { username: 'alice', password: 'secret123' } });
  assert.equal(li.status, 200); assert.equal(li.data.user.name, 'Алиса');
  const me = await call(h, 'GET', '/api/me', { cookie });
  assert.equal(me.status, 200); assert.equal(me.data.user.username, 'alice');
  assert.equal((await call(h, 'GET', '/api/me')).status, 401);
});

test('sync is owner-scoped, monotonic, grade one-way', async () => {
  const db = makeDb(); const h = app(db);
  const a = await call(h, 'POST', '/api/register', { body: reg() });
  const ac = sessionCookie(a.cookie);
  const b = await call(h, 'POST', '/api/register', { body: reg({ username: 'bob', displayName: 'Боб', grade: 5 }) });
  const bc = sessionCookie(b.cookie);

  const s1 = await call(h, 'POST', '/api/sync', { cookie: ac, body: { solved: 5, totalPets: 500, bestCombo: 7, grade: 3, displayName: 'Алиса', avatar: CAT } });
  assert.equal(s1.status, 200);
  assert.equal(s1.data.user.solved, 5); assert.equal(s1.data.user.totalPets, 500);

  // stale lower values must not regress
  const s2 = await call(h, 'POST', '/api/sync', { cookie: ac, body: { solved: 2, totalPets: 100, bestCombo: 1 } });
  assert.equal(s2.data.user.solved, 5); assert.equal(s2.data.user.totalPets, 500); assert.equal(s2.data.user.bestCombo, 7);

  // grade ladder: committed 3 cannot drop to 1 or mix; can climb to 5
  assert.equal((await call(h, 'POST', '/api/sync', { cookie: ac, body: { solved: 5, totalPets: 500, bestCombo: 7, grade: 1 } })).data.user.grade, 3);
  assert.equal((await call(h, 'POST', '/api/sync', { cookie: ac, body: { solved: 5, totalPets: 500, bestCombo: 7, grade: 0 } })).data.user.grade, 3);
  assert.equal((await call(h, 'POST', '/api/sync', { cookie: ac, body: { solved: 5, totalPets: 500, bestCombo: 7, grade: 5 } })).data.user.grade, 5);

  // bob syncing cannot touch alice; body id/owner ignored
  const bs = await call(h, 'POST', '/api/sync', { cookie: bc, body: { id: a.data.user.id, solved: 99, totalPets: 99999, bestCombo: 99 } });
  assert.equal(bs.data.user.username, 'bob'); assert.equal(bs.data.user.solved, 99);
  const aliceNow = await call(h, 'GET', '/api/me', { cookie: ac });
  assert.equal(aliceNow.data.user.solved, 5);

  // sync without session rejected
  assert.equal((await call(h, 'POST', '/api/sync', { body: { solved: 1, totalPets: 1, bestCombo: 1 } })).status, 401);
});

test('board is anonymous, public fields only, sorted by score', async () => {
  const db = makeDb(); const h = app(db);
  const a = await call(h, 'POST', '/api/register', { body: reg() });
  await call(h, 'POST', '/api/sync', { cookie: sessionCookie(a.cookie), body: { solved: 5, totalPets: 500, bestCombo: 7 } });
  const b = await call(h, 'POST', '/api/register', { body: reg({ username: 'bob', displayName: 'Боб', grade: 3 }) });
  await call(h, 'POST', '/api/sync', { cookie: sessionCookie(b.cookie), body: { solved: 1, totalPets: 0, bestCombo: 1 } });

  const board = await call(h, 'GET', '/api/board'); // no cookie
  assert.equal(board.status, 200);
  const names = board.data.players.map((p) => p.name);
  assert.deepEqual(names, ['Алиса', 'Боб']); // 55 vs 10
  assert.equal(board.data.players[0].score, 55);
  for (const p of board.data.players) {
    assert.ok(!('username' in p)); assert.ok(!('password_hash' in p)); assert.ok(!('password_salt' in p));
  }
});

test('logout revokes session', async () => {
  const db = makeDb(); const h = app(db);
  const a = await call(h, 'POST', '/api/register', { body: reg() });
  const cookie = sessionCookie(a.cookie);
  assert.equal((await call(h, 'POST', '/api/logout', { cookie })).status, 200);
  assert.equal((await call(h, 'GET', '/api/me', { cookie })).status, 401);
});

test('register rate limit kicks in', async () => {
  const db = makeDb(); const h = app(db);
  for (let i = 0; i < 5; i++) await call(h, 'POST', '/api/register', { body: reg({ username: 'limituser' }) });
  const sixth = await call(h, 'POST', '/api/register', { body: reg({ username: 'limituser' }) });
  assert.equal(sixth.status, 429);
});

test('origin, method and path guards', async () => {
  const db = makeDb(); const h = app(db);
  assert.equal((await call(h, 'POST', '/api/register', { body: reg(), origin: 'https://evil.example' })).status, 403);
  assert.equal((await call(h, 'POST', '/api/board')).status, 405);
  assert.equal((await call(h, 'GET', '/api/nope')).status, 404);
});