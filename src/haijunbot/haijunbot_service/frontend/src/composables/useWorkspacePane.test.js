// useWorkspacePane unit tests
// Covers: workspace panel state, pane tree core (split/close/collapse/activate/move),
// view routing (ensureAgentEditorPane/ensurePaneForView/setActivePaneView),
// layout persistence (sanitize/restore/persist), content restoration (restoreWorkspacePaneContents),
// plugin extension passthrough (usePlugins return symbols).
// mocks usePlugins (an internal call) and the pluginExtensions loader; the remaining dependency injection is direct/getter.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, computed } from 'vue'

// ---- mock the usePlugins module (called internally by useWorkspacePane) ----
// Note: ref/computed cannot be used inside vi.hoisted (not initialized yet), so pluginState in hoisted only holds
// serializable mock functions and shells; the real ref/computed are rebuilt by makeHarness at runtime.
const { usePluginsMock, pluginStateShell } = vi.hoisted(() => {
  const pluginStateShell = {
    pluginExtensions: null,
    pluginAdminTabs: null,
    pluginSidebarViews: null,
    pluginToolPanels: null,
    pluginSidebarTitle: vi.fn((view) => ''),
    pluginToolPanelTitle: vi.fn((view) => ''),
    WORKSPACE_SIDEBAR_TITLES: {},
    workspaceSidebarTitle: null,
    loadPluginExtensionsForUi: vi.fn(async () => {}),
    resolvePluginExtensionComponent: vi.fn(() => null),
    isPluginSidebarView: vi.fn(() => false),
    isPluginToolView: vi.fn(() => false),
    pluginSidebarCompCache: new Map(),
    activePluginSidebarComp: null,
    activePluginToolPanelComp: null,
  }
  const usePluginsMock = vi.fn(() => pluginStateShell)
  return { usePluginsMock, pluginStateShell }
})
vi.mock('./usePlugins.js', () => ({ usePlugins: usePluginsMock }))
// ---- mock the pluginExtensions loader ----
const { fetchPluginExtensionsMock, loadExtensionComponentMock } = vi.hoisted(() => {
  return {
    fetchPluginExtensionsMock: vi.fn(async () => []),
    loadExtensionComponentMock: vi.fn(async () => null),
  }
})
vi.mock('../pluginExtensions.js', () => ({
  fetchPluginExtensions: fetchPluginExtensionsMock,
  loadExtensionComponent: loadExtensionComponentMock,
}))

// ---- import the module under test (must be after the mocks) ----
const { useWorkspacePane } = await import('./useWorkspacePane.js')

// ---- mock the global environment ----
function setupGlobals() {
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0)
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  globalThis.URL.revokeObjectURL = vi.fn()
}

