/** Base URL of the FastAPI analysis server (read-only API).
 *
 * Default: the SAME host the UI is served from, on the API port — so opening the reviewer UI
 * via the machine's LAN IP (e.g. http://10.19.8.252:3000) calls the API on that machine
 * instead of the viewer's own localhost (which would fail on any other device).
 * Falls back to localhost during server-side rendering (no `window`).
 * Override explicitly with NEXT_PUBLIC_API_BASE (e.g. a deployed API URL).
 */
const API_PORT = process.env.NEXT_PUBLIC_API_PORT ?? "8000";

function defaultApiBase(): string {
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:${API_PORT}`;
  }
  return `http://localhost:${API_PORT}`;
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || defaultApiBase();
