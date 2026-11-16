-- Sayan Clicker — schema for Supabase (Postgres + RLS).
-- username/password auth entirely app-owned (no Supabase Auth email dependency).
-- Run once in Supabase SQL Editor.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Users ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sayan_users (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username         text NOT NULL UNIQUE,          -- 3-32 [a-z0-9_-]
  password_salt    text NOT NULL,
  password_hash    text NOT NULL,
  password_iters   integer NOT NULL DEFAULT 600000,
  display_name     text NOT NULL,                 -- shown on board, ≤40 chars
  grade            integer NOT NULL DEFAULT 0,    -- 0=mix, 1-11
  avatar           text NOT NULL DEFAULT '🐱',   -- emoji from allowlist
  solved           integer NOT NULL DEFAULT 0,
  total_pets       bigint NOT NULL DEFAULT 0,
  best_combo       integer NOT NULL DEFAULT 0,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sayan_users_grade_idx ON sayan_users (grade);

-- ── Sessions ───────────────────────────────────────────────────────────────
-- Only SHA-256 token digests are stored; plaintext tokens never persisted.
CREATE TABLE IF NOT EXISTS sayan_sessions (
  token_digest text PRIMARY KEY,
  user_id      uuid NOT NULL REFERENCES sayan_users (id) ON DELETE CASCADE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  revoked_at   timestamptz
);
CREATE INDEX IF NOT EXISTS sayan_sessions_user_idx ON sayan_sessions (user_id);

-- ── Rate limiter ───────────────────────────────────────────────────────────
-- Fixed-window per key; unique PK for atomic upsert decisions.
CREATE TABLE IF NOT EXISTS sayan_limiter (
  key               text PRIMARY KEY,
  window_started_at timestamptz NOT NULL,
  attempt_count     integer NOT NULL DEFAULT 0
);

-- ── RLS: Edge Function uses service_role key — bypass is correct. ──────────
-- Public anon key (used by nothing except optional future CDN) gets no access.
ALTER TABLE sayan_users    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sayan_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sayan_limiter  ENABLE ROW LEVEL SECURITY;

-- service_role bypasses RLS by default in Supabase — no extra policy needed.
-- If you want to allow direct anon board reads in the future, add a SELECT policy here.
