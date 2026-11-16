import { createSiteContext, createDatabaseClient, errorResponse } from './_qoder/backend.mjs';
import { createApplication } from './router.mjs';

// forwardApplicationCredentials keeps this app's own Cookie / Authorization:
// registration, login and sessions are fully app-owned; no platform identity, no fallback.
const handle = createApplication({ db: createDatabaseClient(), origin: () => Deno.env.get('APP_ORIGIN') });

Deno.serve(async (request) => {
  let context;
  try {
    context = createSiteContext(request, { forwardApplicationCredentials: true });
    return await handle(context);
  } catch (error) {
    return errorResponse(error, context?.requestId);
  }
});