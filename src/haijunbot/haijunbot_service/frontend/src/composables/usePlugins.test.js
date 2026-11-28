// usePlugins unit tests
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { usePlugins } from './usePlugins.js'

// Build a DI harness for usePlugins
function makeHarness({ exts = [], workspaceSidebarViewValue = 'agents' } = {}) {
  const workspaceSidebarView = ref(workspaceSidebarViewValue)
  const fetchPluginExtensions = vi.fn(async () => exts)
  const loadExtensionComponent = vi.fn(async () => ({}))
  const fetchWithAuth = vi.fn()
  const getHttpProtocol = vi.fn(() => 'http')
  const hasAuthToken = vi.fn(() => true)
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const api = usePlugins({
    workspaceSidebarView,
    fetchPluginExtensions,
    loadExtensionComponent,
    fetchWithAuth,
    getHttpProtocol,
    hasAuthToken,
    getGatewayAddress,
  })
  return {
    api,
    workspaceSidebarView,
    fetchPluginExtensions,
    loadExtensionComponent,
    fetchWithAuth,
    getHttpProtocol,
    hasAuthToken,
    getGatewayAddress,
  }
}

// Build one extension item
function makeExt({ id = 'ext-1', extType = 'sidebar_views', title = 'Extension 1' } = {}) {
  return { nodeId: 'master', plugin: 'demo', extType, id, title, entry: 'index.js', url: 'http://x' }
}

describe('usePlugins', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initial state: empty extension list and empty filtered lists', () => {
    const { api } = makeHarness()
    expect(api.pluginExtensions.value).toEqual([])
    expect(api.pluginAdminTabs.value).toEqual([])
    expect(api.pluginSidebarViews.value).toEqual([])
    expect(api.pluginToolPanels.value).toEqual([])
  })

  it('loadPluginExtensionsForUi loads the extension list into pluginExtensions', async () => {
    const exts = [makeExt({ id: 'a', extType: 'admin_tabs' }), makeExt({ id: 'b', extType: 'sidebar_views' })]
    const { api, fetchPluginExtensions, getGatewayAddress } = makeHarness({ exts })
    await api.loadPluginExtensionsForUi()
    expect(fetchPluginExtensions).toHaveBeenCalledTimes(1)
    expect(fetchPluginExtensions).toHaveBeenCalledWith({
      fetchWithAuth: expect.any(Function),
      nodeId: 'master',
      baseUrl: '127.0.0.1:8000',
      getHttpProtocol: expect.any(Function),
    })
    expect(api.pluginExtensions.value).toEqual(exts)
  })

  it('loadPluginExtensionsForUi returns early and does not request without a token', async () => {
    const { api, hasAuthToken, fetchPluginExtensions } = makeHarness()
    hasAuthToken.mockReturnValue(false)
    await api.loadPluginExtensionsForUi()
    expect(fetchPluginExtensions).not.toHaveBeenCalled()
  })

  it('filters by extension point type', () => {
    const exts = [
      makeExt({ id: 'a', extType: 'admin_tabs' }),
      makeExt({ id: 'b', extType: 'sidebar_views' }),
      makeExt({ id: 'c', extType: 'tool_panels' }),
    ]
    const { api, workspaceSidebarView } = makeHarness({ exts })
    // Write manually (simulating the loadPluginExtensionsForUi result)
    api.pluginExtensions.value = exts
    expect(api.pluginAdminTabs.value.map(e => e.id)).toEqual(['a'])
    expect(api.pluginSidebarViews.value.map(e => e.id)).toEqual(['b'])
    expect(api.pluginToolPanels.value.map(e => e.id)).toEqual(['c'])
    // workspaceSidebarTitle uses WORKSPACE_SIDEBAR_TITLES for ordinary views
    workspaceSidebarView.value = 'git'
    expect(api.workspaceSidebarTitle.value).toBe('Git')
    workspaceSidebarView.value = 'unknown'
    expect(api.workspaceSidebarTitle.value).toBe('File Tree')
  })

  it('isPluginSidebarView / isPluginToolView checks', () => {
    const { api } = makeHarness()
    expect(api.isPluginSidebarView('plugin:foo')).toBe(true)
    expect(api.isPluginSidebarView('plugin-tool:foo')).toBe(false)
    expect(api.isPluginSidebarView('agents')).toBe(false)
    expect(api.isPluginToolView('plugin-tool:foo')).toBe(true)
    expect(api.isPluginToolView('plugin:foo')).toBe(false)
    expect(api.isPluginToolView(null)).toBe(false)
  })

  it('pluginSidebarTitle / pluginToolPanelTitle mapping', () => {
    const exts = [makeExt({ id: 's1', extType: 'sidebar_views', title: 'Side extension' }), makeExt({ id: 't1', extType: 'tool_panels', title: 'Tool panel' })]
    const { api } = makeHarness({ exts })
    api.pluginExtensions.value = exts
    expect(api.pluginSidebarTitle('plugin:s1')).toBe('Side extension')
    expect(api.pluginSidebarTitle('plugin:none')).toBe('')
    expect(api.pluginToolPanelTitle('plugin-tool:t1')).toBe('Tool panel')
    expect(api.pluginToolPanelTitle('plugin-tool:none')).toBe('')
  })

  it('workspaceSidebarTitle uses the dynamic title for plugin views', () => {
    const exts = [makeExt({ id: 's1', extType: 'sidebar_views', title: 'Side extension' })]
    const { api, workspaceSidebarView } = makeHarness({ exts })
    api.pluginExtensions.value = exts
    workspaceSidebarView.value = 'plugin:s1'
    expect(api.workspaceSidebarTitle.value).toBe('Side extension')
  })

  it('activePluginSidebarComp returns a cached component (same instance) for plugin views', () => {
    const exts = [makeExt({ id: 's1', extType: 'sidebar_views', title: 'Side extension' })]
    const { api, workspaceSidebarView, loadExtensionComponent } = makeHarness({ exts })
    api.pluginExtensions.value = exts
    workspaceSidebarView.value = 'plugin:s1'
    const comp1 = api.activePluginSidebarComp.value
    expect(comp1).toBeTruthy()
    // Accessing again should hit the cache: same instance
    const comp2 = api.activePluginSidebarComp.value
    expect(comp1).toBe(comp2)
    // Non-plugin views return null
    workspaceSidebarView.value = 'agents'
    expect(api.activePluginSidebarComp.value).toBe(null)
  })

  it('activePluginToolPanelComp returns a component for tool_panel views, isolated from the sidebar cache key', () => {
    const exts = [
      makeExt({ id: 'x', extType: 'sidebar_views', title: 'Side' }),
      makeExt({ id: 'x', extType: 'tool_panels', title: 'Tool' }),
    ]
    const { api, workspaceSidebarView } = makeHarness({ exts })
    api.pluginExtensions.value = exts
    workspaceSidebarView.value = 'plugin:x'
    const sidebarComp = api.activePluginSidebarComp.value
    workspaceSidebarView.value = 'plugin-tool:x'
    const toolComp = api.activePluginToolPanelComp.value
    // The two cache keys differ (plugin:x vs plugin-tool:x), so instances are different
    expect(sidebarComp).not.toBe(toolComp)
    expect(api.activePluginToolPanelComp.value).toBe(toolComp)
  })
})
