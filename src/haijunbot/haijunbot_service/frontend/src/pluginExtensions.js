// Plugin frontend extension loader (approach 2: runtime dynamic loading).
//
// The frontend is a static vite build, so plugins cannot take part in the build.
// A plugin's config.yaml declares its `frontend` extension points (admin_tabs /
// sidebar_views / tool_panels); the backend serves the plugin's frontend assets
// per node (GET /api/plugins/{node_id}/{name}/frontend/{path}, returning the
// content wrapped in JSON). This module is responsible for:
//   - fetching the extension manifest (fetchPluginExtensions)
//   - dynamically loading plugin JS as a Vue component (loadExtensionComponent)
//
// Plugin JS is a pure browser ES module that uses Vue via the global window.Vue
// (exposed by main.js); it does not `import 'vue'` and exports a Vue component
// definition (a render function or an options object both work).

// Loaded component cache: `${nodeId}/${pluginName}/${extType}/${extId}` -> Promise<Component|null>
const componentCache = new Map();

/**
 * Fetches the plugin extension manifest for a given node.
 *
 * @param {object} opts
 * @param {Function} opts.fetchWithAuth authenticated fetch (injected by App.vue)
 * @param {string} [opts.nodeId='master'] target node
 * @param {string} opts.baseUrl gateway address (e.g. http://host:port)
 * @param {Function} [opts.getHttpProtocol] protocol getter (http/https)
 * @returns {Promise<Array>} the extension manifest array; each item is shaped like:
 *   { nodeId, plugin, extType, id, title, entry, url }
 *   On failure an empty array is returned (does not affect the main UI).
 */
export async function fetchPluginExtensions({
  fetchWithAuth,
  nodeId = "master",
  baseUrl,
  getHttpProtocol,
}) {
  const extensions = [];
  try {
    const protocol =
      typeof getHttpProtocol === "function" ? getHttpProtocol() : "http";
    const url = `${protocol}://${baseUrl}/api/plugins?node_id=${encodeURIComponent(nodeId)}`;
    const resp = await fetchWithAuth(url);
    if (!resp || !resp.ok) return extensions;
    const result = await resp.json();
    if (!result || !result.success) return extensions;
    const plugins = (result.data && result.data.plugins) || [];
    for (const plugin of plugins) {
      const frontend = plugin && plugin.frontend;
      if (!frontend || typeof frontend !== "object") continue;
      for (const extType of ["admin_tabs", "sidebar_views", "tool_panels"]) {
        const list = frontend[extType];
        if (!Array.isArray(list)) continue;
        for (const ext of list) {
          if (!ext || !ext.id || !ext.entry) continue;
          extensions.push({
            nodeId,
            plugin: plugin.name,
            pluginVersion: plugin.version,
            extType,
            id: ext.id,
            title: ext.title || ext.id,
            entry: ext.entry,
            icon: ext.icon || null,
            iconSvg: null,
            url: buildExtensionUrl({
              nodeId,
              plugin: plugin.name,
              entry: ext.entry,
              baseUrl,
              getHttpProtocol,
            }),
          });
        }
      }
    }
    // Load SVG content for extensions that specify an icon file path (inline SVGs are used directly)
    await Promise.all(
      extensions.map(async (ext) => {
        if (!ext.icon) return;
        if (
          typeof ext.icon === "string" &&
          ext.icon.trim().startsWith("<svg")
        ) {
          ext.iconSvg = ext.icon;
          return;
        }
        try {
          const iconUrl = buildExtensionUrl({
            nodeId,
            plugin: ext.plugin,
            entry: ext.icon,
            baseUrl,
            getHttpProtocol,
          });
          const resp = await fetchWithAuth(iconUrl);
          if (!resp || !resp.ok) return;
          const result = await resp.json();
          if (!result || !result.success) return;
          const svg = result.data && result.data.content;
          if (typeof svg === "string" && svg.trim()) ext.iconSvg = svg;
        } catch (e) {
          console.warn(
            `[PluginExtensions] Failed to load icon for ${ext.plugin}/${ext.id}:`,
            e,
          );
        }
      }),
    );
  } catch (e) {
    console.warn("[PluginExtensions] Failed to fetch plugin extensions:", e);
  }
  return extensions;
}

/**
 * Builds the serve endpoint URL for the plugin's frontend assets.
 * GET /api/plugins/{node_id}/{name}/frontend/{path}
 */
export function buildExtensionUrl({
  nodeId,
  plugin,
  entry,
  baseUrl,
  getHttpProtocol,
}) {
  const protocol =
    typeof getHttpProtocol === "function" ? getHttpProtocol() : "http";
  const path = String(entry || "").replace(/^\/+/, "");
  return `${protocol}://${baseUrl}/api/plugins/${encodeURIComponent(nodeId)}/${encodeURIComponent(plugin)}/frontend/${path}`;
}

/**
 * Dynamically loads plugin frontend JS as a Vue component.
 *
 * The backend serve_frontend endpoint returns the content as a JSON-wrapped JS
 * source string, which cannot be imported directly via import(url). We fetch the
 * source, create a module from a Blob URL, then import() it. The plugin JS should
 * be a single self-contained file (no relative-path resources), otherwise the
 * Blob module cannot be resolved.
 *
 * @param {object} ext an extension manifest item (element returned by fetchPluginExtensions)
 * @param {object} opts { fetchWithAuth, getHttpProtocol }
 * @returns {Promise<Component|null>} the Vue component (default export), or null on failure
 */
export async function loadExtensionComponent(
  ext,
  { fetchWithAuth, getHttpProtocol } = {},
) {
  if (!ext) return null;
  const cacheKey = `${ext.nodeId}/${ext.plugin}/${ext.extType}/${ext.id}`;
  if (componentCache.has(cacheKey)) return componentCache.get(cacheKey);

  const promise = (async () => {
    try {
      const protocol =
        typeof getHttpProtocol === "function" ? getHttpProtocol() : "http";
      const url = buildExtensionUrl({
        nodeId: ext.nodeId,
        plugin: ext.plugin,
        entry: ext.entry,
        baseUrl: urlHost(ext.url),
        getHttpProtocol: () => protocol,
      });
      const resp = await fetchWithAuth(url);
      if (!resp || !resp.ok) return null;
      const result = await resp.json();
      if (!result || !result.success) return null;
      const source = result.data && result.data.content;
      if (typeof source !== "string" || !source.trim()) return null;

      const blob = new Blob([source], { type: "application/javascript" });
      const blobUrl = URL.createObjectURL(blob);
      try {
        const mod = await import(/* @vite-ignore */ blobUrl);
        return mod && mod.default ? mod.default : null;
      } finally {
        URL.revokeObjectURL(blobUrl);
      }
    } catch (err) {
      console.warn(
        `[PluginExtensions] Failed to load extension ${ext.plugin}/${ext.id}:`,
        err,
      );
      return null;
    }
  })();

  componentCache.set(cacheKey, promise);
  return promise;
}

// Extracts host:port from a full URL (used to build the serve endpoint)
function urlHost(url) {
  try {
    const parsed = new URL(url);
    return parsed.host;
  } catch {
    return "";
  }
}

/** Clears the component cache (call after uninstalling/upgrading a plugin) */
export function clearExtensionCache() {
  componentCache.clear();
}
