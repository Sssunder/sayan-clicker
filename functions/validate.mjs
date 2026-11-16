// Input normalization and bounded validation. Pure functions, no database access.
import { AppError } from './http.mjs';

export const USERNAME_MIN_CHARS = 3;
export const USERNAME_MAX_CHARS = 32;
// Kid-friendly minimum for a low-stakes classroom game; PBKDF2 + rate limits still apply.
export const PASSWORD_MIN_CHARS = 6;
export const PASSWORD_MAX_BYTES = 256;
export const NAME_MAX_CHARS = 40;

// Fixed emoji presets by code point (no uploads, no arbitrary strings).
export const AVATARS = [
  '\u{1F431}', '\u{1F408}', '\u{1F408}\u{200D}\u{2B1B}', '\u{1F981}', '\u{1F42F}', '\u{1F406}',
  '\u{1F98A}', '\u{1F43A}', '\u{1F43B}', '\u{1F43C}', '\u{1F428}', '\u{1F430}',
  '\u{1F439}', '\u{1F42D}', '\u{1F984}', '\u{1F432}', '\u{1F43E}', '\u{2B50}', '\u{1F525}',
];

// Canonical username: trim + lowercase, strict charset; DB UNIQUE enforces uniqueness.
export function canonicalUsername(raw) {
  if (typeof raw !== 'string') throw new AppError('invalid_username', 400);
  const canonical = raw.trim().toLowerCase();
  if (canonical.length < USERNAME_MIN_CHARS || canonical.length > USERNAME_MAX_CHARS) {
    throw new AppError('invalid_username', 400);
  }
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(canonical)) throw new AppError('invalid_username', 400);
  return canonical;
}

// Password is bounded only; never logged, never echoed.
export function validatePassword(raw) {
  if (typeof raw !== 'string') throw new AppError('invalid_password', 400);
  if ([...raw].length < PASSWORD_MIN_CHARS) throw new AppError('invalid_password', 400);
  if (new TextEncoder().encode(raw).length > PASSWORD_MAX_BYTES) throw new AppError('invalid_password', 400);
  return raw;
}

// Display name (nickname shown on the board). Required, bounded, any script.
export function validateDisplayName(raw) {
  if (typeof raw !== 'string') throw new AppError('invalid_name', 400);
  const name = raw.trim();
  if (!name || [...name].length > NAME_MAX_CHARS) throw new AppError('invalid_name', 400);
  return name;
}

// Avatar must be one of the fixed emoji presets.
export function validateAvatar(raw) {
  if (typeof raw !== 'string' || !AVATARS.includes(raw)) throw new AppError('invalid_avatar', 400);
  return raw;
}

// Grade: 0 = mix, 1..11 = school class.
export function validateGrade(raw) {
  if (!Number.isInteger(raw) || raw < 0 || raw > 11) throw new AppError('invalid_grade', 400);
  return raw;
}

// Non-negative safe integer score counter.
export function validateCounter(raw) {
  if (!Number.isSafeInteger(raw) || raw < 0) throw new AppError('invalid_input', 400);
  return raw;
}

export function isUuid(value) {
  return typeof value === 'string'
    && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
}