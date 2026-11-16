// Sayan Clicker — Supabase Edge Function «sayan».
// Routes: GET /health, POST /register, POST /login, POST /logout,
//         GET /me, POST /sync, GET /board.
// Auth: app-owned username+PBKDF2 sessions (no Supabase Auth email dependency).
// Deploy: supabase functions deploy sayan --no-verify-jwt

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ── Config ─────────────────────────────────────────────────────────────────
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const APP_ORIGINS = (Deno.env.get("APP_ORIGINS") || "https://sssunder.github.io").split(",").map(s => s.trim());

// ── DB client ──────────────────────────────────────────────────────────────
function db() {
  return createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
    auth: { persistSession: false },
  });
}

// ── CORS + response helpers ────────────────────────────────────────────────
function corsHeaders(origin: string | null): Record<string, string> {
  const allowed = origin && APP_ORIGINS.includes(origin) ? origin : APP_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept",
    "Vary": "Origin",
  };
}
function json(body: unknown, status = 200, headers: Record<string, string> = {}, origin: string | null = null) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin), ...headers },
  });
}
function err(code: string, status: number, extra: Record<string, string> = {}, origin: string | null = null) {
  return json({ error: code }, status, extra, origin);
}

// ── Session cookie ─────────────────────────────────────────────────────────
const SESSION_COOKIE = "sayan_session";
const SESSION_TTL_S = 12 * 60 * 60; // 12 h
const TOKEN_RE = /^[A-Za-z0-9_-]{43}$/;