// Build the useWorkspacePane dependency-injection harness
function makeHarness(overrides = {}) {
  // —— Rebuild pluginState's ref/computed (ref/computed cannot be used inside vi.hoisted) ——
  const pluginState = {
    ...pluginStateShell,
    pluginExtensions: ref([]),
    pluginAdminTabs: computed(() => pluginState.pluginExtensions.value.filter(e => e.extType === 'admin_tabs')),
    pluginSidebarViews: computed(() => pluginState.pluginExtensions.value.filter(e => e.extType === 'sidebar_views')),
    pluginToolPanels: computed(() => pluginState.pluginExtensions.value.filter(e => e.extType === 'tool_panels')),
    workspaceSidebarTitle: computed(() => ''),
    activePluginSidebarComp: computed(() => null),
    activePluginToolPanelComp: computed(() => null),
  }
  usePluginsMock.mockReturnValue(pluginState)
  // —— Directly passed dependencies (defined before the call site) ——
  const fetchWithAuth = vi.fn()
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const getHttpProtocol = vi.fn(() => 'http')
  const hasAuthToken = vi.fn(() => true)
  const windowWidth = ref(1200)
  const clamp = vi.fn((v, min, max) => Math.min(Math.max(v, min), max))
  const focusWindow = vi.fn()
  const getWorkspaceTabByPath = vi.fn(() => null)
  const activeWorkspaceTab = ref(null)
  const editorViews = new Map()
  const workspaceViewPanes = new Map()
  const diffEditorViews = new Map()
  const workspacePaneTabs = new Map()
  const workspacePaneTabsVersion = ref(0)
  const remountMonacoEditor = vi.fn()
  const scheduleWorkspaceLayout = vi.fn()
  const layoutMonacoEditor = vi.fn()
  const activateWorkspaceTab = vi.fn()
  const openWorkspaceFile = vi.fn(async () => {})
  const layoutGitDiffEditor = vi.fn()
  const disposeDiffEditorForPane = vi.fn()
  const disposeAllDiffEditors = vi.fn()
  const loadDiffForPane = vi.fn(async () => {})
  // —— Getter-injected dependencies (defined after the call site, re-evaluated internally via xxx()) ——
  const panels = ref([])
  const activePanelId = ref(null)
  const closePanel = vi.fn()
  const getPanelAgent = vi.fn(() => null)
  const workspaceSessionPanelId = ref(null)
  const agentList = ref([])
  const gitAgentId = ref(null)
  const switchAgent = vi.fn(async () => {})
  const activeTerminalId = ref(null)
  const terminalSessions = ref([])
  const restoreTerminalSessions = vi.fn(() => vi.fn(async () => {}))
  const focusFirstIn = vi.fn()

  const api = useWorkspacePane({
    fetchWithAuth,
    getGatewayAddress,
    getHttpProtocol,
    hasAuthToken,
    windowWidth,
    // getter-injected (useWorkspaceEditor domain-B symbols, re-evaluated internally by useWorkspacePane via xxx())
    clamp: () => clamp,
    focusWindow: () => focusWindow,
    getWorkspaceTabByPath: () => getWorkspaceTabByPath,
    activeWorkspaceTab: () => activeWorkspaceTab,
    editorViews: () => editorViews,
    workspaceViewPanes: () => workspaceViewPanes,
    diffEditorViews: () => diffEditorViews,
    workspacePaneTabs: () => workspacePaneTabs,
    workspacePaneTabsVersion: () => workspacePaneTabsVersion,
    remountMonacoEditor: () => remountMonacoEditor,
    scheduleWorkspaceLayout: () => scheduleWorkspaceLayout,
    layoutMonacoEditor: () => layoutMonacoEditor,
    activateWorkspaceTab: () => activateWorkspaceTab,
    openWorkspaceFile: () => openWorkspaceFile,
    // getter-injected (re-evaluated internally by useWorkspacePane via xxx()())
    layoutGitDiffEditor: () => layoutGitDiffEditor,
    disposeDiffEditorForPane: () => disposeDiffEditorForPane,
    disposeAllDiffEditors: () => disposeAllDiffEditors,
    loadDiffForPane: () => loadDiffForPane,
    // Getter-injected dependencies
    panels: () => panels,
    activePanelId: () => activePanelId,
    closePanel: () => closePanel,
    getPanelAgent: () => getPanelAgent,
    workspaceSessionPanelId: () => workspaceSessionPanelId,
    agentList: () => agentList,
    gitAgentId: () => gitAgentId,
    switchAgent: () => switchAgent,
    activeTerminalId: () => activeTerminalId,
    terminalSessions: () => terminalSessions,
    restoreTerminalSessions: () => restoreTerminalSessions,
    focusFirstIn: () => focusFirstIn,
    ...overrides,
  })
  return {
    api,
    fetchWithAuth,
    getGatewayAddress,
    getHttpProtocol,
    hasAuthToken,
    windowWidth,
    clamp,
    focusWindow,
    getWorkspaceTabByPath,
    activeWorkspaceTab,
    editorViews,
    workspaceViewPanes,
    diffEditorViews,
    workspacePaneTabs,
    workspacePaneTabsVersion,
    remountMonacoEditor,
    scheduleWorkspaceLayout,
    layoutMonacoEditor,
    activateWorkspaceTab,
    openWorkspaceFile,
    layoutGitDiffEditor,
    disposeDiffEditorForPane,
    disposeAllDiffEditors,
    loadDiffForPane,
    panels,
    activePanelId,
    closePanel,
    getPanelAgent,
    workspaceSessionPanelId,
    agentList,
    gitAgentId,
    switchAgent,
    activeTerminalId,
    terminalSessions,
    restoreTerminalSessions,
    focusFirstIn,
  }
}

// Count the number of leaves in the pane tree
function countLeaves(tree) {
  if (!tree) return 0
  if (tree.type === 'leaf') return 1
  return (tree.children || []).reduce((acc, c) => acc + countLeaves(c), 0)
}

