// useGitView unit tests
// Coverage: Git view state (commit history / branches / details / diff / range selection / patch download), target Agent resolution,
// diff pane multi-instance management (Monaco DiffEditor mock), commit context menu and copy, display utility functions.
// Mock monaco-editor (jsdom cannot load workers), in the same style as useTerminal.test.js mocking xterm.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useGitView } from './useGitView.js'

// ---- mock monaco-editor (vi.hoisted makes the factory referenceable, and the same instance is reachable inside tests) ----
const { monacoMock, MockDiffEditor, MockModel } = vi.hoisted(() => {
  class MockModel {
    constructor(text, language) {
      this.text = text
      this.language = language
      this._disposed = false
    }
    isDisposed() { return this._disposed }
    dispose() { this._disposed = true }
    getValue() { return this.text }
  }
  class MockDiffEditor {
    constructor(container, options) {
      this.container = container
      this.options = options
      this.models = null
      this._disposed = false
      this._layoutCount = 0
      this._updateOptions = []
      this._goToDiff = null
      this._focused = false
    }
    setModel(models) { this.models = models }
    updateOptions(opts) { this._updateOptions.push(opts) }
    layout() { this._layoutCount += 1 }
    dispose() { this._disposed = true }
    getContainerDomNode() { return this.container }
    goToDiff(target) { this._goToDiff = target }
    focus() { this._focused = true }
  }
  const monacoMock = {
    editor: {
      createDiffEditor: vi.fn(),
      createModel: vi.fn(),
    },
  }
  return { monacoMock, MockDiffEditor, MockModel }
})

vi.mock('monaco-editor/esm/vs/editor/editor.main.js', () => monacoMock)

// ---- mock global environment ----
function setupGlobals() {
  // requestAnimationFrame (jsdom provides one by default, but setTimeout keeps the test deterministic)
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0)
  // DOM APIs used for downloading patches
  // jsdom ships a createObjectURL stub but it reads blob._bytes and throws, so force it to a controllable mock
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  globalThis.URL.revokeObjectURL = vi.fn()
}

// Flush all microtasks (for async functions with multiple await levels)
async function flushPromises() {
  for (let i = 0; i < 20; i++) {
    await Promise.resolve()
  }
}

// Build the useGitView dependency-injection harness
function makeHarness(overrides = {}) {
  // —— direct dependencies (defined before the call site) ——
  const EDITOR_FONT_FAMILY = "'Consolas', monospace"
  const buildNodeHttpUrl = vi.fn((host, port, nodeId, path) => `http://${host}:${port}/api/node/${nodeId}/${path}`)
  const fetchWithAuth = vi.fn()
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const getLanguageExtension = vi.fn((ext) => ext || 'plaintext')
  const getLanguageFromFilename = vi.fn((path) => (path ? path.split('.').pop() : ''))
  const windowWidth = ref(1200)
  const activeWorkspaceSessionId = ref(null)
  const ensurePaneForView = vi.fn(() => null)
  const findWorkspacePaneById = vi.fn((node, paneId) => {
    if (!node) return null
    if (node.type === 'leaf') return node.id === paneId ? node : null
    for (const child of node.children || []) {
      const found = findWorkspacePaneById(child, paneId)
      if (found) return found
    }
    return null
  })
  const gitCustomDir = ref(null)
  const persistWorkspacePaneLayout = vi.fn()
  const resolveDiffContainer = vi.fn(() => null)
  const scheduleWorkspaceLayout = vi.fn()
  const showWorkspacePanel = ref(false)
  const workspacePaneTree = ref({ type: 'leaf', id: 'pane-main', view: 'file' })
  const workspaceSidebarView = ref('git')
  const diffContainerRefs = ref(new Map())
  const diffEditorViews = new Map()
  const openWorkspaceFile = vi.fn(async () => {})
  const activePane = ref(null)
  const getPanePanel = vi.fn(() => null)

  // —— getter-injected dependencies (defined after the call site) ——
  const effectiveGitAgentId = ref(null)
  const agentList = ref([])
  const showToast = vi.fn()
  const viewDiff = vi.fn()
  const copyTextToClipboard = vi.fn(async () => {})
  const getPanelAgent = vi.fn(() => null)
  const getCurrentAgentOrNull = vi.fn(() => null)

  const api = useGitView({
    EDITOR_FONT_FAMILY,
    buildNodeHttpUrl,
    fetchWithAuth,
    getGatewayAddress,
    getLanguageExtension,
    getLanguageFromFilename,
    windowWidth,
    activeWorkspaceSessionId,
    ensurePaneForView,
    findWorkspacePaneById,
    gitCustomDir,
    persistWorkspacePaneLayout,
    resolveDiffContainer,
    scheduleWorkspaceLayout,
    showWorkspacePanel,
    workspacePaneTree,
    workspaceSidebarView,
    diffContainerRefs,
    diffEditorViews,
    openWorkspaceFile,
    activePane,
    getPanePanel,
    // getter injection (useGitView re-evaluates with xxx())
    effectiveGitAgentId: () => effectiveGitAgentId,
    agentList: () => agentList,
    showToast: () => showToast,
    viewDiff: () => viewDiff,
    copyTextToClipboard: () => copyTextToClipboard,
    getPanelAgent: () => getPanelAgent,
    getCurrentAgentOrNull: () => getCurrentAgentOrNull,
    ...overrides,
  })

  return {
    api,
    EDITOR_FONT_FAMILY,
    buildNodeHttpUrl,
    fetchWithAuth,
    getGatewayAddress,
    getLanguageExtension,
    getLanguageFromFilename,
    windowWidth,
    activeWorkspaceSessionId,
    ensurePaneForView,
    findWorkspacePaneById,
    gitCustomDir,
    persistWorkspacePaneLayout,
    resolveDiffContainer,
    scheduleWorkspaceLayout,
    showWorkspacePanel,
    workspacePaneTree,
    workspaceSidebarView,
    diffContainerRefs,
    diffEditorViews,
    openWorkspaceFile,
    activePane,
    getPanePanel,
    effectiveGitAgentId,
    agentList,
    showToast,
    viewDiff,
    copyTextToClipboard,
    getPanelAgent,
    getCurrentAgentOrNull,
  }
}

