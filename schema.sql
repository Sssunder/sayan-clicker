-- Sayan clicker online class backend. Business + app-owned auth tables only.
-- Access policies: function_backend generates fixed private policies (accessPolicies: []).
-- The Function enforces ownership; the board endpoint is the controlled public read.

CREATE TABLE app.users (
  id uuid PRIMARY KEY,
  username text NOT NULL UNIQUE,
  password_salt text NOT NULL,
  password_hash text NOT NULL,
  password_iterations integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  display_name text NOT NULL,
  grade integer NOT NULL,
  avatar text NOT NULL,
  solved integer NOT NULL,
  total_pets bigint NOT NULL,
  best_combo integer NOT NULL
);
CREATE INDEX users_grade_idx ON app.users (grade);

-- Only token digests, user id and times; plaintext session tokens never stored.
CREATE TABLE app.sessions (
  token_digest text PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES app.users (id),
  created_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz
);

-- Fixed-window rate limiter: one row per key, unique PK for atomic decisions.
CREATE TABLE app.auth_limiter (
  key text PRIMARY KEY,
  window_started_at timestamptz NOT NULL,
  attempt_count integer NOT NULL
);