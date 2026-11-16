// HTTP helpers: fixed-origin check, bounded JSON reads, stable error objects.
// Application identity comes only from this app's own session validation.

// Fixed public HTTPS origin of this site (a site constant, not a secret).
// Set to the allocated site origin before deployment; never read Host/Forwarded.
export const PUBLIC_ORIGIN = 'https://sayan-class-lmn1gvdnznk.qoder.website';

export const BODY_LIMIT_BYTES = 8192;

export class AppError extends Error {
  constructor(code, status) {
    super(code);
    this.name = 'AppError';
    this.code = code;
    this.status = status;
  }
}

const NO_STORE = { 'cache-control': 'private, no-store', 'referrer-policy': 'no-referrer' };

export function json(value, status = 200, extra = {}) {
  return Response.json(value, { status, headers: { ...NO_STORE, ...extra } });
}

export function errorJson(code, status, extra = {}) {
  return json({ error: code }, status, extra);
}

// Gateway replaces the app segment with the physical function name; Provider may strip /functions/v1.
export function applicationPath(request) {
  const match = new URL(request.url).pathname.match(/^\/(?:functions\/v1\/)?(?:app|app-d[0-9a-f]{32})(\/.*)?$/);
  if (!match) throw new AppError('not_found', 404);
  return match[1] || '/';
}

// Unsafe methods must come from the fixed origin (second CSRF line beyond SameSite=Lax cookies).
export function requireTrustedOrigin(request, origin = PUBLIC_ORIGIN) {
  let configured;
  try { configured = new URL(origin); } catch { throw new AppError('application_auth_not_configured', 503); }
  if (configured.protocol !== 'https:' || configured.origin !== origin) throw new AppError('application_auth_not_configured', 503);
  if (['GET', 'HEAD', 'OPTIONS'].includes(request.method)) return;
  if (request.headers.get('origin') !== origin) throw new AppError('origin_forbidden', 403);
}

// Bound by bytes actually read from the stream, not Content-Length.
export async function readJson(request, maxBytes = BODY_LIMIT_BYTES) {
  if (request.headers.get('content-type')?.split(';')[0].trim() !== 'application/json') {
    throw new AppError('invalid_input', 400);
  }
  const reader = request.body?.getReader();
  if (!reader) throw new AppError('invalid_input', 400);
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > maxBytes) {
        await reader.cancel();
        throw new AppError('payload_too_large', 413);
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try {
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } catch {
    throw new AppError('invalid_input', 400);
  }
}

// Map data-layer results to business results; keep stable codes, never leak provider detail.
export function rows(result) {
  if (result?.error || !Array.isArray(result?.data)) throw new AppError('database_unavailable', 503);
  return result.data;
}