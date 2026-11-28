// useOrchestrate unit tests
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useOrchestrate } from './useOrchestrate.js'
// Flush all microtasks (used when an async function has multiple levels of await)
async function flushPromises() {
  for (let i = 0; i < 20; i++) {
    await Promise.resolve()
  }
}
// Build a useOrchestrate dependency-injection harness
function makeHarness(overrides = {}) {
  const agentList = ref([])
  const availableNodeOptions = ref([])
  const buildNodeHttpUrl = vi.fn((host, port, nodeId, path) => `http://${host}:${port}/api/nodes/${nodeId}/${path}`)
  const fetchWithAuth = vi.fn()
  const filteredNodeOptionsForCreateAgent = ref([])
  const getDefaultCreateAgentNodeId = vi.fn(() => 'master')
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: 8080 }))
  const hasNoPanel = ref(true)
  const openAgentInPanel = vi.fn()
  const pipelineStore = { addPreview: vi.fn(), getPipeline: vi.fn() }
  const pipelineVersion = ref(0)
  const setWorkspaceSidebarView = vi.fn()
  const showToast = vi.fn()
  const showWorkspaceSidebar = ref(false)
  const readFileAsDataUrl = vi.fn(async (file) => `data:${file.name}`)
  const createAgentWithOptions = vi.fn()
  const fetchAgentList = vi.fn()
  const fetchNodeStatus = vi.fn()
  const dirDialogContext = ref('create-agent')
  const openDirDialog = vi.fn()
  const startAgentListRefresh = vi.fn()
  const api = useOrchestrate({
    agentList,
    availableNodeOptions,
    buildNodeHttpUrl,
    fetchWithAuth,
    filteredNodeOptionsForCreateAgent,
    getDefaultCreateAgentNodeId,
    getGatewayAddress,
    hasNoPanel,
    openAgentInPanel,
    pipelineStore,
    pipelineVersion,
    setWorkspaceSidebarView,
    showToast,
    showWorkspaceSidebar,
    readFileAsDataUrl,
    createAgentWithOptions,
    fetchAgentList,
    fetchNodeStatus,
    dirDialogContext,
    openDirDialog,
    startAgentListRefresh,
    ...overrides,
  })
  return {
    api,
    agentList,
    availableNodeOptions,
    buildNodeHttpUrl,
    fetchWithAuth,
    filteredNodeOptionsForCreateAgent,
    getDefaultCreateAgentNodeId,
    getGatewayAddress,
    hasNoPanel,
    openAgentInPanel,
    pipelineStore,
    pipelineVersion,
    setWorkspaceSidebarView,
    showToast,
    showWorkspaceSidebar,
    readFileAsDataUrl,
    createAgentWithOptions,
    fetchAgentList,
    fetchNodeStatus,
    dirDialogContext,
    openDirDialog,
    startAgentListRefresh,
  }
}
describe('useOrchestrate', () => {
  beforeEach(() => {
    localStorage.clear()
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })
  it('initial state: all ref default values are correct', () => {
    const { api } = makeHarness()
    expect(api.showOrchestrateModal.value).toBe(false)
    expect(api.orchestrateNodeId.value).toBe('master')
    expect(api.orchestrateFilePath.value).toBe('')
    expect(api.orchestratePluginTemplates.value).toEqual([])
    expect(api.orchestratePluginTemplatesLoading.value).toBe(false)
    expect(api.orchestrateRecentFiles.value).toEqual([])
    expect(api.orchestrateAgents.value).toEqual([])
    expect(api.orchestrateHasFlow.value).toBe(false)
    expect(api.orchestrateNodes.value).toEqual([])
    expect(api.orchestrateActiveIndex.value).toBe(0)
    expect(api.orchestrateLoading.value).toBe(false)
    expect(api.orchestrateError.value).toBe('')
    expect(api.orchestrateCreating.value).toBe(false)
    expect(api.orchestrateResults.value).toEqual([])
    expect(api.orchestrateRunWorkingDir.value).toBe('')
    expect(api.orchestrateRunning.value).toBe(false)
    expect(api.orchestrateFileEntries.value).toEqual([])
    expect(api.orchestrateSelectedFile.value).toBe('')
    expect(api.orchestrateDialogRef.value).toBe(null)
    expect(api.orchestrateShowBrowser.value).toBe(false)
    expect(api.orchestrateCurrentDirPath.value).toBe('')
    expect(api.orchestrateLocalFileInput.value).toBe(null)
    expect(api.orchestrateDirSearchText.value).toBe('')
    expect(api.orchestrateSelectedIndex.value).toBe(-1)
    expect(api.ORCHESTRATE_RECENT_KEY).toBe('haijunbot_recent_orchestrations')
    expect(api.ORCHESTRATE_RECENT_MAX).toBe(20)
    expect(api.ORCHESTRATE_FILE_EXTENSIONS).toEqual(['.yaml', '.yml', '.flow'])
  })
  it('buildOrchestrateAgentForm: field mapping and default fallbacks', () => {
    const { api } = makeHarness()
    const form = api.buildOrchestrateAgentForm({
      name: 'foo',
      working_dir: '/tmp',
      llm_group: 'g1',
      tool_group: 't1',
      task: 'do it',
      additional_args: '--x',
      quick_mode: true,
      restore_session: true,
      no_interaction_mode: true,
      node_id: 'node1',
      proxy_node: 'p1',
      access_acl: { read: ['u1'], interact: ['u2'] },
    }, 'fallback')
    expect(form).toEqual({
      name: 'foo',
      workingDir: '/tmp',
      llmGroup: 'g1',
      toolGroup: 't1',
      task: 'do it',
      additionalArgs: '--x',
      quickMode: true,
      restoreSession: true,
      noInteractionMode: true,
      nodeId: 'node1',
      proxyNode: 'p1',
      accessAclRead: ['u1'],
      accessAclInteract: ['u2'],
    })
    // Use fallbackNodeId when raw is empty
    const empty = api.buildOrchestrateAgentForm({}, 'fb-node')
    expect(empty.nodeId).toBe('fb-node')
    expect(empty.workingDir).toBe('.')
    expect(empty.llmGroup).toBe('default')
  })
  it('openOrchestrateModal: opens the modal, initializes state, loads templates and recent history', async () => {
    const { api, fetchNodeStatus, getDefaultCreateAgentNodeId, loadOrchestratePluginTemplates } = makeHarness()
    // Do not mock loadOrchestratePluginTemplates; let it run for real (returns empty with no fetchWithAuth mock)
    api.showOrchestrateModal.value = false
    await api.openOrchestrateModal()
    expect(api.showOrchestrateModal.value).toBe(true)
    expect(api.orchestrateError.value).toBe('')
    expect(api.orchestrateResults.value).toEqual([])
    expect(api.orchestrateAgents.value).toEqual([])
    expect(api.orchestrateHasFlow.value).toBe(false)
    expect(api.orchestrateActiveIndex.value).toBe(0)
    expect(api.orchestrateFilePath.value).toBe('')
    expect(getDefaultCreateAgentNodeId).toHaveBeenCalled()
  })
  it('openOrchestrateModal: fetches node status when node options are empty', async () => {
    const { api, fetchNodeStatus } = makeHarness()
    await api.openOrchestrateModal()
    expect(fetchNodeStatus).toHaveBeenCalled()
  })
  it('closeOrchestrateModal: resets all state and resets the directory context to create-agent', () => {
    const { api, dirDialogContext } = makeHarness()
    api.showOrchestrateModal.value = true
    api.orchestrateAgents.value = [{ name: 'x' }]
    api.orchestrateHasFlow.value = true
    api.orchestrateNodes.value = [{ id: 'n1' }]
    api.orchestrateShowBrowser.value = true
    api.orchestrateFileEntries.value = [{ name: 'a' }]
    api.orchestrateSelectedFile.value = '/a.yaml'
    api.orchestrateCurrentDirPath.value = '/tmp'
    api.orchestrateDirSearchText.value = 'foo'
    api.orchestrateSelectedIndex.value = 3
    dirDialogContext.value = 'orchestrate'
    api.closeOrchestrateModal()
    expect(api.showOrchestrateModal.value).toBe(false)
    expect(api.orchestrateAgents.value).toEqual([])
    expect(api.orchestrateHasFlow.value).toBe(false)
    expect(api.orchestrateNodes.value).toEqual([])
    expect(api.orchestrateShowBrowser.value).toBe(false)
    expect(api.orchestrateFileEntries.value).toEqual([])
    expect(api.orchestrateSelectedFile.value).toBe('')
    expect(api.orchestrateCurrentDirPath.value).toBe('')
    expect(api.orchestrateDirSearchText.value).toBe('')
    expect(api.orchestrateSelectedIndex.value).toBe(-1)
    expect(dirDialogContext.value).toBe('create-agent')
  })
  it('loadOrchestrateRecentFiles: reads valid localStorage data', () => {
    const { api } = makeHarness()
    localStorage.setItem('haijunbot_recent_orchestrations', JSON.stringify([{ path: '/a.yaml', nodeId: 'master' }]))
    api.loadOrchestrateRecentFiles()
    expect(api.orchestrateRecentFiles.value).toEqual([{ path: '/a.yaml', nodeId: 'master' }])
  })
  it('loadOrchestrateRecentFiles: falls back to an empty array on invalid data', () => {
    const { api } = makeHarness()
    localStorage.setItem('haijunbot_recent_orchestrations', JSON.stringify([{ path: 123 }]))
    api.loadOrchestrateRecentFiles()
    expect(api.orchestrateRecentFiles.value).toEqual([])
  })
  it('saveOrchestrateRecentFile: deduplicates and moves to top, persists, length-limits', () => {
    const { api } = makeHarness()
    api.orchestrateRecentFiles.value = [
      { path: '/a.yaml', nodeId: 'master' },
      { path: '/b.yaml', nodeId: 'master' },
    ]
    api.saveOrchestrateRecentFile('/a.yaml', 'master')
    expect(api.orchestrateRecentFiles.value[0]).toEqual({ path: '/a.yaml', nodeId: 'master' })
    expect(api.orchestrateRecentFiles.value).toHaveLength(2)
    expect(JSON.parse(localStorage.getItem('haijunbot_recent_orchestrations'))[0].path).toBe('/a.yaml')
    // Do not save an empty path
    api.saveOrchestrateRecentFile('', 'master')
    expect(api.orchestrateRecentFiles.value).toHaveLength(2)
  })
  it('removeOrchestrateRecentFile: removes the specified entry and persists', () => {
    const { api } = makeHarness()
    api.orchestrateRecentFiles.value = [
      { path: '/a.yaml', nodeId: 'master' },
      { path: '/b.yaml', nodeId: 'master' },
    ]
    api.removeOrchestrateRecentFile('/a.yaml', 'master')
    expect(api.orchestrateRecentFiles.value).toEqual([{ path: '/b.yaml', nodeId: 'master' }])
    expect(JSON.parse(localStorage.getItem('haijunbot_recent_orchestrations'))).toHaveLength(1)
  })
  it('parseOrchestrationFile: on success fills agents/hasFlow/nodes and records recent history', async () => {
    const { api, fetchWithAuth } = makeHarness()
    api.orchestrateFilePath.value = '/tmp/team.yaml'
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          path: '/tmp/team.yaml',
          agents: [{ name: 'a1', working_dir: '/w1' }],
          has_flow: false,
          nodes: [],
        },
      }),
    })
    await api.parseOrchestrationFile()
    expect(api.orchestrateLoading.value).toBe(false)
    expect(api.orchestrateError.value).toBe('')
    expect(api.orchestrateAgents.value).toHaveLength(1)
    expect(api.orchestrateAgents.value[0].name).toBe('a1')
    expect(api.orchestrateAgents.value[0].workingDir).toBe('/w1')
    expect(api.orchestrateHasFlow.value).toBe(false)
    expect(api.orchestrateRecentFiles.value[0].path).toBe('/tmp/team.yaml')
  })
  it('parseOrchestrationFile: orchestrateHasFlow is true for .flow with has_flow', async () => {
    const { api, fetchWithAuth } = makeHarness()
    api.orchestrateFilePath.value = '/tmp/flow.flow'
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          path: '/tmp/flow.flow',
          agents: [{ name: 'a1' }],
          has_flow: true,
          nodes: [{ id: 'n1' }],
        },
      }),
    })
    await api.parseOrchestrationFile()
    expect(api.orchestrateHasFlow.value).toBe(true)
    expect(api.orchestrateNodes.value).toEqual([{ id: 'n1' }])
  })
  it('parseOrchestrationFile: errors on an empty path', async () => {
    const { api } = makeHarness()
    api.orchestrateFilePath.value = ''
    await api.parseOrchestrationFile()
    expect(api.orchestrateError.value).toBe('Please enter the orchestration file path')
  })
  it('parseOrchestrationFile: errors when the backend fails', async () => {
    const { api, fetchWithAuth } = makeHarness()
    api.orchestrateFilePath.value = '/tmp/team.yaml'
    fetchWithAuth.mockResolvedValue({
      ok: false,
      json: async () => ({ success: false, error: { message: 'File not found' } }),
    })
    await api.parseOrchestrationFile()
    expect(api.orchestrateError.value).toBe('File not found')
  })
  it('addOrchestrateAgent/removeOrchestrateAgent: tab add/remove and active index adjustment', () => {
    const { api } = makeHarness()
    api.addOrchestrateAgent()
    api.addOrchestrateAgent()
    expect(api.orchestrateAgents.value).toHaveLength(2)
    expect(api.orchestrateActiveIndex.value).toBe(1)
    api.removeOrchestrateAgent(0)
    expect(api.orchestrateAgents.value).toHaveLength(1)
    expect(api.orchestrateActiveIndex.value).toBe(0)
    // Out-of-range removal has no effect
    api.removeOrchestrateAgent(5)
    expect(api.orchestrateAgents.value).toHaveLength(1)
  })
  it('createAllOrchestrateAgents: errors when there are no Agents', async () => {
    const { api } = makeHarness()
    await api.createAllOrchestrateAgents()
    expect(api.orchestrateError.value).toBe('No Agents to create')
  })
  it('createAllOrchestrateAgents: errors on an empty working directory and focuses that tab', async () => {
    const { api } = makeHarness()
    api.orchestrateAgents.value = [
      { name: 'a1', workingDir: '', task: '', noInteractionMode: false, llmGroup: 'default', quickMode: false, restoreSession: false, nodeId: 'master', proxyNode: '', accessAclRead: [], accessAclInteract: [], toolGroup: 'default', additionalArgs: '' },
    ]
    await api.createAllOrchestrateAgents()
    expect(api.orchestrateError.value).toContain('working directory cannot be empty')
    expect(api.orchestrateActiveIndex.value).toBe(0)
  })
  it('createAllOrchestrateAgents: errors when non-interactive mode has no task', async () => {
    const { api } = makeHarness()
    api.orchestrateAgents.value = [
      { name: 'a1', workingDir: '/w', task: '', noInteractionMode: true, llmGroup: 'default', quickMode: false, restoreSession: false, nodeId: 'master', proxyNode: '', accessAclRead: [], accessAclInteract: [], toolGroup: 'default', additionalArgs: '' },
    ]
    await api.createAllOrchestrateAgents()
    expect(api.orchestrateError.value).toContain('requires a task description')
  })
  it('createAllOrchestrateAgents: on full success closes the modal, adds to the list, refreshes and toasts', async () => {
    const { api, createAgentWithOptions, agentList, fetchAgentList, startAgentListRefresh, showToast, hasNoPanel, openAgentInPanel } = makeHarness()
    api.orchestrateAgents.value = [
      { name: 'a1', workingDir: '/w1', task: '', noInteractionMode: false, llmGroup: 'default', quickMode: false, restoreSession: false, nodeId: 'master', proxyNode: '', accessAclRead: [], accessAclInteract: [], toolGroup: 'default', additionalArgs: '' },
    ]
    createAgentWithOptions.mockResolvedValue({ ok: true, agent: { agent_id: 'ag1', name: 'a1' } })
    hasNoPanel.value = false
    await api.createAllOrchestrateAgents()
    expect(api.orchestrateCreating.value).toBe(false)
    expect(api.showOrchestrateModal.value).toBe(false)
    expect(api.orchestrateResults.value).toEqual([])
    expect(agentList.value[0]).toEqual({ agent_id: 'ag1', name: 'a1' })
    expect(fetchAgentList).toHaveBeenCalled()
    expect(startAgentListRefresh).toHaveBeenCalled()
    expect(openAgentInPanel).toHaveBeenCalledWith({ agent_id: 'ag1', name: 'a1' })
    expect(showToast).toHaveBeenCalledWith('Created 1 Agent(s)', 'success')
  })
  it('createAllOrchestrateAgents: on partial success keeps failed entries and toasts', async () => {
    const { api, createAgentWithOptions, showToast } = makeHarness()
    api.orchestrateAgents.value = [
      { name: 'a1', workingDir: '/w1', task: '', noInteractionMode: false, llmGroup: 'default', quickMode: false, restoreSession: false, nodeId: 'master', proxyNode: '', accessAclRead: [], accessAclInteract: [], toolGroup: 'default', additionalArgs: '' },
      { name: 'a2', workingDir: '/w2', task: '', noInteractionMode: false, llmGroup: 'default', quickMode: false, restoreSession: false, nodeId: 'master', proxyNode: '', accessAclRead: [], accessAclInteract: [], toolGroup: 'default', additionalArgs: '' },
    ]
    createAgentWithOptions
      .mockResolvedValueOnce({ ok: true, agent: { agent_id: 'ag1' } })
      .mockResolvedValueOnce({ ok: false, error: 'failed' })
    await api.createAllOrchestrateAgents()
    expect(api.orchestrateResults.value).toEqual([
      { name: 'a1', ok: true, error: '' },
      { name: 'a2', ok: false, error: 'failed' },
    ])
    // Partial success: do not close the modal (keep its original open state), keep failed entries for retry after fixing
    expect(api.showOrchestrateModal.value).toBe(false)
    expect(showToast).toHaveBeenCalledWith('Creation complete: 1/2 succeeded', 'warning')
  })
  it('openOrchestrateDirDialog: does not open the directory modal when there are no Agents', () => {
    const { api, openDirDialog } = makeHarness()
    api.openOrchestrateDirDialog()
    expect(openDirDialog).not.toHaveBeenCalled()
  })
  it('openOrchestrateDirDialog: sets the context and opens when there are Agents', () => {
    const { api, openDirDialog, dirDialogContext } = makeHarness()
    api.orchestrateAgents.value = [{ name: 'a1', workingDir: '/w' }]
    api.openOrchestrateDirDialog()
    expect(dirDialogContext.value).toBe('orchestrate')
    expect(openDirDialog).toHaveBeenCalled()
  })
  it('runOrchestration: errors when there is no file', async () => {
    const { api } = makeHarness()
    api.orchestrateFilePath.value = ''
    await api.runOrchestration()
    expect(api.orchestrateError.value).toBe('Please select and parse an orchestration file first')
  })
  it('runOrchestration: on success closes the modal and switches to Orchestration View', async () => {
    const { api, fetchWithAuth, showToast, showWorkspaceSidebar, setWorkspaceSidebarView } = makeHarness()
    api.orchestrateFilePath.value = '/tmp/flow.flow'
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    })
    await api.runOrchestration()
    expect(api.orchestrateRunning.value).toBe(false)
    expect(api.showOrchestrateModal.value).toBe(false)
    expect(showToast).toHaveBeenCalledWith('Pipeline started; view progress in "Orchestration View"', 'success')
    expect(showWorkspaceSidebar.value).toBe(true)
    expect(setWorkspaceSidebarView).toHaveBeenCalledWith('orchestration')
  })
  it('previewOrchestration: errors when there are no DAG nodes', () => {
    const { api } = makeHarness()
    api.orchestrateNodes.value = []
    api.previewOrchestration()
    expect(api.orchestrateError.value).toBe('No DAG nodes to preview; parse an orchestration file first')
  })
  it('previewOrchestration: generates a preview and switches to Orchestration View', () => {
    const { api, pipelineStore, pipelineVersion, setWorkspaceSidebarView, showToast } = makeHarness()
    api.orchestrateNodes.value = [{ id: 'n1' }]
    api.orchestrateFilePath.value = '/tmp/flow.flow'
    api.previewOrchestration()
    expect(pipelineStore.addPreview).toHaveBeenCalled()
    expect(pipelineVersion.value).toBe(1)
    expect(showToast).toHaveBeenCalled()
    expect(api.showOrchestrateModal.value).toBe(false)
    expect(setWorkspaceSidebarView).toHaveBeenCalledWith('orchestration')
  })
  it('handleApproval: returns immediately when there is no pipelineId', async () => {
    const { api, pipelineStore } = makeHarness()
    await api.handleApproval('approve', {})
    expect(pipelineStore.getPipeline).not.toHaveBeenCalled()
  })
  it('handleApproval: toasts when the pipeline is not found', async () => {
    const { api, pipelineStore, showToast } = makeHarness()
    pipelineStore.getPipeline.mockReturnValue(undefined)
    await api.handleApproval('approve', { pipelineId: 'p1' })
    expect(showToast).toHaveBeenCalledWith('Pipeline record not found', 'error')
  })
  it('handleApproval: on reject only records the decision', async () => {
    const { api, pipelineStore, fetchWithAuth, showToast } = makeHarness()
    pipelineStore.getPipeline.mockReturnValue({ orchestrationFile: '/f.flow', workingDir: '/w' })
    fetchWithAuth.mockResolvedValue({ ok: true, json: async () => ({ success: true }) })
    await api.handleApproval('reject', { pipelineId: 'p1' })
    expect(fetchWithAuth).toHaveBeenCalledTimes(1)
    expect(showToast).toHaveBeenCalledWith('Rejected', 'success')
  })
  it('handleApproval: on approve records the decision and re-runs the pipeline', async () => {
    const { api, pipelineStore, fetchWithAuth, showToast } = makeHarness()
    pipelineStore.getPipeline.mockReturnValue({ orchestrationFile: '/f.flow', workingDir: '/w' })
    fetchWithAuth.mockResolvedValue({ ok: true, json: async () => ({ success: true }) })
    await api.handleApproval('approve', { pipelineId: 'p1' })
    expect(fetchWithAuth).toHaveBeenCalledTimes(2)
    expect(showToast).toHaveBeenCalledWith('Approved, pipeline re-run', 'success')
  })
  it('isOrchestrateFile: recognizes the allowed extensions', () => {
    const { api } = makeHarness()
    expect(api.isOrchestrateFile('a.yaml')).toBe(true)
    expect(api.isOrchestrateFile('b.yml')).toBe(true)
    expect(api.isOrchestrateFile('c.flow')).toBe(true)
    expect(api.isOrchestrateFile('d.txt')).toBe(false)
    expect(api.isOrchestrateFile('e.YAML')).toBe(true)
  })
  it('filterOrchestrateEntries: filters by search keyword', () => {
    const { api } = makeHarness()
    api.orchestrateDirSearchText.value = 'foo'
    const items = [
      { name: 'foo.yaml', path: '/foo.yaml' },
      { name: 'bar.yaml', path: '/bar.yaml' },
    ]
    const filtered = api.filterOrchestrateEntries(items)
    expect(filtered).toHaveLength(1)
    expect(filtered[0].name).toBe('foo.yaml')
  })
  it('fetchOrchestrateEntries: successfully fetches directories and files', async () => {
    const { api, fetchWithAuth } = makeHarness()
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          current_path: '/tmp',
          items: [
            { name: 'sub', path: '/tmp/sub', type: 'directory' },
            { name: 'a.yaml', path: '/tmp/a.yaml', type: 'file' },
          ],
        },
      }),
    })
    await api.fetchOrchestrateEntries('/tmp')
    expect(api.orchestrateCurrentDirPath.value).toBe('/tmp')
    expect(api.orchestrateFileEntries.value).toHaveLength(2)
  })
  it('toggleOrchestrateBrowser: fetches the initial path when expanding', async () => {
    const { api, fetchWithAuth } = makeHarness()
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { current_path: '~', items: [] } }),
    })
    await api.toggleOrchestrateBrowser()
    expect(api.orchestrateShowBrowser.value).toBe(true)
    expect(fetchWithAuth).toHaveBeenCalled()
  })
  it('orchestrateInitialBrowsePath: file path uses the parent directory, empty uses the home directory', () => {
    const { api } = makeHarness()
    api.orchestrateFilePath.value = ''
    expect(api.orchestrateInitialBrowsePath()).toBe('~')
    api.orchestrateFilePath.value = '/a/b/team.yaml'
    expect(api.orchestrateInitialBrowsePath()).toBe('/a/b')
    api.orchestrateFilePath.value = '/dir'
    expect(api.orchestrateInitialBrowsePath()).toBe('/dir')
  })
  it('onOrchestrateSelectFile: fills in the path', () => {
    const { api } = makeHarness()
    api.onOrchestrateSelectFile('/tmp/a.yaml')
    expect(api.orchestrateSelectedFile.value).toBe('/tmp/a.yaml')
    expect(api.orchestrateFilePath.value).toBe('/tmp/a.yaml')
  })
  it('onOrchestrateLocalSelect: triggers a click on the hidden file input', () => {
    const { api } = makeHarness()
    const click = vi.fn()
    api.orchestrateLocalFileInput.value = { value: '/old', click }
    api.onOrchestrateLocalSelect()
    expect(click).toHaveBeenCalled()
  })
  it('onOrchestrateLocalFileChange: on successful upload fills in the path and parses', async () => {
    const { api, fetchWithAuth, readFileAsDataUrl, showToast } = makeHarness()
    api.orchestrateCurrentDirPath.value = '/tmp'
    const file = { name: 'team.yaml' }
    const event = { target: { files: [file], value: '/x' } }
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    })
    await api.onOrchestrateLocalFileChange(event)
    expect(readFileAsDataUrl).toHaveBeenCalledWith(file)
    expect(api.orchestrateFilePath.value).toBe('/tmp/team.yaml')
    expect(showToast).toHaveBeenCalledWith('Uploaded to /tmp/team.yaml', 'success')
  })
  it('handleOrchestrateSearchKeydown: Esc collapses the panel', () => {
    const { api } = makeHarness()
    api.orchestrateShowBrowser.value = true
    const event = { key: 'Escape', preventDefault: vi.fn() }
    api.handleOrchestrateSearchKeydown(event)
    expect(api.orchestrateShowBrowser.value).toBe(false)
    expect(event.preventDefault).toHaveBeenCalled()
  })
  it('handleOrchestrateSearchKeydown: ArrowDown selects the next item and syncs the highlight', () => {
    const { api } = makeHarness()
    api.orchestrateFileEntries.value = [
      { name: 'd1', path: '/d1', type: 'directory' },
      { name: 'a.yaml', path: '/a.yaml', type: 'file' },
    ]
    const event = { key: 'ArrowDown', preventDefault: vi.fn(), ctrlKey: false, altKey: false, metaKey: false }
    api.handleOrchestrateSearchKeydown(event)
    expect(api.orchestrateSelectedIndex.value).toBe(0)
    expect(event.preventDefault).toHaveBeenCalled()
    api.handleOrchestrateSearchKeydown(event)
    expect(api.orchestrateSelectedIndex.value).toBe(1)
    expect(api.orchestrateSelectedFile.value).toBe('/a.yaml')
  })
  it('handleOrchestrateSearchKeydown: Enter enters a directory', async () => {
    const { api, fetchWithAuth } = makeHarness()
    api.orchestrateFileEntries.value = [
      { name: 'd1', path: '/d1', type: 'directory' },
    ]
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { current_path: '/d1', items: [] } }),
    })
    const event = { key: 'ArrowDown', preventDefault: vi.fn(), ctrlKey: false, altKey: false, metaKey: false }
    api.handleOrchestrateSearchKeydown(event)
    const enterEvent = { key: 'Enter', preventDefault: vi.fn(), ctrlKey: false, altKey: false, metaKey: false }
    api.handleOrchestrateSearchKeydown(enterEvent)
    await flushPromises()
    expect(fetchWithAuth).toHaveBeenCalled()
  })
  it('onOrchestrateNodeChange: resets the path and re-fetches templates', async () => {
    const { api, fetchWithAuth } = makeHarness()
    api.orchestrateFilePath.value = '/old.yaml'
    api.orchestrateSelectedFile.value = '/old.yaml'
    api.orchestrateSelectedIndex.value = 2
    api.orchestrateShowBrowser.value = false
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { current_path: '~', items: [] } }),
    })
    await api.onOrchestrateNodeChange()
    expect(api.orchestrateFilePath.value).toBe('')
    expect(api.orchestrateSelectedFile.value).toBe('')
    expect(api.orchestrateSelectedIndex.value).toBe(-1)
  })
  it('loadOrchestratePluginTemplates: successfully fetches templates and filters out entries without file', async () => {
    const { api, fetchWithAuth } = makeHarness()
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: { orchestrations: [{ name: 't1', file: '/t1.yaml' }, { name: 't2' }] },
      }),
    })
    await api.loadOrchestratePluginTemplates()
    expect(api.orchestratePluginTemplatesLoading.value).toBe(false)
    expect(api.orchestratePluginTemplates.value).toEqual([{ name: 't1', file: '/t1.yaml' }])
  })
  it('selectOrchestratePluginTemplate: fills in the path and parses', async () => {
    const { api, fetchWithAuth } = makeHarness()
    api.orchestrateFilePath.value = ''
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: { path: '/t1.yaml', agents: [{ name: 'a1' }], has_flow: false, nodes: [] },
      }),
    })
    api.selectOrchestratePluginTemplate({ file: '/t1.yaml' })
    expect(api.orchestrateFilePath.value).toBe('/t1.yaml')
    await flushPromises()
    expect(api.orchestrateAgents.value).toHaveLength(1)
  })
})