// Build a valid Agent (matching the backend response shape)
function makeAgent(id, workingDir = '/home/user/project') {
  return { agent_id: id, name: `Agent ${id}`, node_id: 'node-1', working_dir: workingDir }
}

// Build a valid commit
function makeCommit(hash, subject = 'fix bug', refs = ['HEAD', 'main']) {
  return {
    hash,
    subject,
    refs,
    author: 'Alice',
    email: 'alice@example.com',
    date: '2024-01-01 12:00:00',
    body: '',
  }
}

beforeEach(() => {
  setupGlobals()
  monacoMock.editor.createDiffEditor.mockReset()
  monacoMock.editor.createModel.mockReset()
  monacoMock.editor.createDiffEditor.mockImplementation((container, options) => new MockDiffEditor(container, options))
  monacoMock.editor.createModel.mockImplementation((text, language) => new MockModel(text, language))
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useGitView', () => {
  it('exposes the expected interface', () => {
    const { api } = makeHarness()
    // refs / computed
    expect(typeof api.gitLog).toBe('object')
    expect(typeof api.gitLogLoading).toBe('object')
    expect(typeof api.gitLogError).toBe('object')
    expect(typeof api.gitLogHasMore).toBe('object')
    expect(typeof api.gitLogTotal).toBe('object')
    expect(typeof api.gitBranches).toBe('object')
    expect(typeof api.gitTags).toBe('object')
    expect(typeof api.gitCurrentBranch).toBe('object')
    expect(typeof api.gitSelectedCommit).toBe('object')
    expect(typeof api.gitRangeSelectMode).toBe('object')
    expect(typeof api.gitSelectedCommits).toBe('object')
    expect(typeof api.gitPatchLoading).toBe('object')
    expect(typeof api.gitCommitFiles).toBe('object')
    expect(typeof api.gitCommitDetailLoading).toBe('object')
    expect(typeof api.gitSelectedFile).toBe('object')
    expect(typeof api.gitDiffText).toBe('object')
    expect(typeof api.gitDiffLoading).toBe('object')
    expect(typeof api.gitDiffError).toBe('object')
    expect(typeof api.gitDiffTruncated).toBe('object')
    expect(typeof api.gitDiffSideBySide).toBe('object')
    expect(typeof api.gitDiffShowFull).toBe('object')
    expect(typeof api.pluginSidebarWorkingDir).toBe('object')
    expect(typeof api.pluginActiveAgentInfo).toBe('object')
    expect(typeof api.gitCommitContextMenu).toBe('object')
    expect(typeof api.gitCommitInfoModal).toBe('object')
    // constants
    expect(api.GIT_LOG_PAGE_SIZE).toBe(100)
    // functions
    for (const fn of [
      'isNarrowGitDiffViewport', 'getGitTargetAgent', 'getGitTargetNodeId', 'getGitWorkingDir',
      'callGitApi', 'fetchGitLog', 'fetchGitBranches', 'refreshGitView', 'toggleGitCommitDetail',
      'enterGitRangeSelect', 'exitGitRangeSelect', 'toggleGitRangeSelect', 'downloadGitPatch',
      'viewGitTargetDiff', 'onDiffTitleClick', 'onOpenDiffFileFromMessage', 'viewGitFileDiff',
      'ensureGitDiffFullText', 'layoutGitDiffEditor', 'disposeDiffEditorForPane',
      'disposeAllDiffEditors', 'ensureDiffEditorForPane', 'renderDiffForPane', 'loadDiffForPane',
      'togglePaneDiffSideBySide', 'togglePaneDiffShowFull', 'navigatePaneDiff', 'closePaneDiff',
      'scheduleDiffLayout', 'gitRefClass', 'gitFileStatus', 'formatGitRelativeTime', 'shortGitHash',
      'closeGitCommitContextMenu', 'openGitCommitContextMenu', 'copyGitCommit', 'copyGitCommitId',
      'formatGitCommitInfo', 'formatGitCommitTooltip', 'showGitCommitInfoModal',
    ]) {
      expect(typeof api[fn]).toBe('function')
    }
  })

  it('initial state: empty lists, not loading, no errors', () => {
    const { api } = makeHarness()
    expect(api.gitLog.value).toEqual([])
    expect(api.gitLogLoading.value).toBe(false)
    expect(api.gitLogError.value).toBe('')
    expect(api.gitLogHasMore.value).toBe(false)
    expect(api.gitLogTotal.value).toBe(null)
    expect(api.gitBranches.value).toEqual([])
    expect(api.gitTags.value).toEqual([])
    expect(api.gitCurrentBranch.value).toBe('')
    expect(api.gitSelectedCommit.value).toBe(null)
    expect(api.gitRangeSelectMode.value).toBe(false)
    expect(api.gitSelectedCommits.value).toEqual(new Set())
    expect(api.gitPatchLoading.value).toBe(false)
    expect(api.gitCommitFiles.value).toEqual([])
    expect(api.gitCommitDetailLoading.value).toBe(false)
    expect(api.gitSelectedFile.value).toBe(null)
    expect(api.gitDiffText.value).toBe('')
    expect(api.gitDiffLoading.value).toBe(false)
    expect(api.gitDiffError.value).toBe('')
    expect(api.gitDiffTruncated.value).toBe(false)
    expect(api.gitDiffShowFull.value).toBe(false)
    expect(api.gitCommitContextMenu.value).toEqual({ visible: false, x: 0, y: 0, commit: null })
    expect(api.gitCommitInfoModal.value).toBe(null)
  })

  describe('getGitTargetAgent / getGitTargetNodeId / getGitWorkingDir', () => {
    it('no Git target Agent returns null / empty', () => {
      const { api } = makeHarness()
      expect(api.getGitTargetAgent()).toBe(null)
      expect(api.getGitTargetNodeId()).toBe('')
      expect(api.getGitWorkingDir()).toBe('')
    })
    it('finds the target Agent by effectiveGitAgentId', () => {
      const { api, effectiveGitAgentId, agentList } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a'), makeAgent('a2', '/work/b')]
      effectiveGitAgentId.value = 'a2'
      expect(api.getGitTargetAgent().agent_id).toBe('a2')
      expect(api.getGitTargetNodeId()).toBe('node-1')
      expect(api.getGitWorkingDir()).toBe('/work/b')
    })
    it('falls back to empty when the Agent is not found', () => {
      const { api, effectiveGitAgentId, agentList } = makeHarness()
      agentList.value = [makeAgent('a1')]
      effectiveGitAgentId.value = 'nonexistent'
      expect(api.getGitTargetAgent()).toBe(null)
      expect(api.getGitTargetNodeId()).toBe('')
      expect(api.getGitWorkingDir()).toBe('')
    })
    it('a custom Git directory takes priority over the Agent', () => {
      const { api, effectiveGitAgentId, agentList, gitCustomDir } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      gitCustomDir.value = { nodeId: 'custom-node', path: '/custom/path' }
      expect(api.getGitTargetNodeId()).toBe('custom-node')
      expect(api.getGitWorkingDir()).toBe('/custom/path')
    })
  })

  describe('pluginSidebarWorkingDir / pluginActiveAgentInfo', () => {
    it('pluginSidebarWorkingDir follows the working directory', () => {
      const { api, effectiveGitAgentId, agentList } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      expect(api.pluginSidebarWorkingDir.value).toBe('/work/a')
    })
    it('pluginActiveAgentInfo returns Agent info (null when no Agent)', () => {
      const { api, effectiveGitAgentId, agentList } = makeHarness()
      expect(api.pluginActiveAgentInfo.value).toBe(null)
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      expect(api.pluginActiveAgentInfo.value).toEqual({
        agentId: 'a1',
        agentName: 'Agent a1',
        workingDir: '/work/a',
      })
    })
  })

  describe('isNarrowGitDiffViewport', () => {
    it('window width <= 768 is a narrow viewport', () => {
      const { api, windowWidth } = makeHarness()
      windowWidth.value = 768
      expect(api.isNarrowGitDiffViewport()).toBe(true)
      windowWidth.value = 769
      expect(api.isNarrowGitDiffViewport()).toBe(false)
    })
  })

  describe('callGitApi', () => {
    it('builds the request and parses a successful response', async () => {
      const { api, fetchWithAuth, buildNodeHttpUrl, getGatewayAddress, effectiveGitAgentId, agentList } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { commits: [] } }),
      })
      const data = await api.callGitApi('git/log', { path: '/work/a' })
      expect(getGatewayAddress).toHaveBeenCalled()
      expect(buildNodeHttpUrl).toHaveBeenCalledWith('127.0.0.1', '8000', 'node-1', 'git/log')
      const [url, opts] = fetchWithAuth.mock.calls[0]
      expect(url).toBe('http://127.0.0.1:8000/api/node/node-1/git/log')
      expect(opts.method).toBe('POST')
      expect(JSON.parse(opts.body)).toEqual({ path: '/work/a', node_id: 'node-1' })
      expect(data).toEqual({ commits: [] })
    })
    it('falls back to master when there is no target node', async () => {
      const { api, fetchWithAuth } = makeHarness()
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: {} }),
      })
      await api.callGitApi('git/log', {})
      const [url] = fetchWithAuth.mock.calls[0]
      expect(url).toContain('/master/git/log')
    })
    it('throws on a failed response', async () => {
      const { api, fetchWithAuth } = makeHarness()
      fetchWithAuth.mockResolvedValue({
        ok: false,
        json: async () => ({ success: false, error: { message: 'Insufficient permissions' } }),
      })
      await expect(api.callGitApi('git/log', {})).rejects.toThrow('Insufficient permissions')
    })
    it('uses the generic message when no message is present', async () => {
      const { api, fetchWithAuth } = makeHarness()
      fetchWithAuth.mockResolvedValue({
        ok: false,
        json: async () => ({ success: false, error: {} }),
      })
      await expect(api.callGitApi('git/log', {})).rejects.toThrow('Git request failed')
    })
  })

  describe('fetchGitLog', () => {
    it('sets the error and clears the list when there is no working directory', async () => {
      const { api } = makeHarness()
      await api.fetchGitLog()
      expect(api.gitLogError.value).toBe('The current Agent has no working directory')
      expect(api.gitLog.value).toEqual([])
      expect(api.gitLogTotal.value).toBe(null)
    })
    it('successfully fetches the commit list (non-append)', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { commits: [makeCommit('abc123')], has_more: true, total: 150 } }),
      })
      await api.fetchGitLog()
      expect(api.gitLog.value).toEqual([makeCommit('abc123')])
      expect(api.gitLogHasMore.value).toBe(true)
      expect(api.gitLogTotal.value).toBe(150)
      expect(api.gitLogLoading.value).toBe(false)
      expect(api.gitLogError.value).toBe('')
      // verify the request body: limit=100, skip=0
      const [, opts] = fetchWithAuth.mock.calls[0]
      expect(JSON.parse(opts.body)).toMatchObject({ path: '/work/a', limit: 100, skip: 0 })
    })
    it('append mode: skip = current length and merges', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.gitLog.value = [makeCommit('old1')]
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { commits: [makeCommit('new1')], has_more: false } }),
      })
      await api.fetchGitLog(true)
      const [, opts] = fetchWithAuth.mock.calls[0]
      expect(JSON.parse(opts.body)).toMatchObject({ skip: 1 })
      expect(api.gitLog.value).toEqual([makeCommit('old1'), makeCommit('new1')])
      expect(api.gitLogHasMore.value).toBe(false)
    })
    it('records the error and clears on failure (non-append)', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth.mockResolvedValue({
        ok: false,
        json: async () => ({ success: false, error: { message: 'Network error' } }),
      })
      await api.fetchGitLog()
      expect(api.gitLogError.value).toBe('Network error')
      expect(api.gitLog.value).toEqual([])
      expect(api.gitLogTotal.value).toBe(null)
      expect(api.gitLogLoading.value).toBe(false)
    })
    it('keeps the existing list on failure (append mode)', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.gitLog.value = [makeCommit('old1')]
      fetchWithAuth.mockRejectedValue(new Error('Timeout'))
      await api.fetchGitLog(true)
      expect(api.gitLogError.value).toBe('Timeout')
      expect(api.gitLog.value).toEqual([makeCommit('old1')])
    })
  })

  describe('fetchGitBranches', () => {
    it('successfully fetches branches/tags/current branch', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { branches: ['main', 'dev'], tags: ['v1.0'], current: 'dev' } }),
      })
      await api.fetchGitBranches()
      expect(api.gitBranches.value).toEqual(['main', 'dev'])
      expect(api.gitTags.value).toEqual(['v1.0'])
      expect(api.gitCurrentBranch.value).toBe('dev')
    })
    it('returns silently when there is no working directory', async () => {
      const { api, fetchWithAuth } = makeHarness()
      await api.fetchGitBranches()
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('clears branch info on failure (without throwing)', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.gitBranches.value = ['stale']
      fetchWithAuth.mockRejectedValue(new Error('boom'))
      await api.fetchGitBranches()
      expect(api.gitBranches.value).toEqual([])
      expect(api.gitTags.value).toEqual([])
      expect(api.gitCurrentBranch.value).toBe('')
    })
  })

  describe('refreshGitView', () => {
    it('resets detail state and fetches history and branches together', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.gitSelectedCommit.value = 'abc'
      api.gitCommitFiles.value = [{ file_path: 'x' }]
      api.gitSelectedFile.value = 'x'
      api.gitDiffText.value = 'old'
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { commits: [], has_more: false } }),
      })
      await api.refreshGitView()
      expect(api.gitSelectedCommit.value).toBe(null)
      expect(api.gitCommitFiles.value).toEqual([])
      expect(api.gitSelectedFile.value).toBe(null)
      expect(api.gitDiffText.value).toBe('')
      expect(api.gitDiffError.value).toBe('')
      expect(fetchWithAuth).toHaveBeenCalledTimes(2) // git/log + git/branches
    })
  })

  describe('toggleGitCommitDetail', () => {
    it('collapses when the same commit is clicked again', async () => {
      const { api, effectiveGitAgentId, agentList } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.gitSelectedCommit.value = 'abc'
      api.gitCommitFiles.value = [{ file_path: 'x' }]
      api.gitSelectedFile.value = 'x'
      api.gitDiffText.value = 'old'
      await api.toggleGitCommitDetail(makeCommit('abc'))
      expect(api.gitSelectedCommit.value).toBe(null)
      expect(api.gitCommitFiles.value).toEqual([])
      expect(api.gitSelectedFile.value).toBe(null)
      expect(api.gitDiffText.value).toBe('')
    })
    it('expands commit details: fetches the changed-files list', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { files: [{ file_path: 'a.py', additions: 1, deletions: 0 }] } }),
      })
      await api.toggleGitCommitDetail(makeCommit('abc'))
      expect(api.gitSelectedCommit.value).toBe('abc')
      expect(api.gitCommitFiles.value).toEqual([{ file_path: 'a.py', additions: 1, deletions: 0 }])
      expect(api.gitCommitDetailLoading.value).toBe(false)
    })
    it('expands without requesting when there is no working directory', async () => {
      const { api, fetchWithAuth } = makeHarness()
      await api.toggleGitCommitDetail(makeCommit('abc'))
      expect(api.gitSelectedCommit.value).toBe('abc')
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('records the error when fetching fails', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth.mockRejectedValue(new Error('detail fail'))
      await api.toggleGitCommitDetail(makeCommit('abc'))
      expect(api.gitDiffError.value).toBe('detail fail')
      expect(api.gitCommitDetailLoading.value).toBe(false)
    })
  })

  describe('range selection enter/exit/toggle', () => {
    it('enterGitRangeSelect clears the selection and exits details', () => {
      const { api } = makeHarness()
      api.gitRangeSelectMode.value = false
      api.gitSelectedCommit.value = 'abc'
      api.gitCommitFiles.value = [{ file_path: 'x' }]
      api.gitSelectedFile.value = 'x'
      api.gitDiffText.value = 'old'
      api.enterGitRangeSelect()
      expect(api.gitRangeSelectMode.value).toBe(true)
      expect(api.gitSelectedCommits.value).toEqual(new Set())
      expect(api.gitSelectedCommit.value).toBe(null)
      expect(api.gitCommitFiles.value).toEqual([])
      expect(api.gitSelectedFile.value).toBe(null)
      expect(api.gitDiffText.value).toBe('')
    })
    it('exitGitRangeSelect clears the selection', () => {
      const { api } = makeHarness()
      api.gitRangeSelectMode.value = true
      api.gitSelectedCommits.value = new Set(['abc'])
      api.exitGitRangeSelect()
      expect(api.gitRangeSelectMode.value).toBe(false)
      expect(api.gitSelectedCommits.value).toEqual(new Set())
    })
    it('toggleGitRangeSelect toggles selection and triggers reactivity', () => {
      const { api } = makeHarness()
      api.toggleGitRangeSelect(makeCommit('abc'))
      expect(api.gitSelectedCommits.value.has('abc')).toBe(true)
      api.toggleGitRangeSelect(makeCommit('abc'))
      expect(api.gitSelectedCommits.value.has('abc')).toBe(false)
      api.toggleGitRangeSelect(makeCommit('def'))
      expect(api.gitSelectedCommits.value).toEqual(new Set(['def']))
    })
  })

  describe('downloadGitPatch', () => {
    it('returns directly when there is no working directory', async () => {
      const { api, fetchWithAuth } = makeHarness()
      await api.downloadGitPatch()
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('shows a toast when no commit is selected', async () => {
      const { api, effectiveGitAgentId, agentList, showToast } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      await api.downloadGitPatch()
      expect(showToast).toHaveBeenCalledWith('Please select at least one commit first', 'error')
    })
    it('downloads a single commit as .patch', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth, showToast } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.gitSelectedCommits.value = new Set(['abc'])
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { format: 'patch', filename: 'abc.patch', content: 'diff --git a/x b/x' } }),
      })
      await api.downloadGitPatch()
      const [, opts] = fetchWithAuth.mock.calls[0]
      expect(JSON.parse(opts.body)).toMatchObject({ path: '/work/a', commits: ['abc'] })
      expect(showToast).toHaveBeenCalledWith('Downloaded abc.patch', 'success')
      expect(api.gitPatchLoading.value).toBe(false)
    })
    it('downloads multiple commits as tar.gz (base64 decode)', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth, showToast } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.gitSelectedCommits.value = new Set(['abc', 'def'])
      const base64 = btoa('binary-data')
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { format: 'tar.gz', filename: 'patch.tar.gz', content_base64: base64 } }),
      })
      await api.downloadGitPatch()
      expect(showToast).toHaveBeenCalledWith('Downloaded patch.tar.gz', 'success')
      expect(api.gitPatchLoading.value).toBe(false)
    })
    it('toasts an error when the data is invalid', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth, showToast } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.gitSelectedCommits.value = new Set(['abc'])
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: {} }),
      })
      await api.downloadGitPatch()
      expect(showToast).toHaveBeenCalledWith('Invalid patch data', 'error')
    })
  })

  describe('viewGitTargetDiff', () => {
    it('toasts when there is no target Agent', () => {
      const { api, showToast } = makeHarness()
      api.viewGitTargetDiff()
      expect(showToast).toHaveBeenCalledWith('Please select a Git target Agent first', 'error')
    })
    it('calls viewDiff with a target Agent present (getter re-evaluated)', () => {
      const { api, effectiveGitAgentId, agentList, viewDiff } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      api.viewGitTargetDiff()
      expect(viewDiff).toHaveBeenCalledWith(makeAgent('a1', '/work/a'))
    })
  })

  describe('onDiffTitleClick', () => {
    it('returns directly when there is no filePath', async () => {
      const { api, openWorkspaceFile } = makeHarness()
      await api.onDiffTitleClick({}, { diff: {} })
      expect(openWorkspaceFile).not.toHaveBeenCalled()
    })
    it('joins the relative path with the working directory and opens it', async () => {
      const { api, effectiveGitAgentId, agentList, openWorkspaceFile } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      const event = { preventDefault: vi.fn(), stopPropagation: vi.fn() }
      await api.onDiffTitleClick(event, { diff: { filePath: 'src/x.py' } })
      expect(event.preventDefault).toHaveBeenCalled()
      expect(event.stopPropagation).toHaveBeenCalled()
      expect(openWorkspaceFile).toHaveBeenCalledWith('/work/a/src/x.py', 'a1')
    })
    it('opens an absolute path directly', async () => {
      const { api, effectiveGitAgentId, agentList, openWorkspaceFile } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      await api.onDiffTitleClick({ preventDefault: vi.fn(), stopPropagation: vi.fn() }, { diff: { filePath: '/abs/x.py' } })
      expect(openWorkspaceFile).toHaveBeenCalledWith('/abs/x.py', 'a1')
    })
    it('returns directly when there is no working directory', async () => {
      const { api, openWorkspaceFile } = makeHarness()
      await api.onDiffTitleClick({ preventDefault: vi.fn(), stopPropagation: vi.fn() }, { diff: { filePath: 'src/x.py' } })
      expect(openWorkspaceFile).not.toHaveBeenCalled()
    })
  })

  describe('onOpenDiffFileFromMessage', () => {
    it('returns directly when there is no filePath', async () => {
      const { api, openWorkspaceFile } = makeHarness()
      await api.onOpenDiffFileFromMessage('')
      expect(openWorkspaceFile).not.toHaveBeenCalled()
    })
    it('joins the session Agent working directory and opens it', async () => {
      const { api, activePane, getPanePanel, getPanelAgent, openWorkspaceFile } = makeHarness()
      const pane = { view: 'session', sessionPanelId: 'panel-1' }
      activePane.value = pane
      getPanePanel.mockReturnValue({ id: 'panel-1' })
      getPanelAgent.mockReturnValue(makeAgent('a1', '/work/a'))
      await api.onOpenDiffFileFromMessage('src/x.py')
      expect(openWorkspaceFile).toHaveBeenCalledWith('/work/a/src/x.py', 'a1')
    })
    it('falls back to the Git target working directory when there is no session Agent', async () => {
      const { api, effectiveGitAgentId, agentList, openWorkspaceFile } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      await api.onOpenDiffFileFromMessage('src/x.py')
      expect(openWorkspaceFile).toHaveBeenCalledWith('/work/a/src/x.py', 'a1')
    })
    it('opens an absolute path directly', async () => {
      const { api, openWorkspaceFile } = makeHarness()
      await api.onOpenDiffFileFromMessage('/abs/x.py')
      expect(openWorkspaceFile).toHaveBeenCalledWith('/abs/x.py', null)
    })
  })

  describe('viewGitFileDiff', () => {
    it('returns directly when there is no working directory', async () => {
      const { api, fetchWithAuth } = makeHarness()
      await api.viewGitFileDiff('abc', 'x.py')
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('reuses and loads an existing diff pane (ensurePaneForView returns paneId)', async () => {
      const { api, effectiveGitAgentId, agentList, ensurePaneForView, fetchWithAuth, workspacePaneTree, resolveDiffContainer } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: null }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      ensurePaneForView.mockReturnValue('pane-diff')
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { diff: '--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n', truncated: false } }),
      })
      await api.viewGitFileDiff('abc', 'x.py')
      expect(api.gitSelectedFile.value).toBe('x.py')
      expect(ensurePaneForView).toHaveBeenCalledWith('diff')
      expect(diffPane.view).toBe('diff')
      expect(diffPane.diff).toBeTruthy()
      expect(diffPane.diff.commitHash).toBe('abc')
      expect(diffPane.diff.filePath).toBe('x.py')
      expect(diffPane.diff.loading).toBe(false)
      expect(diffPane.diff.error).toBe('')
      expect(monacoMock.editor.createDiffEditor).toHaveBeenCalled()
    })
    it('takes the leaf path when unsplit and created in place', async () => {
      const { api, effectiveGitAgentId, agentList, ensurePaneForView, fetchWithAuth, workspacePaneTree, resolveDiffContainer } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      const leaf = { type: 'leaf', id: 'pane-main', view: 'file' }
      workspacePaneTree.value = leaf
      ensurePaneForView.mockReturnValue(null)
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { diff: '--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n', truncated: false } }),
      })
      await api.viewGitFileDiff('abc', 'x.py')
      expect(leaf.view).toBe('diff')
      expect(leaf.diff).toBeTruthy()
      expect(leaf.diff.commitHash).toBe('abc')
      expect(monacoMock.editor.createDiffEditor).toHaveBeenCalled()
    })
  })

  describe('diff pane multi-instance management', () => {
    function makeSplitTree() {
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: null }
      const tree = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      return { tree, diffPane }
    }

    it('ensureDiffEditorForPane creates and caches a DiffEditor', () => {
      const { api, resolveDiffContainer, diffEditorViews } = makeHarness()
      const container = { isConnected: true }
      resolveDiffContainer.mockReturnValue(container)
      const entry = api.ensureDiffEditorForPane('pane-x')
      expect(entry).toBeTruthy()
      expect(entry.editor).toBeTruthy()
      expect(monacoMock.editor.createDiffEditor).toHaveBeenCalledWith(container, expect.objectContaining({ theme: 'blueDark', readOnly: true }))
      expect(diffEditorViews.get('pane-x')).toBe(entry)
      // calling again returns the same instance
      expect(api.ensureDiffEditorForPane('pane-x')).toBe(entry)
    })
    it('destroys and rebuilds when the container is replaced', () => {
      const { api, resolveDiffContainer, diffEditorViews } = makeHarness()
      const container1 = { isConnected: true }
      const container2 = { isConnected: true }
      resolveDiffContainer.mockReturnValueOnce(container1).mockReturnValueOnce(container2)
      const entry1 = api.ensureDiffEditorForPane('pane-x')
      const entry2 = api.ensureDiffEditorForPane('pane-x')
      expect(entry1.editor._disposed).toBe(true)
      expect(entry2.editor).not.toBe(entry1.editor)
    })
    it('disposeDiffEditorForPane releases the instance and models', () => {
      const { api, resolveDiffContainer, diffEditorViews } = makeHarness()
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      const entry = api.ensureDiffEditorForPane('pane-x')
      const model = new MockModel('a', 'py')
      entry.originalModel = model
      entry.modifiedModel = new MockModel('b', 'py')
      api.disposeDiffEditorForPane('pane-x')
      expect(model.isDisposed()).toBe(true)
      expect(entry.editor._disposed).toBe(true)
      expect(diffEditorViews.has('pane-x')).toBe(false)
    })
    it('disposeAllDiffEditors releases all instances and clears containers', () => {
      const { api, resolveDiffContainer, diffEditorViews, diffContainerRefs } = makeHarness()
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      api.ensureDiffEditorForPane('pane-1')
      api.ensureDiffEditorForPane('pane-2')
      diffContainerRefs.value.set('pane-1', { isConnected: true })
      diffContainerRefs.value.set('pane-2', { isConnected: true })
      api.disposeAllDiffEditors()
      expect(diffEditorViews.size).toBe(0)
      expect(diffContainerRefs.value.size).toBe(0)
    })
    it('renderDiffForPane renders the model (polls then gives up without a container)', async () => {
      const { api, resolveDiffContainer } = makeHarness()
      resolveDiffContainer.mockReturnValue(null)
      await api.renderDiffForPane('pane-x')
      expect(monacoMock.editor.createModel).not.toHaveBeenCalled()
    })
    it('renderDiffForPane restores both sides with parseUnifiedDiff', async () => {
      const { api, resolveDiffContainer, workspacePaneTree, getLanguageExtension, getLanguageFromFilename, diffEditorViews } = makeHarness()
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: { commitHash: 'abc', filePath: 'x.py', diffText: '--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n', sideBySide: true, showFull: false } }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      const container = { isConnected: true }
      resolveDiffContainer.mockReturnValue(container)
      await api.renderDiffForPane('pane-diff')
      expect(monacoMock.editor.createModel).toHaveBeenCalled()
      const entry = diffEditorViews.get('pane-diff')
      expect(entry.originalModel.getValue()).toBe('old')
      expect(entry.modifiedModel.getValue()).toBe('new')
      expect(entry.editor.models).toEqual({ original: entry.originalModel, modified: entry.modifiedModel })
      expect(entry.editor._updateOptions.some(o => 'renderSideBySide' in o)).toBe(true)
      expect(entry.editor._layoutCount).toBeGreaterThan(0)
    })
    it('renderDiffForPane records the error on failure', async () => {
      const { api, resolveDiffContainer, workspacePaneTree } = makeHarness()
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: { commitHash: 'abc', filePath: 'x.py', diffText: 'x', sideBySide: true, showFull: false } }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      monacoMock.editor.createModel.mockImplementation(() => { throw new Error('model fail') })
      await api.renderDiffForPane('pane-diff')
      expect(diffPane.diff.error).toContain('Failed to render diff')
    })
    it('loadDiffForPane fetches the diff and renders it', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth, workspacePaneTree, resolveDiffContainer } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: null }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { diff: '--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n', truncated: false } }),
      })
      await api.loadDiffForPane('pane-diff', 'abc', 'x.py')
      expect(diffPane.diff).toBeTruthy()
      expect(diffPane.diff.commitHash).toBe('abc')
      expect(diffPane.diff.loading).toBe(false)
      expect(diffPane.diff.error).toBe('')
      expect(diffPane.diff.diffText).toContain('@@')
      expect(monacoMock.editor.createDiffEditor).toHaveBeenCalled()
    })
    it('loadDiffForPane records the error on failure', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth, workspacePaneTree } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: null }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      fetchWithAuth.mockRejectedValue(new Error('diff fail'))
      await api.loadDiffForPane('pane-diff', 'abc', 'x.py')
      expect(diffPane.diff.loading).toBe(false)
      expect(diffPane.diff.error).toBe('diff fail')
    })
    it('togglePaneDiffSideBySide toggles and updates the editor', () => {
      const { api, workspacePaneTree, resolveDiffContainer, diffEditorViews } = makeHarness()
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: { commitHash: 'abc', filePath: 'x.py', sideBySide: true, showFull: false } }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      const entry = api.ensureDiffEditorForPane('pane-diff')
      api.togglePaneDiffSideBySide('pane-diff')
      expect(diffPane.diff.sideBySide).toBe(false)
      expect(entry.editor._updateOptions.some(o => o.renderSideBySide === false)).toBe(true)
    })
    it('navigatePaneDiff calls goToDiff', () => {
      const { api, resolveDiffContainer, diffEditorViews } = makeHarness()
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      const entry = api.ensureDiffEditorForPane('pane-diff')
      api.navigatePaneDiff('pane-diff', 'prev')
      expect(entry.editor._goToDiff).toBe('previous')
      api.navigatePaneDiff('pane-diff', 'next')
      expect(entry.editor._goToDiff).toBe('next')
    })
    it('closePaneDiff releases the instance and returns to empty', async () => {
      const { api, workspacePaneTree, resolveDiffContainer, diffEditorViews, persistWorkspacePaneLayout, scheduleWorkspaceLayout } = makeHarness()
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: { commitHash: 'abc', filePath: 'x.py' } }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      api.ensureDiffEditorForPane('pane-diff')
      api.closePaneDiff('pane-diff')
      expect(diffPane.view).toBe('empty')
      expect(diffPane.diff).toBe(null)
      expect(diffEditorViews.has('pane-diff')).toBe(false)
      expect(persistWorkspacePaneLayout).toHaveBeenCalled()
      await nextTick()
      expect(scheduleWorkspaceLayout).toHaveBeenCalled()
    })
    it('layoutGitDiffEditor only layouts connected instances', () => {
      const { api, resolveDiffContainer, diffEditorViews } = makeHarness()
      const connected = { isConnected: true }
      const disconnected = { isConnected: false }
      resolveDiffContainer.mockImplementation((paneId) => (paneId === 'c' ? connected : disconnected))
      const entryC = api.ensureDiffEditorForPane('c')
      const entryD = api.ensureDiffEditorForPane('d')
      api.layoutGitDiffEditor()
      expect(entryC.editor._layoutCount).toBeGreaterThan(0)
      expect(entryD.editor._layoutCount).toBe(0)
    })
    it('scheduleDiffLayout coalesces layout with rAF', async () => {
      const { api, resolveDiffContainer, diffEditorViews } = makeHarness()
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      const entry = api.ensureDiffEditorForPane('c')
      api.scheduleDiffLayout()
      api.scheduleDiffLayout() // coalesced: the second call does not schedule again
      await new Promise((r) => setTimeout(r, 5))
      expect(entry.editor._layoutCount).toBeGreaterThan(0)
    })
  })

  describe('ensureGitDiffFullText', () => {
    it('returns null when there is no working directory', async () => {
      const { api, fetchWithAuth } = makeHarness()
      const result = await api.ensureGitDiffFullText('abc', 'x.py')
      expect(result).toBe(null)
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('fetches both sides of the full text and caches', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { content: 'full text', truncated: false } }),
      })
      const result = await api.ensureGitDiffFullText('abc', 'x.py')
      expect(result).toEqual({ oldText: 'full text', newText: 'full text', truncated: false })
      // the second call hits the cache, no new request
      fetchWithAuth.mockClear()
      const result2 = await api.ensureGitDiffFullText('abc', 'x.py')
      expect(result2).toEqual(result)
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('treats a failed parent-version request as an empty file', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth
        .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: { content: 'new', truncated: false } }) })
        .mockRejectedValueOnce(new Error('NOT_FOUND'))
      const result = await api.ensureGitDiffFullText('abc', 'x.py')
      expect(result).toEqual({ oldText: '', newText: 'new', truncated: false })
    })
  })

  describe('togglePaneDiffShowFull', () => {
    it('switches to full text: fetches the full text and updates the editor', async () => {
      const { api, effectiveGitAgentId, agentList, fetchWithAuth, workspacePaneTree, resolveDiffContainer, diffEditorViews } = makeHarness()
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: { commitHash: 'abc', filePath: 'x.py', diffText: '--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n', sideBySide: true, showFull: false, truncated: false } }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      const entry = api.ensureDiffEditorForPane('pane-diff')
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { content: 'FULL', truncated: false } }),
      })
      await api.togglePaneDiffShowFull('pane-diff')
      expect(diffPane.diff.showFull).toBe(true)
      expect(diffPane.diff.loading).toBe(false)
      expect(entry.oldText).toBe('FULL')
      expect(entry.newText).toBe('FULL')
      expect(monacoMock.editor.createModel).toHaveBeenCalled()
    })
    it('switches back to context only: clears the full-text cache variables', async () => {
      const { api, workspacePaneTree, resolveDiffContainer, diffEditorViews } = makeHarness()
      const diffPane = { type: 'leaf', id: 'pane-diff', view: 'diff', diff: { commitHash: 'abc', filePath: 'x.py', diffText: '--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n', sideBySide: true, showFull: true, truncated: false } }
      workspacePaneTree.value = { type: 'split', direction: 'row', ratio: 0.5, children: [
        { type: 'leaf', id: 'pane-main', view: 'file' },
        diffPane,
      ] }
      resolveDiffContainer.mockReturnValue({ isConnected: true })
      const entry = api.ensureDiffEditorForPane('pane-diff')
      entry.oldText = 'OLD'
      entry.newText = 'NEW'
      await api.togglePaneDiffShowFull('pane-diff')
      expect(diffPane.diff.showFull).toBe(false)
      expect(entry.oldText).toBe('')
      expect(entry.newText).toBe('')
    })
  })

  describe('display utility functions', () => {
    it('gitRefClass distinguishes HEAD/tag/branch', () => {
      const { api } = makeHarness()
      expect(api.gitRefClass('HEAD -> main')).toBe('git-ref-head')
      expect(api.gitRefClass('tag: v1.0')).toBe('git-ref-tag')
      expect(api.gitRefClass('main')).toBe('git-ref-branch')
    })
    it('gitFileStatus is inferred from added/deleted line counts', () => {
      const { api } = makeHarness()
      expect(api.gitFileStatus({ additions: 1, deletions: 0 })).toBe('A')
      expect(api.gitFileStatus({ additions: 0, deletions: 1 })).toBe('D')
      expect(api.gitFileStatus({ additions: 1, deletions: 1 })).toBe('M')
      expect(api.gitFileStatus({})).toBe('M')
    })
    it('formatGitRelativeTime covers all buckets', () => {
      const { api } = makeHarness()
      const now = Date.now()
      expect(api.formatGitRelativeTime(new Date(now - 30 * 1000).toISOString())).toBe('just now')
      expect(api.formatGitRelativeTime(new Date(now - 5 * 60 * 1000).toISOString())).toBe('5 minutes ago')
      expect(api.formatGitRelativeTime(new Date(now - 3 * 3600 * 1000).toISOString())).toBe('3 hours ago')
      expect(api.formatGitRelativeTime(new Date(now - 5 * 86400 * 1000).toISOString())).toBe('5 days ago')
      expect(api.formatGitRelativeTime(new Date(now - 2 * 30 * 86400 * 1000).toISOString())).toBe('2 months ago')
      expect(api.formatGitRelativeTime(new Date(now - 2 * 365 * 86400 * 1000).toISOString())).toBe('2 years ago')
      expect(api.formatGitRelativeTime('invalid')).toBe('')
    })
    it('shortGitHash takes the first 7 characters', () => {
      const { api } = makeHarness()
      expect(api.shortGitHash('abcdef1234567890')).toBe('abcdef1')
      expect(api.shortGitHash('')).toBe('')
      expect(api.shortGitHash(null)).toBe('')
    })
  })

  describe('commit context menu', () => {
    it('openGitCommitContextMenu opens and clamps to bounds', () => {
      const { api } = makeHarness()
      window.innerWidth = 1000
      window.innerHeight = 800
      api.openGitCommitContextMenu(makeCommit('abc'), { clientX: 900, clientY: 750 })
      expect(api.gitCommitContextMenu.value.visible).toBe(true)
      expect(api.gitCommitContextMenu.value.x).toBe(780) // 1000-220
      expect(api.gitCommitContextMenu.value.y).toBe(680) // 800-120
      expect(api.gitCommitContextMenu.value.commit.hash).toBe('abc')
    })
    it('closeGitCommitContextMenu closes', () => {
      const { api } = makeHarness()
      api.gitCommitContextMenu.value = { visible: true, x: 0, y: 0, commit: makeCommit('abc') }
      api.closeGitCommitContextMenu()
      expect(api.gitCommitContextMenu.value.visible).toBe(false)
    })
    it('copyGitCommit copies the full info and toasts', async () => {
      const { api, copyTextToClipboard, showToast } = makeHarness()
      api.gitCommitContextMenu.value = { visible: true, x: 0, y: 0, commit: makeCommit('abc') }
      await api.copyGitCommit(makeCommit('abc'))
      expect(copyTextToClipboard).toHaveBeenCalledWith(api.formatGitCommitInfo(makeCommit('abc')))
      expect(showToast).toHaveBeenCalledWith('Commit info copied')
      expect(api.gitCommitContextMenu.value.visible).toBe(false)
    })
    it('copyGitCommit toasts an error when copying fails', async () => {
      const { api, copyTextToClipboard, showToast } = makeHarness()
      copyTextToClipboard.mockRejectedValue(new Error('clipboard fail'))
      await api.copyGitCommit(makeCommit('abc'))
      expect(showToast).toHaveBeenCalledWith('Copy failed', 'error')
    })
    it('copyGitCommitId copies the hash', async () => {
      const { api, copyTextToClipboard, showToast } = makeHarness()
      await api.copyGitCommitId(makeCommit('abc'))
      expect(copyTextToClipboard).toHaveBeenCalledWith('abc')
      expect(showToast).toHaveBeenCalledWith('Commit ID copied')
    })
    it('formatGitCommitInfo assembles the full info', () => {
      const { api } = makeHarness()
      const commit = makeCommit('abc123', 'fix bug', ['HEAD', 'main'])
      commit.body = 'body text'
      const info = api.formatGitCommitInfo(commit)
      expect(info).toContain('commit abc123')
      expect(info).toContain('refs: HEAD, main')
      expect(info).toContain('Author: Alice <alice@example.com>')
      expect(info).toContain('Date:   2024-01-01 12:00:00')
      expect(info).toContain('fix bug')
      expect(info).toContain('body text')
    })
    it('formatGitCommitTooltip returns an empty string without a commit', () => {
      const { api } = makeHarness()
      expect(api.formatGitCommitTooltip(null)).toBe('')
      expect(api.formatGitCommitTooltip(makeCommit('abc'))).toContain('commit abc')
    })
    it('showGitCommitInfoModal sets/closes', () => {
      const { api } = makeHarness()
      api.showGitCommitInfoModal(makeCommit('abc'))
      expect(api.gitCommitInfoModal.value.hash).toBe('abc')
      // original behavior: returns directly when the commit is empty, does not reset the modal
      api.showGitCommitInfoModal(null)
      expect(api.gitCommitInfoModal.value.hash).toBe('abc')
    })
  })

  describe('watch(activeWorkspaceSessionId)', () => {
    it('refreshes when the Git view is active and the panel is visible', async () => {
      const { api, activeWorkspaceSessionId, showWorkspacePanel, workspaceSidebarView, effectiveGitAgentId, agentList, fetchWithAuth } = makeHarness()
      showWorkspacePanel.value = true
      workspaceSidebarView.value = 'git'
      agentList.value = [makeAgent('a1', '/work/a')]
      effectiveGitAgentId.value = 'a1'
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { commits: [], has_more: false } }),
      })
      activeWorkspaceSessionId.value = 'session-2'
      await nextTick()
      await flushPromises()
      expect(fetchWithAuth).toHaveBeenCalled()
    })
    it('does not refresh when the Git view is not active', async () => {
      const { api, activeWorkspaceSessionId, showWorkspacePanel, workspaceSidebarView, fetchWithAuth } = makeHarness()
      showWorkspacePanel.value = true
      workspaceSidebarView.value = 'files'
      activeWorkspaceSessionId.value = 'session-2'
      await nextTick()
      await flushPromises()
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('does not refresh when the panel is hidden', async () => {
      const { api, activeWorkspaceSessionId, showWorkspacePanel, workspaceSidebarView, fetchWithAuth } = makeHarness()
      showWorkspacePanel.value = false
      workspaceSidebarView.value = 'git'
      activeWorkspaceSessionId.value = 'session-2'
      await nextTick()
      await flushPromises()
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
  })
})
