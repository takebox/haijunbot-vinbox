// Plugin frontend extensions composable.
//
// Extracted from App.vue's <script setup> (Issue #118 Step 8) while preserving identical behavior:
// - state: pluginExtensions / pluginAdminTabs / pluginSidebarViews / pluginToolPanels
// - title mapping: pluginSidebarTitle / pluginToolPanelTitle / WORKSPACE_SIDEBAR_TITLES / workspaceSidebarTitle
// - loading: loadPluginExtensionsForUi / resolvePluginExtensionComponent
// - detection: isPluginSidebarView / isPluginToolView
// - async component cache & activation: pluginSidebarCompCache / activePluginSidebarComp / activePluginToolPanelComp
//
// Dependency injection (the caller passes these in setup; must be called after their definition):
// - workspaceSidebarView: ref of the sidebar's current view (created in App.vue, earlier than this composable's call site)
// - fetchPluginExtensions / loadExtensionComponent: plugin extension loaders (imported from external modules and passed in)
// - fetchWithAuth / getHttpProtocol / hasAuthToken / getGatewayAddress: gateway access functions
import { computed, defineAsyncComponent, ref } from 'vue'
export function usePlugins({
  workspaceSidebarView,
  fetchPluginExtensions,
  loadExtensionComponent,
  fetchWithAuth,
  getHttpProtocol,
  hasAuthToken,
  getGatewayAddress,
}) {
  // Plugin frontend extension list (scheme 2): parsed from each plugin's config.yaml frontend declaration.
  // Each item: { nodeId, plugin, extType, id, title, entry, url }
  const pluginExtensions = ref([])
  // Filter by extension-point type
  const pluginAdminTabs = computed(() => pluginExtensions.value.filter(e => e.extType === 'admin_tabs'))
  const pluginSidebarViews = computed(() => pluginExtensions.value.filter(e => e.extType === 'sidebar_views'))
  const pluginToolPanels = computed(() => pluginExtensions.value.filter(e => e.extType === 'tool_panels'))
  // Title mapping for dynamic sidebar views: view name = plugin:${id}
  function pluginSidebarTitle(view) {
    const ext = pluginSidebarViews.value.find(e => `plugin:${e.id}` === view)
    return ext ? ext.title : ''
  }
  // tool_panels extension point reuses sidebar rendering: view name = plugin-tool:${id}
  function pluginToolPanelTitle(view) {
    const ext = pluginToolPanels.value.find(e => `plugin-tool:${e.id}` === view)
    return ext ? ext.title : ''
  }
  // Sidebar title: mapped from the current view; plugin dynamic views use pluginSidebarTitle / pluginToolPanelTitle
  const WORKSPACE_SIDEBAR_TITLES = {
    search: 'Global Search',
    git: 'Git',
    agents: 'Agent List',
    manage: 'Enhanced Capabilities',
    timers: 'Scheduled Tasks',
    plugins: 'Plugin Management',
    orchestration: 'Orchestration View',
  }
  const workspaceSidebarTitle = computed(() => {
    const view = workspaceSidebarView.value
    if (isPluginSidebarView(view)) return pluginSidebarTitle(view)
    if (isPluginToolView(view)) return pluginToolPanelTitle(view)
    return WORKSPACE_SIDEBAR_TITLES[view] || 'File Tree'
  })
  // Load the plugin extension list (called after login); failures are silent and do not affect the main UI
  async function loadPluginExtensionsForUi() {
    if (!hasAuthToken()) return
    const { host, port } = getGatewayAddress()
    const exts = await fetchPluginExtensions({
      fetchWithAuth,
      nodeId: 'master',
      baseUrl: `${host}:${port}`,
      getHttpProtocol,
    })
    pluginExtensions.value = exts
  }
  // Asynchronously load the plugin extension component (for sidebar/admin panel rendering)
  function resolvePluginExtensionComponent(ext) {
    return loadExtensionComponent(ext, { fetchWithAuth, getHttpProtocol })
  }
  // Whether a sidebar view is a plugin extension view
  function isPluginSidebarView(view) {
    return typeof view === 'string' && view.startsWith('plugin:')
  }
  // Whether a sidebar view is a plugin tool_panel extension view
  function isPluginToolView(view) {
    return typeof view === 'string' && view.startsWith('plugin-tool:')
  }
  // Cache the async component instances for plugin sidebars so computed does not return a fresh
  // defineAsyncComponent each time. A fresh instance each render makes Vue treat <component :is> as
  // a different component, repeatedly unmounting/reloading and leaving the plugin content empty.
  const pluginSidebarCompCache = new Map()
  // Async component for the currently active plugin sidebar view (rendered via <component :is>)
  const activePluginSidebarComp = computed(() => {
    const view = workspaceSidebarView.value
    if (!isPluginSidebarView(view)) return null
    const ext = pluginSidebarViews.value.find(e => `plugin:${e.id}` === view)
    if (!ext) return null
    if (!pluginSidebarCompCache.has(ext.id)) {
      pluginSidebarCompCache.set(ext.id, defineAsyncComponent(() => resolvePluginExtensionComponent(ext)))
    }
    return pluginSidebarCompCache.get(ext.id)
  })
  // Async component for the currently active plugin tool_panel view (reuses the pluginSidebarCompCache
  // but keys with the plugin-tool: prefix to avoid colliding with same-named sidebar_views extensions)
  const activePluginToolPanelComp = computed(() => {
    const view = workspaceSidebarView.value
    if (!isPluginToolView(view)) return null
    const ext = pluginToolPanels.value.find(e => `plugin-tool:${e.id}` === view)
    if (!ext) return null
    const cacheKey = `plugin-tool:${ext.id}`
    if (!pluginSidebarCompCache.has(cacheKey)) {
      pluginSidebarCompCache.set(cacheKey, defineAsyncComponent(() => resolvePluginExtensionComponent(ext)))
    }
    return pluginSidebarCompCache.get(cacheKey)
  })

  return {
    pluginExtensions,
    pluginAdminTabs,
    pluginSidebarViews,
    pluginToolPanels,
    pluginSidebarTitle,
    pluginToolPanelTitle,
    WORKSPACE_SIDEBAR_TITLES,
    workspaceSidebarTitle,
    loadPluginExtensionsForUi,
    resolvePluginExtensionComponent,
    isPluginSidebarView,
    isPluginToolView,
    pluginSidebarCompCache,
    activePluginSidebarComp,
    activePluginToolPanelComp,
  }
}
