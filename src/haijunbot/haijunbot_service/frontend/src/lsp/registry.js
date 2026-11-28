/**
 * Registry for the LSP language server catalog.
 *
 * All data comes from the backend `GET /api/lsp/servers`; the frontend hardcodes no languages:
 * to add a language, just add an entry under the `lsp.languages` section of `~/.haijunbot/config.yaml`; this file needs no changes.
 *
 * Catalog fields (returned by the backend):
 *   id            unique language server identifier, e.g. "python"
 *   monacoLanguage the corresponding Monaco language id, e.g. "python"
 *   extensions    list of file extensions, e.g. [".py", ".pyi"]
 *   installHint   hint text when the server is not installed
 *   source        source, always "config"
 */

/** @type {Map<string, object>} monacoLanguage -> serverSpec */
let serverByLanguage = new Map();

/** @type {Map<string, object>} extension (lowercase, with dot) -> serverSpec */
let serverByExtension = new Map();

let loaded = false;
let loadPromise = null;

/**
 * Fetch the catalog and build the index. On failure, silently fall back to an empty map (no throw).
 *
 * @param {object} deps
 * @param {(path: string, options?: object) => Promise<Response>} deps.fetchWithAuth
 * @param {() => {host: string, port: string}} deps.getGatewayAddress
 * @param {() => string} deps.getHttpProtocol
 * @param {boolean} [force] force a fresh fetch (ignore cache)
 * @returns {Promise<Map<string, object>>} monacoLanguage -> serverSpec
 */
export async function loadLspServers(
  { fetchWithAuth, getGatewayAddress, getHttpProtocol },
  force = false,
) {
  if (loaded && !force) return serverByLanguage;
  if (loadPromise && !force) return loadPromise;

  loadPromise = (async () => {
    try {
      const { host, port } = getGatewayAddress();
      const protocol = getHttpProtocol();
      const url = `${protocol}://${host}:${port}/api/lsp/servers`;
      const response = await fetchWithAuth(url, { method: "GET" });
      if (!response.ok) {
        console.warn(`[lsp] Failed to fetch the language server catalog: HTTP ${response.status}`);
        return serverByLanguage;
      }
      const result = await response.json();
      const servers = Array.isArray(result?.servers) ? result.servers : [];

      const byLang = new Map();
      const byExt = new Map();
      for (const spec of servers) {
        if (!spec || !spec.id || !spec.monacoLanguage) continue;
        // The backend already dedupes by language name; keep only the first per monacoLanguage
        if (!byLang.has(spec.monacoLanguage)) {
          byLang.set(spec.monacoLanguage, spec);
        }
        for (const ext of spec.extensions || []) {
          byExt.set(String(ext).toLowerCase(), spec);
        }
      }
      serverByLanguage = byLang;
      serverByExtension = byExt;
      loaded = true;
    } catch (error) {
      console.warn(
        "[lsp] Error fetching the language server catalog; degraded to no LSP:",
        error?.message || error,
      );
    }
    return serverByLanguage;
  })();

  return loadPromise;
}

/**
 * Look up a server spec by Monaco language id.
 * @param {string} monacoLanguage
 * @returns {object|null}
 */
export function getServerByLanguage(monacoLanguage) {
  if (!monacoLanguage) return null;
  return serverByLanguage.get(String(monacoLanguage)) || null;
}

/**
 * Look up a server spec by file extension (fallback when the language id is unreliable).
 * @param {string} path
 * @returns {object|null}
 */
export function getServerByPath(path) {
  if (!path) return null;
  const match = String(path).match(/(\.[^./\\]+)$/);
  if (!match) return null;
  return serverByExtension.get(match[1].toLowerCase()) || null;
}

/** Whether the catalog has been loaded successfully. */
export function isLspRegistryLoaded() {
  return loaded;
}
