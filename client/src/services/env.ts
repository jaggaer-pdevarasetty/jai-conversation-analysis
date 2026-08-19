/** Current environment (uit/prod) for the reviewer session.
 *
 * The value is a cross-cutting concern (like a header), so instead of threading it through every
 * service call we keep it here and append `?env=` to every analysis-API request. It is read
 * synchronously from localStorage at module load so the very first request already carries the
 * persisted environment (no race with React effects). Changing it does a full reload (see
 * EnvContext) so every provider + page re-fetches for the new environment.
 */
const STORAGE_KEY = "jai.env";

let _env = "uit";
if (typeof window !== "undefined") {
  _env = window.localStorage.getItem(STORAGE_KEY) || "uit";
}

export function getEnv(): string {
  return _env;
}

export function persistEnv(env: string): void {
  _env = env || "uit";
  if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, _env);
}

/** Append the current environment to an analysis-API URL. */
export function withEnv(url: URL): URL {
  url.searchParams.set("env", _env);
  return url;
}