function setCookie(token: string) {
  return `${SESSION_COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=None; Max-Age=${SESSION_TTL_S}`;
}
function clearCookie() {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=None; Max-Age=0`;
}
function tokenFromRequest(req: Request): string | null {
  const hdr = req.headers.get("cookie") ?? "";
  for (const part of hdr.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name.trim() === SESSION_COOKIE) {
      const val = rest.join("=").trim();
      if (TOKEN_RE.test(val)) return val;
    }
  }
  return null;
}

// ── Crypto helpers ─────────────────────────────────────────────────────────
const enc = new TextEncoder();
async function sha256hex(s: string) {
  const buf = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}
function newToken() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function toB64(bytes: Uint8Array) {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}
function fromB64(s: string) {
  const bin = atob(s);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}
async function hashPwd(password: string) {
  const salt = new Uint8Array(16);
  crypto.getRandomValues(salt);
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations: 600000, hash: "SHA-256" }, key, 256);
  return { salt: toB64(salt), hash: toB64(new Uint8Array(bits)), iters: 600000 };
}
function timingSafe(a: string, b: string) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
async function verifyPwd(password: string, record: { salt: string; hash: string; iters: number }) {
  const salt = fromB64(record.salt);
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations: record.iters, hash: "SHA-256" }, key, 256);
  return timingSafe(toB64(new Uint8Array(bits)), record.hash);
}
// Constant-time dummy for unknown usernames
const DUMMY_SALT = new Uint8Array(16);
async function dummyVerify(password: string) {
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  await crypto.subtle.deriveBits({ name: "PBKDF2", salt: DUMMY_SALT, iterations: 600000, hash: "SHA-256" }, key, 256);
}

// ── Validation ─────────────────────────────────────────────────────────────
const AVATARS = ["🐱","🐈","🐈‍⬛","🦁","🐯","🐆","🦊","🐺","🐻","🐼","🐨","🐰","🐹","🐭","🦄","🐲","🐾","⭐","🔥"];
function canonUser(raw: unknown) {
  if (typeof raw !== "string") return null;
  const u = raw.trim().toLowerCase();
  if (u.length < 3 || u.length > 32 || !/^[a-z0-9][a-z0-9_-]*$/.test(u)) return null;
  return u;
}
function validPwd(raw: unknown) { return typeof raw === "string" && [...(raw as string)].length >= 6 && enc.encode(raw as string).length <= 256; }
function validName(raw: unknown) { return typeof raw === "string" && (raw as string).trim().length > 0 && [...(raw as string).trim()].length <= 40; }
function validAvatar(raw: unknown) { return typeof raw === "string" && AVATARS.includes(raw as string); }
function validGrade(raw: unknown) { return Number.isInteger(raw) && (raw as number) >= 0 && (raw as number) <= 11; }
function validCounter(raw: unknown) { return Number.isSafeInteger(raw) && (raw as number) >= 0; }

// ── Rate limiter (fixed window in DB) ─────────────────────────────────────
const LIMITS: Record<string, { max: number; windowS: number }> = {
  register: { max: 5, windowS: 3600 },
  login:    { max: 10, windowS: 900 },
};
async function rateCheck(client: ReturnType<typeof db>, action: string, key: string): Promise<boolean> {
  const cfg = LIMITS[action];
  if (!cfg) return true;
  const lkey = `${action}:${key}`;
  const now = new Date().toISOString();
  const { data } = await client.from("sayan_limiter").select("key,window_started_at,attempt_count").eq("key", lkey).limit(1);
  const row = data?.[0];
  if (!row) {
    await client.from("sayan_limiter").insert({ key: lkey, window_started_at: now, attempt_count: 1 });
    return true;
  }
  const age = (Date.now() - new Date(row.window_started_at).getTime()) / 1000;
  if (age > cfg.windowS) {
    await client.from("sayan_limiter").update({ window_started_at: now, attempt_count: 1 }).eq("key", lkey);
    return true;
  }
  if (row.attempt_count >= cfg.max) return false;
  await client.from("sayan_limiter").update({ attempt_count: row.attempt_count + 1 }).eq("key", lkey);
  return true;
}

// ── Session helpers ────────────────────────────────────────────────────────
async function createSession(client: ReturnType<typeof db>, userId: string) {
  const token = newToken();
  const digest = await sha256hex(token);
  const expiresAt = new Date(Date.now() + SESSION_TTL_S * 1000).toISOString();
  await client.from("sayan_sessions").insert({ token_digest: digest, user_id: userId, expires_at: expiresAt });
  return token;
}
async function validateSession(client: ReturnType<typeof db>, req: Request) {
  const token = tokenFromRequest(req);
  if (!token) return null;
  const digest = await sha256hex(token);
  const { data } = await client.from("sayan_sessions")
    .select("token_digest,user_id,expires_at,revoked_at").eq("token_digest", digest).limit(1);
  const row = data?.[0];
  if (!row || row.revoked_at || new Date(row.expires_at) <= new Date()) return null;
  return { digest, userId: row.user_id as string };
}
async function revokeSession(client: ReturnType<typeof db>, digest: string) {
  await client.from("sayan_sessions").update({ revoked_at: new Date().toISOString() }).eq("token_digest", digest);
}

// ── Board score ────────────────────────────────────────────────────────────
const boardScore = (solved: number, totalPets: number) => solved * 10 + Math.floor(totalPets / 100);
const publicUser = (r: Record<string, unknown>) => ({
  id: r.id, username: r.username, name: r.display_name, grade: r.grade, avatar: r.avatar,
  solved: r.solved, totalPets: r.total_pets, bestCombo: r.best_combo,
});
const boardEntry = (r: Record<string, unknown>) => ({
  id: r.id, name: r.display_name, grade: r.grade, avatar: r.avatar,
  solved: r.solved, totalPets: r.total_pets,
  score: boardScore(r.solved as number, r.total_pets as number),
});

// ── Route handlers ─────────────────────────────────────────────────────────
async function handleRegister(client: ReturnType<typeof db>, body: unknown, origin: string | null) {
  if (!body || typeof body !== "object") return err("invalid_input", 400, {}, origin);
  const b = body as Record<string, unknown>;
  const username = canonUser(b.username);
  if (!username) return err("invalid_username", 400, {}, origin);
  if (!validPwd(b.password)) return err("invalid_password", 400, {}, origin);
  if (!validName(b.displayName)) return err("invalid_name", 400, {}, origin);
  if (!validGrade(b.grade)) return err("invalid_grade", 400, {}, origin);
  if (!validAvatar(b.avatar)) return err("invalid_avatar", 400, {}, origin);

  if (!(await rateCheck(client, "register", username))) return err("rate_limited", 429, {}, origin);

  const { data: existing } = await client.from("sayan_users").select("id").eq("username", username).limit(1);
  if (existing?.length) return err("username_taken", 409, {}, origin);

  const { salt, hash, iters } = await hashPwd(b.password as string);
  const { data: created, error } = await client.from("sayan_users").insert({
    username, password_salt: salt, password_hash: hash, password_iters: iters,
    display_name: (b.displayName as string).trim(), grade: b.grade, avatar: b.avatar,
  }).select("id,username,display_name,grade,avatar,solved,total_pets,best_combo").single();

  if (error || !created) return err("username_taken", 409, {}, origin);
  const token = await createSession(client, created.id);
  return json({ user: publicUser(created) }, 201, { "Set-Cookie": setCookie(token) }, origin);
}

async function handleLogin(client: ReturnType<typeof db>, body: unknown, origin: string | null) {
  if (!body || typeof body !== "object") return err("invalid_input", 400, {}, origin);
  const b = body as Record<string, unknown>;
  const username = canonUser(b.username);
  if (!username) return err("invalid_username", 400, {}, origin);
  if (typeof b.password !== "string") return err("invalid_password", 400, {}, origin);

  if (!(await rateCheck(client, "login", username))) return err("rate_limited", 429, {}, origin);

  const { data } = await client.from("sayan_users")
    .select("id,username,password_salt,password_hash,password_iters,display_name,grade,avatar,solved,total_pets,best_combo")
    .eq("username", username).limit(1);
  const user = data?.[0];
  if (!user) { await dummyVerify(b.password as string); return err("invalid_credentials", 401, {}, origin); }

  const ok = await verifyPwd(b.password as string, { salt: user.password_salt, hash: user.password_hash, iters: user.password_iters });
  if (!ok) return err("invalid_credentials", 401, {}, origin);

  const token = await createSession(client, user.id);
  return json({ user: publicUser(user) }, 200, { "Set-Cookie": setCookie(token) }, origin);
}

async function handleLogout(client: ReturnType<typeof db>, req: Request, origin: string | null) {
  const token = tokenFromRequest(req);
  if (token) {
    const digest = await sha256hex(token);
    await revokeSession(client, digest);
  }
  return json({ ok: true }, 200, { "Set-Cookie": clearCookie() }, origin);
}

async function handleMe(client: ReturnType<typeof db>, req: Request, origin: string | null) {
  const sess = await validateSession(client, req);
  if (!sess) return err("login_required", 401, { "Set-Cookie": clearCookie() }, origin);
  const { data } = await client.from("sayan_users")
    .select("id,username,display_name,grade,avatar,solved,total_pets,best_combo")
    .eq("id", sess.userId).limit(1);
  const user = data?.[0];
  if (!user) return err("login_required", 401, { "Set-Cookie": clearCookie() }, origin);
  return json({ user: publicUser(user) }, 200, {}, origin);
}

async function handleSync(client: ReturnType<typeof db>, req: Request, body: unknown, origin: string | null) {
  const sess = await validateSession(client, req);
  if (!sess) return err("login_required", 401, { "Set-Cookie": clearCookie() }, origin);
  if (!body || typeof body !== "object") return err("invalid_input", 400, {}, origin);
  const b = body as Record<string, unknown>;
  if (!validCounter(b.solved) || !validCounter(b.totalPets) || !validCounter(b.bestCombo)) return err("invalid_input", 400, {}, origin);

  const { data: cur } = await client.from("sayan_users")
    .select("id,username,display_name,grade,avatar,solved,total_pets,best_combo")
    .eq("id", sess.userId).limit(1);
  const c = cur?.[0];
  if (!c) return err("login_required", 401, { "Set-Cookie": clearCookie() }, origin);

  // Grade ladder: committed 1-11 can't go down or to 0
  const committed = typeof c.grade === "number" && c.grade >= 1 && c.grade <= 11;
  let nextGrade = c.grade;
  if (b.grade !== undefined && validGrade(b.grade)) {
    const g = b.grade as number;
    if (!(committed && (g === 0 || g < c.grade))) nextGrade = g;
  }

  const displayName = (b.displayName !== undefined && validName(b.displayName))
    ? (b.displayName as string).trim() : c.display_name;
  const avatar = (b.avatar !== undefined && validAvatar(b.avatar)) ? b.avatar as string : c.avatar;

  const { data: updated } = await client.from("sayan_users").update({
    display_name: displayName, grade: nextGrade, avatar,
    solved: Math.max(c.solved, b.solved as number),
    total_pets: Math.max(c.total_pets, b.totalPets as number),
    best_combo: Math.max(c.best_combo, b.bestCombo as number),
    updated_at: new Date().toISOString(),
  }).eq("id", sess.userId).select("id,username,display_name,grade,avatar,solved,total_pets,best_combo").single();

  if (!updated) return err("sync_failed", 503, {}, origin);
  return json({ user: publicUser(updated) }, 200, {}, origin);
}

async function handleBoard(client: ReturnType<typeof db>, origin: string | null) {
  const { data } = await client.from("sayan_users")
    .select("id,display_name,grade,avatar,solved,total_pets,best_combo")
    .order("solved", { ascending: false })
    .limit(500);
  const players = (data || []).map(boardEntry)
    .sort((a, b) => b.score - a.score || b.solved - a.solved || b.totalPets - a.totalPets);
  return json({ players }, 200, {}, origin);
}

// ── Entry point ────────────────────────────────────────────────────────────
Deno.serve(async (req: Request) => {
  const origin = req.headers.get("origin");

  // Preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(origin) });
  }

  const url = new URL(req.url);
  // Strip the function prefix: /functions/v1/sayan/api/xxx → /api/xxx
  const path = "/" + url.pathname.split("/").slice(url.pathname.startsWith("/functions/") ? 4 : 1).join("/");

  if (path === "/api/health" && req.method === "GET") {
    return json({ ok: true }, 200, {}, origin);
  }

  const client = db();

  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(origin) });

  if (path === "/api/board" && req.method === "GET") return handleBoard(client, origin);
  if (path === "/api/logout" && req.method === "POST") return handleLogout(client, req, origin);
  if (path === "/api/me" && req.method === "GET") return handleMe(client, req, origin);

  if (["POST"].includes(req.method) && ["/api/register", "/api/login", "/api/sync"].includes(path)) {
    let body: unknown = null;
    try { body = await req.json(); } catch { return err("invalid_input", 400, {}, origin); }
    if (path === "/api/register") return handleRegister(client, body, origin);
    if (path === "/api/login") return handleLogin(client, body, origin);
    if (path === "/api/sync") return handleSync(client, req, body, origin);
  }

  return err("not_found", 404, {}, origin);
});