beforeEach(() => {
  setupGlobals()
  localStorage.clear()
  usePluginsMock.mockClear()
  fetchPluginExtensionsMock.mockClear()
  loadExtensionComponentMock.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useWorkspacePane', () => {
  it('exposes the expected API (refs / computed / functions / plugin symbols)', () => {
    const { api } = makeHarness()
    // refs
    expect(typeof api.workspacePaneTree).toBe('object')
    expect(typeof api.activePaneId).toBe('object')
    expect(typeof api.workspaceSessions).toBe('object')
    expect(typeof api.workspaceTabs).toBe('object')
    expect(typeof api.workspaceMainView).toBe('object')
    expect(typeof api.workspacePaneCount).toBe('object')
    expect(typeof api.activePane).toBe('object')
    expect(typeof api.workspaceSidebarView).toBe('object')
    // Functions
    expect(typeof api.findWorkspacePaneById).toBe('function')
    expect(typeof api.activateWorkspacePane).toBe('function')
    expect(typeof api.splitWorkspacePane).toBe('function')
    expect(typeof api.closeWorkspacePane).toBe('function')
    expect(typeof api.collapseWorkspacePanes).toBe('function')
    expect(typeof api.restoreWorkspacePaneLayout).toBe('function')
    expect(typeof api.restoreWorkspacePaneContents).toBe('function')
    // Plugin symbols
    expect(typeof api.pluginExtensions).toBe('object')
    expect(typeof api.loadPluginExtensionsForUi).toBe('function')
    expect(typeof api.workspaceSidebarTitle).toBe('object')
  })

  it('initial state: single leaf file view, workspaceMainView derived', () => {
    const { api } = makeHarness()
    expect(api.workspacePaneCount.value).toBe(1)
    expect(api.workspacePaneTree.value.type).toBe('leaf')
    expect(api.workspacePaneTree.value.view).toBe('file')
    expect(api.activePaneId.value).toBe(api.workspacePaneTree.value.id)
    expect(api.workspaceMainView.value).toBe('file')
    expect(api.activePane.value.id).toBe(api.workspacePaneTree.value.id)
  })

  it('splitWorkspacePane: splits a single leaf into a row split, new leaf activated', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    const tree = api.workspacePaneTree.value
    expect(tree.type).toBe('split')
    expect(tree.direction).toBe('row')
    expect(tree.ratio).toBe(0.5)
    expect(countLeaves(tree)).toBe(2)
    // The new leaf is the active pane, view is empty
    expect(api.activePane.value.view).toBe('empty')
    expect(api.activePaneId.value).not.toBe(rootId)
    // The original leaf stays first
    expect(tree.children[0].id).toBe(rootId)
    // First split: the global tabs are frozen into the original pane
    expect(api.workspacePaneCount.value).toBe(2)
  })

  it('splitWorkspacePane: column direction', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'column')
    expect(api.workspacePaneTree.value.direction).toBe('column')
  })

  it('splitWorkspacePane: returns when windowWidth <= 768 (not supported on mobile)', () => {
    const { api, windowWidth } = makeHarness()
    windowWidth.value = 700
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    expect(api.workspacePaneCount.value).toBe(1)
  })

  it('closeWorkspacePane: closing a leaf returns to a single leaf', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    expect(api.workspacePaneCount.value).toBe(2)
    // Close the new leaf (active pane)
    const newId = api.activePaneId.value
    api.closeWorkspacePane(newId)
    expect(api.workspacePaneCount.value).toBe(1)
    expect(api.workspacePaneTree.value.type).toBe('leaf')
    expect(api.workspacePaneTree.value.id).toBe(rootId)
  })

  it('closeWorkspacePane: not allowed when only one leaf remains', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.closeWorkspacePane(rootId)
    expect(api.workspacePaneCount.value).toBe(1)
    expect(api.workspacePaneTree.value.id).toBe(rootId)
  })

  it('collapseWorkspacePanes: collapses all splits back to a single file leaf', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    api.splitWorkspacePane(api.activePaneId.value, 'column')
    expect(api.workspacePaneCount.value).toBe(3)
    api.collapseWorkspacePanes()
    expect(api.workspacePaneCount.value).toBe(1)
    expect(api.workspacePaneTree.value.type).toBe('leaf')
    expect(api.workspacePaneTree.value.view).toBe('file')
  })

  it('activateWorkspacePane: activates an existing pane, ignores nonexistent ones', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    const newId = api.activePaneId.value
    // Activate the original leaf
    api.activateWorkspacePane(rootId)
    expect(api.activePaneId.value).toBe(rootId)
    // Activate the new leaf
    api.activateWorkspacePane(newId)
    expect(api.activePaneId.value).toBe(newId)
    // Nonexistent panes are ignored
    api.activateWorkspacePane('pane-nonexistent')
    expect(api.activePaneId.value).toBe(newId)
  })

  it('moveActivePaneInDirection: returns false when unsplit', () => {
    const { api } = makeHarness()
    expect(api.moveActivePaneInDirection('right')).toBe(false)
  })

  it('moveActivePaneInDirection: with a row split, moves right to the other pane', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    // The new leaf is active (right side); move left back to root
    expect(api.moveActivePaneInDirection('left')).toBe(true)
    expect(api.activePaneId.value).toBe(rootId)
    // Move right back to the new leaf
    expect(api.moveActivePaneInDirection('right')).toBe(true)
    expect(api.activePaneId.value).not.toBe(rootId)
  })

  it('toggleMaximizeWorkspacePane: maximize/restore', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.toggleMaximizeWorkspacePane(rootId)
    expect(api.maximizedPaneId.value).toBe(rootId)
    api.toggleMaximizeWorkspacePane(rootId)
    expect(api.maximizedPaneId.value).toBeNull()
  })

  it('setActivePaneView: switches the active pane view', () => {
    const { api } = makeHarness()
    const ok = api.setActivePaneView('terminal')
    expect(ok).toBe(true)
    expect(api.activePane.value.view).toBe('terminal')
    // Switching to session requires a sessionPanelId
    expect(api.setActivePaneView('session')).toBe(false)
    expect(api.setActivePaneView('session', 'panel-1')).toBe(true)
    expect(api.activePane.value.view).toBe('session')
    expect(api.activePane.value.sessionPanelId).toBe('panel-1')
  })

  it('setActivePaneView: session panel dedup (only one pane per panel)', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    // Both panes host panel-1
    api.setActivePaneViewForPane(api.workspacePaneTree.value.children[0], 'session', 'panel-1')
    api.setActivePaneViewForPane(api.workspacePaneTree.value.children[1], 'session', 'panel-1')
    // When the second pane is set, the first one is cleared
    const first = api.workspacePaneTree.value.children[0]
    const second = api.workspacePaneTree.value.children[1]
    expect(first.view).toBe('empty')
    expect(second.view).toBe('session')
    expect(second.sessionPanelId).toBe('panel-1')
  })

  it('ensureAgentEditorPane: reuses the pane when the Agent already has a file pane', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.ensureAgentEditorPane('agent-1')
    // When unsplit and currently a file view, reuse it directly
    expect(api.activePane.value.view).toBe('file')
    expect(api.activePane.value.agentId).toBe('agent-1')
    expect(api.activePaneId.value).toBe(rootId)
  })

  it('ensureAgentEditorPane: splits out a new pane when the current view is not file', () => {
    const { api } = makeHarness()
    api.setActivePaneView('terminal')
    const paneId = api.ensureAgentEditorPane('agent-1')
    expect(paneId).toBeTruthy()
    expect(api.workspacePaneCount.value).toBe(2)
    const pane = api.findWorkspacePaneById(api.workspacePaneTree.value, paneId)
    expect(pane.view).toBe('file')
    expect(pane.agentId).toBe('agent-1')
  })

  it('ensurePaneForView: chat/terminal host singleton reuse', () => {
    const { api } = makeHarness()
    const id1 = api.ensurePaneForView('terminal')
    expect(id1).toBeTruthy()
    // Opening terminal again reuses the same pane instead of creating a new one
    const id2 = api.ensurePaneForView('terminal')
    expect(id2).toBe(id1)
    expect(api.workspacePaneCount.value).toBe(1)
  })

  it('getWorkspacePaneTitle: titles for each view', () => {
    const { api } = makeHarness()
    const pane = api.workspacePaneTree.value
    // file with no bound file -> empty area
    expect(api.getWorkspacePaneTitle(pane)).toBe('Empty area')
    pane.view = 'chat'
    expect(api.getWorkspacePaneTitle(pane)).toBe('Chat room')
    pane.view = 'terminal'
    expect(api.getWorkspacePaneTitle(pane)).toBe('Terminal')
    pane.view = 'empty'
    expect(api.getWorkspacePaneTitle(pane)).toBe('Empty area')
    // diff
    pane.view = 'diff'
    pane.diff = { filePath: '/home/user/a.js' }
    expect(api.getWorkspacePaneTitle(pane)).toBe('diff: a.js')
    // session: panel agent found
    pane.view = 'session'
    pane.sessionPanelId = 'panel-1'
    expect(api.getWorkspacePaneTitle(pane)).toBe('Session')
  })

  it('getWorkspacePaneStatus: file pane statuses', () => {
    const { api, getWorkspaceTabByPath } = makeHarness()
    const pane = api.workspacePaneTree.value
    pane.view = 'file'
    // No bound file -> ''
    expect(api.getWorkspacePaneStatus(pane)).toBe('')
    // Bound file but no tab -> ''
    api.workspaceSessions.value = [{ agent_id: 'agent-1', tabs: [], activeTabPath: '/a.js' }]
    api.activeWorkspaceSessionId.value = 'agent-1'
    getWorkspaceTabByPath.mockReturnValue(null)
    expect(api.getWorkspacePaneStatus(pane)).toBe('')
    // With a tab: dirty / saved / loading / error
    getWorkspaceTabByPath.mockReturnValue({ isDirty: true })
    expect(api.getWorkspacePaneStatus(pane)).toBe('Unsaved changes')
    getWorkspaceTabByPath.mockReturnValue({ isDirty: false })
    expect(api.getWorkspacePaneStatus(pane)).toBe('Saved')
    getWorkspaceTabByPath.mockReturnValue({ loading: true })
    expect(api.getWorkspacePaneStatus(pane)).toBe('Loading...')
    getWorkspaceTabByPath.mockReturnValue({ error: 'boom' })
    expect(api.getWorkspacePaneStatus(pane)).toBe('boom')
  })

  it('isPaneActive: determines whether a pane is active', () => {
    const { api } = makeHarness()
    const pane = api.workspacePaneTree.value
    expect(api.isPaneActive(pane)).toBe(true)
    const other = { id: 'pane-other', type: 'leaf', view: 'file' }
    expect(api.isPaneActive(other)).toBe(false)
  })

  it('persistWorkspacePaneLayout: does not write to localStorage when unsplit', () => {
    const { api } = makeHarness()
    api.persistWorkspacePaneLayout()
    expect(localStorage.getItem('haijunbot_workspace_pane_layout')).toBeNull()
  })

  it('persistWorkspacePaneLayout: writes and restores after splitting', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    api.persistWorkspacePaneLayout()
    const raw = localStorage.getItem('haijunbot_workspace_pane_layout')
    expect(raw).toBeTruthy()
    const payload = JSON.parse(raw)
    expect(payload.version).toBe(2)
    expect(payload.tree.type).toBe('split')
    // Restore into a new harness
    const { api: api2 } = makeHarness()
    api2.restoreWorkspacePaneLayout()
    expect(api2.workspacePaneCount.value).toBe(2)
    expect(api2.workspacePaneTree.value.type).toBe('split')
  })

  it('restoreWorkspacePaneLayout: dirty data falls back to the default single leaf', () => {
    localStorage.setItem('haijunbot_workspace_pane_layout', JSON.stringify({ version: 2, activePaneId: 'x', tree: { type: 'split', direction: 'row', ratio: 0.5, children: [{ type: 'leaf', id: 'pane-1', view: 'file' }, { type: 'leaf', id: 'pane-1', view: 'file' }] } }))
    const { api } = makeHarness()
    api.restoreWorkspacePaneLayout()
    // Duplicate leaf id -> invalid -> fall back to default
    expect(api.workspacePaneCount.value).toBe(1)
  })

  it('restoreWorkspacePaneLayout: invalid JSON falls back to default', () => {
    localStorage.setItem('haijunbot_workspace_pane_layout', '{invalid json')
    const { api } = makeHarness()
    api.restoreWorkspacePaneLayout()
    expect(api.workspacePaneCount.value).toBe(1)
  })

  it('restoreWorkspacePaneContents: does not restore when agentList is empty', async () => {
    const { api } = makeHarness()
    await api.restoreWorkspacePaneContents()
    // Not flagged, so it can be called again once agentList is ready
    expect(api.workspacePaneCount.value).toBe(1)
  })

  it('restoreWorkspacePaneContents: restores a session pane', async () => {
    const { api, agentList, panels, activePanelId, workspaceSessionPanelId, switchAgent } = makeHarness()
    // Build a session leaf tree with content
    const tree = {
      type: 'split',
      direction: 'row',
      ratio: 0.5,
      children: [
        { type: 'leaf', id: 'pane-1', view: 'file', sessionPanelId: null, agentId: null, content: null },
        { type: 'leaf', id: 'pane-2', view: 'session', sessionPanelId: null, agentId: 'agent-1', content: { agentId: 'agent-1' } },
      ],
    }
    api.workspacePaneTree.value = tree
    api.activePaneId.value = 'pane-2'
    agentList.value = [{ agent_id: 'agent-1', name: 'Agent 1' }]
    await api.restoreWorkspacePaneContents()
    const pane = api.findWorkspacePaneById(tree, 'pane-2')
    expect(pane.view).toBe('session')
    expect(pane.sessionPanelId).toBeTruthy()
    expect(panels.value.length).toBe(1)
    expect(activePanelId.value).toBe(pane.sessionPanelId)
    expect(workspaceSessionPanelId.value).toBe(pane.sessionPanelId)
    expect(switchAgent).toHaveBeenCalled()
    // content has been cleared
    expect(pane.content).toBeNull()
  })

  it('restoreWorkspacePaneContents: session Agent missing degrades to an empty pane', async () => {
    const { api, agentList } = makeHarness()
    const tree = {
      type: 'leaf',
      id: 'pane-1',
      view: 'session',
      sessionPanelId: null,
      agentId: 'agent-gone',
      content: { agentId: 'agent-gone' },
    }
    api.workspacePaneTree.value = tree
    agentList.value = [{ agent_id: 'agent-1', name: 'Agent 1' }]
    await api.restoreWorkspacePaneContents()
    expect(tree.view).toBe('empty')
    expect(tree.agentId).toBeNull()
  })

  it('restoreWorkspacePaneContents: restores a file pane's tabs', async () => {
    const { api, agentList, openWorkspaceFile, activateWorkspaceTab } = makeHarness()
    const tree = {
      type: 'leaf',
      id: 'pane-1',
      view: 'file',
      sessionPanelId: null,
      agentId: 'agent-1',
      content: { tabs: ['/a.js', '/b.js'], activePath: '/a.js', agentId: 'agent-1' },
    }
    api.workspacePaneTree.value = tree
    agentList.value = [{ agent_id: 'agent-1', name: 'Agent 1' }]
    await api.restoreWorkspacePaneContents()
    expect(openWorkspaceFile).toHaveBeenCalledTimes(2)
    expect(openWorkspaceFile).toHaveBeenCalledWith('/a.js', 'agent-1')
    expect(openWorkspaceFile).toHaveBeenCalledWith('/b.js', 'agent-1')
    expect(activateWorkspaceTab).toHaveBeenCalledWith('/a.js')
    expect(tree.content).toBeNull()
  })

  it('restoreWorkspacePaneContents: restores a diff pane; failure degrades to empty', async () => {
    const { api, agentList, loadDiffForPane, gitAgentId } = makeHarness()
    const tree = {
      type: 'leaf',
      id: 'pane-1',
      view: 'diff',
      sessionPanelId: null,
      agentId: 'agent-1',
      diff: null,
      content: { commitHash: 'abc123', filePath: '/a.js', agentId: 'agent-1' },
    }
    api.workspacePaneTree.value = tree
    agentList.value = [{ agent_id: 'agent-1', name: 'Agent 1' }]
    loadDiffForPane.mockImplementation(async () => {
      const pane = api.findWorkspacePaneById(api.workspacePaneTree.value, 'pane-1')
      pane.diff = { error: 'commit not found' }
    })
    await api.restoreWorkspacePaneContents()
    expect(loadDiffForPane).toHaveBeenCalledWith('pane-1', 'abc123', '/a.js')
    // diff fetch failure -> degrade to an empty pane
    expect(tree.view).toBe('empty')
    expect(tree.diff).toBeNull()
    expect(gitAgentId.value).toBeNull()
  })

  it('restoreWorkspacePaneContents: restores a terminal pane', async () => {
    const { api, agentList, terminalSessions, activeTerminalId } = makeHarness()
    const tree = {
      type: 'leaf',
      id: 'pane-1',
      view: 'terminal',
      sessionPanelId: null,
      agentId: null,
      content: { terminalId: 'term-1' },
    }
    api.workspacePaneTree.value = tree
    agentList.value = [{ agent_id: 'agent-1', name: 'Agent 1' }]
    terminalSessions.value = [{ terminal_id: 'term-1' }]
    await api.restoreWorkspacePaneContents()
    expect(activeTerminalId.value).toBe('term-1')
    expect(tree.view).toBe('terminal')
    expect(tree.content).toBeNull()
  })

  it('restoreWorkspacePaneContents: terminal session missing degrades to empty', async () => {
    const { api, agentList, terminalSessions } = makeHarness()
    const tree = {
      type: 'leaf',
      id: 'pane-1',
      view: 'terminal',
      sessionPanelId: null,
      agentId: null,
      content: { terminalId: 'term-gone' },
    }
    api.workspacePaneTree.value = tree
    agentList.value = [{ agent_id: 'agent-1', name: 'Agent 1' }]
    terminalSessions.value = []
    await api.restoreWorkspacePaneContents()
    expect(tree.view).toBe('empty')
  })

  it('setSplitWorkspaceContainerRef: registers/removes containers and triggers scheduleWorkspaceLayout', () => {
    const { api, scheduleWorkspaceLayout } = makeHarness()
    const el = { isConnected: true }
    api.setSplitWorkspaceContainerRef('pane-1', el)
    // Vue's deep-reactive proxied Map: get returns a proxied object, compare contents with toStrictEqual
    expect(api.splitWorkspaceContainerRefs.value.get('pane-1')).toStrictEqual(el)
    expect(scheduleWorkspaceLayout).toHaveBeenCalled()
    api.setSplitWorkspaceContainerRef('pane-1', null)
    expect(api.splitWorkspaceContainerRefs.value.has('pane-1')).toBe(false)
  })

  it('saveWorkspacePanelRect / workspacePanelRect persistence', () => {
    const { api } = makeHarness()
    api.workspacePanelRect.value = { top: 10, left: 20, width: 800, height: 600 }
    api.saveWorkspacePanelRect()
    const raw = localStorage.getItem('haijunbot_workspace_panel_rect')
    expect(raw).toBeTruthy()
    expect(JSON.parse(raw).width).toBe(800)
  })

  it('usePlugins is called and its return symbols are passed through', () => {
    const { api } = makeHarness()
    expect(usePluginsMock).toHaveBeenCalledTimes(1)
    // Passthrough symbols: pluginState is rebuilt inside makeHarness; validated through the usePluginsMock return value here
    const returned = usePluginsMock.mock.results[0].value
    expect(api.pluginExtensions).toBe(returned.pluginExtensions)
    expect(api.pluginAdminTabs).toBe(returned.pluginAdminTabs)
    expect(api.loadPluginExtensionsForUi).toBe(returned.loadPluginExtensionsForUi)
  })

  it('workspaceSidebarView defaults to agents and can be switched', () => {
    const { api } = makeHarness()
    expect(api.workspaceSidebarView.value).toBe('agents')
    api.workspaceSidebarView.value = 'git'
    expect(api.workspaceSidebarView.value).toBe('git')
  })

  it('workspaceMainView: returns file after splitting (compatible with legacy read sites)', () => {
    const { api } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    expect(api.workspaceMainView.value).toBe('file')
  })

  it('startWorkspacePaneResize: dragging adjusts the split ratio', () => {
    const { api, clamp } = makeHarness()
    const rootId = api.workspacePaneTree.value.id
    api.splitWorkspacePane(rootId, 'row')
    const splitNode = api.workspacePaneTree.value
    const event = {
      currentTarget: { parentElement: { getBoundingClientRect: () => ({ width: 1000, height: 600 }) } },
      clientX: 500,
      clientY: 0,
      preventDefault: vi.fn(),
      stopPropagation: vi.fn(),
    }
    api.startWorkspacePaneResize(event, splitNode)
    // Simulate mousemove: clientX 600 -> ratio 0.5 + 100/1000 = 0.6
    document.dispatchEvent(new MouseEvent('mousemove', { clientX: 600 }))
    expect(splitNode.ratio).toBeCloseTo(0.6, 5)
    // Simulate mouseup: end the drag, ratio stays the same
    document.dispatchEvent(new MouseEvent('mouseup'))
    // Further mousemove after the drag should not change the ratio (context already cleared)
    document.dispatchEvent(new MouseEvent('mousemove', { clientX: 800 }))
    expect(splitNode.ratio).toBeCloseTo(0.6, 5)
  })
})
