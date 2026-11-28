// Orchestration composable.
//
// Extracted from App.vue's <script setup> (Issue #118 Step 9), keeping behavior identical:
// - State: showOrchestrateModal / orchestrateNodeId / orchestrateFilePath / orchestrateAgents / ... (all orchestration modal refs)
// - Parse/create: parseOrchestrationFile / createAllOrchestrateAgents / runOrchestration / previewOrchestration / handleApproval
// - File browsing: fetchOrchestrateEntries / toggleOrchestrateBrowser / keyboard navigation / local file upload
//
// Dependency injection (passed in by the caller in setup, must be called after their definition):
// - agentList / hasNoPanel / openAgentInPanel / showToast / showWorkspaceSidebar / setWorkspaceSidebarView
// - getGatewayAddress / fetchWithAuth / buildNodeHttpUrl / availableNodeOptions / filteredNodeOptionsForCreateAgent / getDefaultCreateAgentNodeId
// - pipelineStore / pipelineVersion (defined in App.vue)
// - readFileAsDataUrl (returned by useFileTree)
// - returned by useAgents: createAgentWithOptions / fetchAgentList / fetchNodeStatus / dirDialogContext / openDirDialog / startAgentListRefresh
//
// Note: orchestrateAgents / orchestrateActiveIndex / orchestrateNodeId are also read by useAgents'
// openDirDialog / confirmDirectory / getCreateAgentDirectoryNodeId, so they are returned by this composable,
// and useAgents receives them via a getter (useOrchestrate is called after useAgents).
import { ref, computed, watch, nextTick } from 'vue'

export function useOrchestrate({
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
  // Returned by useAgents (useOrchestrate is called after useAgents, so pass the refs directly)
  createAgentWithOptions,
  fetchAgentList,
  fetchNodeStatus,
  dirDialogContext,
  openDirDialog,
  startAgentListRefresh,
}) {
  const showOrchestrateModal = ref(false)          // orchestration modal
  const orchestrateNodeId = ref('master')          // node holding the orchestration file (also the default node for creating Agents)
  const orchestrateFilePath = ref('')              // absolute path of the orchestration file
  const orchestratePluginTemplates = ref([])        // orchestration templates declared by plugins [{plugin,name,description,file}]
  const orchestratePluginTemplatesLoading = ref(false) // plugin orchestration templates loading
  const orchestrateRecentFiles = ref([])            // recently used orchestration files [{path,nodeId}] (persisted in localStorage)
  const ORCHESTRATE_RECENT_KEY = 'haijunbot_recent_orchestrations' // localStorage key for recent orchestration files
  const ORCHESTRATE_RECENT_MAX = 20                // max number of recent orchestration files kept
  const orchestrateAgents = ref([])                // parsed Agent form list (each entry maps to a tab)
  const orchestrateHasFlow = ref(false)            // whether the orchestration file has a flow field (decides "run pipeline" vs "create Agent")
  const orchestrateNodes = ref([])                 // parsed DAG nodes (for previewing a static graph, not executed)
  const orchestrateActiveIndex = ref(0)            // index of the currently active tab
  const orchestrateLoading = ref(false)            // parsing
  const orchestrateError = ref('')                 // parse error
  const orchestrateCreating = ref(false)           // batch creating
  const orchestrateResults = ref([])               // batch creation results [{ name, ok, error }]
  // Run pipeline (same path as an Agent calling pipeline_runner, drives DAG visualization)
  const orchestrateRunWorkingDir = ref('')         // working directory for running the pipeline (artifacts .haijunbot/artifacts/ are created inside it)
  const orchestrateRunning = ref(false)            // pipeline running (only means submitted; actual progress is event-driven)
  // Orchestration file browser panel: merged directory + file list (reuses DirectoryDialog in fileSelectable mode)
  const orchestrateFileEntries = ref([])           // directories and files in the current directory ({name,path,type})
  const orchestrateSelectedFile = ref('')          // currently selected file path in the panel
  const orchestrateDialogRef = ref(null)           // embedded DirectoryDialog ref
  const orchestrateShowBrowser = ref(false)        // whether the file browser panel is expanded
  const orchestrateCurrentDirPath = ref('')        // current directory path of the browser panel
  const orchestrateLocalFileInput = ref(null)       // hidden file input for choosing an orchestration file from this machine
  const orchestrateDirSearchText = ref('')         // browser panel search text
  const orchestrateSelectedIndex = ref(-1)         // keyboard navigation selected index in the browser panel (-1 = none)
  // Allowed extensions for orchestration files (only these files are shown for selection): .yaml/.yml=org orchestration, .flow=flow orchestration
  const ORCHESTRATE_FILE_EXTENSIONS = ['.yaml', '.yml', '.flow']

  // Map a single agent config from the orchestration file to an editable form object (falls back to backend defaults when fields are missing)
  function buildOrchestrateAgentForm(raw = {}, fallbackNodeId = 'master') {
    const acl = raw.access_acl && typeof raw.access_acl === 'object' ? raw.access_acl : {}
    return {
      name: String(raw.name || ''),
      workingDir: String(raw.working_dir || '.'),
      llmGroup: String(raw.llm_group || 'default'),
      toolGroup: String(raw.tool_group || 'default'),
      task: String(raw.task || ''),
      additionalArgs: String(raw.additional_args || ''),
      quickMode: !!raw.quick_mode,
      restoreSession: !!raw.restore_session,
      noInteractionMode: !!raw.no_interaction_mode,
      nodeId: String(raw.node_id || fallbackNodeId || 'master'),
      proxyNode: String(raw.proxy_node || ''),
      accessAclRead: Array.isArray(acl.read) ? acl.read.map(String) : [],
      accessAclInteract: Array.isArray(acl.interact) ? acl.interact.map(String) : [],
    }
  }

  // Open the orchestration modal: load node options and initialize the default node
  async function openOrchestrateModal() {
    orchestrateError.value = ''
    orchestrateResults.value = []
    orchestrateAgents.value = []
    orchestrateHasFlow.value = false
    orchestrateNodes.value = []
    orchestrateActiveIndex.value = 0
    orchestrateFilePath.value = ''
    showOrchestrateModal.value = true
    if (!availableNodeOptions.value.length) {
      try { await fetchNodeStatus() } catch (error) { /* keep the list empty on failure; the modal will show a hint */ }
    }
    const allowed = filteredNodeOptionsForCreateAgent.value
    orchestrateNodeId.value = allowed.some(n => n.node_id === orchestrateNodeId.value)
      ? orchestrateNodeId.value
      : (getDefaultCreateAgentNodeId() || 'master')
    // Fetch orchestration templates declared by plugins on the current node so the user can select them directly
    loadOrchestratePluginTemplates()
    // Load the history of recently used orchestration files
    loadOrchestrateRecentFiles()
  }

  function closeOrchestrateModal() {
    showOrchestrateModal.value = false
    orchestrateError.value = ''
    orchestrateResults.value = []
    orchestrateAgents.value = []
    orchestrateHasFlow.value = false
    orchestrateNodes.value = []
    orchestrateActiveIndex.value = 0
    orchestrateFilePath.value = ''
    orchestratePluginTemplates.value = []
    orchestratePluginTemplatesLoading.value = false
    // Reset the file browser panel state
    orchestrateShowBrowser.value = false
    orchestrateFileEntries.value = []
    orchestrateSelectedFile.value = ''
    orchestrateCurrentDirPath.value = ''
    orchestrateDirSearchText.value = ''
    orchestrateSelectedIndex.value = -1
    // Reset the directory selection context so it does not affect the create Agent "select directory" flow
    dirDialogContext.value = 'create-agent'
  }

  // Recently used orchestration file management (persisted in localStorage)
  // Entry format: { path: string, nodeId: string }, distinguished by node
  function loadOrchestrateRecentFiles() {
    try {
      const stored = localStorage.getItem(ORCHESTRATE_RECENT_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        const isValid = Array.isArray(parsed) && parsed.every(item =>
          item && typeof item === 'object' && typeof item.path === 'string' && typeof item.nodeId === 'string'
        )
        orchestrateRecentFiles.value = isValid ? parsed : []
      } else {
        orchestrateRecentFiles.value = []
      }
    } catch (error) {
      console.error('[ORCHESTRATE] Failed to load recent orchestration files:', error)
      orchestrateRecentFiles.value = []
    }
  }

  // Record a successfully parsed/used orchestration file to the recent history
  function saveOrchestrateRecentFile(path, nodeId) {
    const normalizedPath = String(path || '').trim()
    if (!normalizedPath) return
    const normalizedNodeId = String(nodeId || '').trim() || 'master'
    // Deduplicate: filter out an existing same-node same-path entry
    const filtered = orchestrateRecentFiles.value.filter(item =>
      !(item.path === normalizedPath && item.nodeId === normalizedNodeId)
    )
    orchestrateRecentFiles.value = [{ path: normalizedPath, nodeId: normalizedNodeId }, ...filtered].slice(0, ORCHESTRATE_RECENT_MAX)
    try {
      localStorage.setItem(ORCHESTRATE_RECENT_KEY, JSON.stringify(orchestrateRecentFiles.value))
    } catch (error) {
      console.error('[ORCHESTRATE] Failed to save recent orchestration file:', error)
    }
  }

  // Remove one entry from the recent history
  function removeOrchestrateRecentFile(path, nodeId) {
    const normalizedPath = String(path || '').trim()
    const normalizedNodeId = String(nodeId || '').trim() || 'master'
    orchestrateRecentFiles.value = orchestrateRecentFiles.value.filter(item =>
      !(item.path === normalizedPath && item.nodeId === normalizedNodeId)
    )
    try {
      localStorage.setItem(ORCHESTRATE_RECENT_KEY, JSON.stringify(orchestrateRecentFiles.value))
    } catch (error) {
      console.error('[ORCHESTRATE] Failed to remove recent orchestration file:', error)
    }
  }

  // Select a recently used orchestration file: fill in the path and parse immediately
  function selectOrchestrateRecentFile(item) {
    if (!item || !item.path) return
    orchestrateFilePath.value = item.path
    parseOrchestrationFile()
  }

  // Fetch the list of orchestration templates declared by plugins on the current node (so the user can pick directly without typing a path)
  async function loadOrchestratePluginTemplates() {
    orchestratePluginTemplatesLoading.value = true
    orchestratePluginTemplates.value = []
    try {
      const { host, port } = getGatewayAddress()
      const nodeId = String(orchestrateNodeId.value || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, nodeId, 'plugins/orchestrations'))
      const result = await response.json().catch(() => ({}))
      if (!response.ok || !result.success || !result.data) {
        orchestratePluginTemplates.value = []
        return
      }
      const templates = Array.isArray(result.data.orchestrations) ? result.data.orchestrations : []
      orchestratePluginTemplates.value = templates.filter(t => t && t.file)
    } catch (error) {
      orchestratePluginTemplates.value = []
    } finally {
      orchestratePluginTemplatesLoading.value = false
    }
  }

  // Select a plugin orchestration template: fill in the path and parse immediately
  function selectOrchestratePluginTemplate(tpl) {
    if (!tpl || !tpl.file) return
    orchestrateFilePath.value = tpl.file
    parseOrchestrationFile()
  }

  // Parse the orchestration file: call the backend API to read the YAML and extract the agents list
  async function parseOrchestrationFile() {
    const path = String(orchestrateFilePath.value || '').trim()
    if (!path) {
      orchestrateError.value = 'Please enter the orchestration file path'
      return
    }
    orchestrateLoading.value = true
    orchestrateError.value = ''
    orchestrateResults.value = []
    try {
      const { host, port } = getGatewayAddress()
      const nodeId = String(orchestrateNodeId.value || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, nodeId, 'parse-orchestration'), {
        method: 'POST',
        body: JSON.stringify({ path, node_id: nodeId }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok || !result.success || !result.data) {
        orchestrateError.value = result.error?.message || 'Failed to parse the orchestration file'
        return
      }
      const agents = Array.isArray(result.data.agents) ? result.data.agents : []
      if (!agents.length) {
        orchestrateError.value = 'The orchestration file has no agents'
        return
      }
      orchestrateAgents.value = agents.map(raw => buildOrchestrateAgentForm(raw, nodeId))
      // Only .flow flow orchestration goes through the pipeline; .yaml/.yml are org orchestration, always handled as batch creation, ignoring their flow field
      const isFlowOrchestration = String(result.data.path || path).toLowerCase().endsWith('.flow')
      orchestrateHasFlow.value = isFlowOrchestration && !!result.data.has_flow
      orchestrateNodes.value = Array.isArray(result.data.nodes) ? result.data.nodes : []
      orchestrateFilePath.value = String(result.data.path || path)
      orchestrateActiveIndex.value = 0
      // Record the recently used orchestration file history
      saveOrchestrateRecentFile(orchestrateFilePath.value, orchestrateNodeId.value)
    } catch (error) {
      orchestrateError.value = error.message || 'Failed to parse the orchestration file'
    } finally {
      orchestrateLoading.value = false
    }
  }

  // Add a blank Agent tab
  function addOrchestrateAgent() {
    orchestrateAgents.value.push(buildOrchestrateAgentForm({}, orchestrateNodeId.value))
    orchestrateActiveIndex.value = orchestrateAgents.value.length - 1
  }

  // Remove the Agent on the specified tab
  function removeOrchestrateAgent(index) {
    if (index < 0 || index >= orchestrateAgents.value.length) return
    orchestrateAgents.value.splice(index, 1)
    if (orchestrateActiveIndex.value >= orchestrateAgents.value.length) {
      orchestrateActiveIndex.value = Math.max(0, orchestrateAgents.value.length - 1)
    }
  }

  // One-click create: call createAgentWithOptions for each, aggregating the result of every Agent
  async function createAllOrchestrateAgents() {
    if (orchestrateCreating.value) return
    if (!orchestrateAgents.value.length) {
      orchestrateError.value = 'No Agents to create'
      return
    }
    // Unified validation before creation: working directory required; non-interactive mode requires a task description
    for (let i = 0; i < orchestrateAgents.value.length; i++) {
      const form = orchestrateAgents.value[i]
      const label = form.name || form.workingDir || `Agent ${i + 1}`
      if (!String(form.workingDir || '').trim()) {
        orchestrateError.value = `"${label}" working directory cannot be empty`
        orchestrateActiveIndex.value = i
        return
      }
      if (form.noInteractionMode && !String(form.task || '').trim()) {
        orchestrateError.value = `"${label}" has non-interactive mode enabled and requires a task description`
        orchestrateActiveIndex.value = i
        return
      }
    }
    orchestrateCreating.value = true
    orchestrateError.value = ''
    orchestrateResults.value = []
    const created = []
    try {
      for (const form of orchestrateAgents.value) {
        const result = await createAgentWithOptions({
          agentType: 'agent',
          workingDir: form.workingDir,
          name: form.name,
          llmGroup: form.llmGroup,
          quickMode: form.quickMode,
          restoreSession: form.restoreSession,
          noInteractionMode: form.noInteractionMode,
          // The task description is independent of non-interactive mode: pass it to the Agent whenever filled in (non-interactive mode merely additionally requires the task)
          task: form.task,
          nodeId: form.nodeId,
          proxyNode: form.proxyNode,
          accessAclRead: form.accessAclRead,
          accessAclInteract: form.accessAclInteract,
          toolGroup: form.toolGroup,
          additionalArgs: form.additionalArgs,
        })
        orchestrateResults.value.push({
          name: form.name || form.workingDir || 'Untitled',
          ok: !!result.ok,
          error: result.ok ? '' : (result.error || 'Creation failed'),
        })
        if (result.ok) created.push(result.agent)
      }
      // If all succeeded, close the modal and finish up (add to list, refresh, open the Panel per the scenario)
      const allOk = orchestrateResults.value.every(r => r.ok)
      if (allOk && created.length) {
        showOrchestrateModal.value = false
        orchestrateAgents.value = []
        orchestrateResults.value = []
        for (const agent of created) {
          agentList.value.unshift(agent)
        }
        await fetchAgentList()
        startAgentListRefresh()
        if (!hasNoPanel.value && created[0]) {
          await openAgentInPanel(created[0])
        }
        showToast(`Created ${created.length} Agent(s)`, 'success')
      } else {
        const okCount = orchestrateResults.value.filter(r => r.ok).length
        if (okCount) {
          // Partial success: refresh the list and keep failed entries so the user can fix them and retry
          await fetchAgentList()
          startAgentListRefresh()
        }
        showToast(`Creation complete: ${okCount}/${orchestrateResults.value.length} succeeded`, okCount ? 'warning' : 'error')
      }
    } finally {
      orchestrateCreating.value = false
    }
  }

  // Choose a working directory for the current orchestration tab: reuse the directory selection modal (orchestrate scenario)
  function openOrchestrateDirDialog() {
    if (!orchestrateAgents.value.length) return
    dirDialogContext.value = 'orchestrate'
    openDirDialog()
  }

  // Run pipeline: call the backend /run-orchestration (the same path as an Agent calling pipeline_runner),
  // run progress is driven via pipeline_event events to OrchestrationView's DAG visualization.
  async function runOrchestration() {
    if (orchestrateRunning.value) return
    const orchestrationFile = String(orchestrateFilePath.value || '').trim()
    if (!orchestrationFile) {
      orchestrateError.value = 'Please select and parse an orchestration file first'
      return
    }
    // The top-level spec field of the orchestration file is read by the backend as the background for each stage's Agent
    orchestrateRunning.value = true
    orchestrateError.value = ''
    try {
      const { host, port } = getGatewayAddress()
      const nodeId = String(orchestrateNodeId.value || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, nodeId, 'run-orchestration'), {
        method: 'POST',
        body: JSON.stringify({
          orchestration_file: orchestrationFile,
          working_dir: String(orchestrateRunWorkingDir.value || '').trim(),
          node_id: nodeId,
        }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok || !result.success) {
        orchestrateError.value = result.error?.message || 'Failed to run the pipeline'
        return
      }
      showToast('Pipeline started; view progress in "Orchestration View"', 'success')
      // Close the modal so the user sees the DAG visualization directly (auto-refreshes when events arrive)
      closeOrchestrateModal()
      showWorkspaceSidebar.value = true
      setWorkspaceSidebarView('orchestration')
    } catch (error) {
      orchestrateError.value = error.message || 'Failed to run the pipeline'
    } finally {
      orchestrateRunning.value = false
    }
  }

  // Preview: draw a static graph from the parsed DAG nodes (no execution, no Agent creation), add it directly to pipelineStore and switch to "Orchestration View".
  function previewOrchestration() {
    const nodes = orchestrateNodes.value
    if (!nodes.length) {
      orchestrateError.value = 'No DAG nodes to preview; parse an orchestration file first'
      return
    }
    const orchestrationFile = String(orchestrateFilePath.value || '').trim()
    const pid = `preview_${Date.now()}`
    pipelineStore.addPreview(pid, nodes, orchestrationFile)
    pipelineVersion.value++ // Trigger pipelineList computed recompute so Orchestration View immediately renders the new preview
    showToast('Orchestration preview generated (static DAG, not executed)', 'success')
    closeOrchestrateModal()
    showWorkspaceSidebar.value = true
    setWorkspaceSidebarView('orchestration')
  }
  // Gate manual approval: record the decision (approve/reject/retry); on approve/retry, re-run the pipeline with approve=true.
  // Triggered by OrchestrationView's approval overlay (args { pipelineId, note }).
  async function handleApproval(action, { pipelineId, note = '' } = {}) {
    if (!pipelineId) return
    const pipeline = pipelineStore.getPipeline(pipelineId)
    if (!pipeline) {
      showToast('Pipeline record not found', 'error')
      return
    }
    const { host, port } = getGatewayAddress()
    // 1) First record the approval decision (POST /api/pipeline-approval, master gateway)
    try {
      const resp = await fetchWithAuth(buildNodeHttpUrl(host, port, 'master', 'pipeline-approval'), {
        method: 'POST',
        body: JSON.stringify({ pipeline_id: pipelineId, action, note }),
      })
      const result = await resp.json().catch(() => ({}))
      if (!resp.ok || !result.success) {
        showToast(result.error?.message || 'Failed to record the approval decision', 'error')
        return
      }
    } catch (error) {
      showToast(error.message || 'Failed to record the approval decision', 'error')
      return
    }
    const actionLabel = { approve: 'Approved', reject: 'Rejected', retry: 'Retried' }[action] || action
    // 2) Approve/retry: re-run the pipeline with approve=true (continue with subsequent stages after the gate confirms)
    if (action === 'approve' || action === 'retry') {
      const orchestrationFile = String(pipeline.orchestrationFile || '').trim()
      const workingDir = String(pipeline.workingDir || '').trim()
      if (!orchestrationFile) {
        showToast('Pipeline is missing its orchestration file and cannot be re-run', 'error')
        return
      }
      try {
        const resp = await fetchWithAuth(buildNodeHttpUrl(host, port, 'master', 'run-orchestration'), {
          method: 'POST',
          body: JSON.stringify({
            orchestration_file: orchestrationFile,
            working_dir: workingDir,
            node_id: 'master',
            approve: true,
          }),
        })
        const result = await resp.json().catch(() => ({}))
        if (!resp.ok || !result.success) {
          showToast(result.error?.message || 'Failed to re-run the pipeline', 'error')
          return
        }
        showToast(`${actionLabel}, pipeline re-run`, 'success')
      } catch (error) {
        showToast(error.message || 'Failed to re-run the pipeline', 'error')
        return
      }
    } else {
      showToast(`${actionLabel}`, 'success')
    }
  }
  // ===== Orchestration file browser panel (node dropdown + embedded directory/file browsing, modeled on "Open Directory") =====
  // Directory entries (for DirectoryDialog's filteredDirs, supports search filtering)
  const orchestrateFilteredDirs = computed(() => {
    const dirs = orchestrateFileEntries.value.filter(item => item.type === 'directory')
    return filterOrchestrateEntries(dirs)
  })
  // File entries (only allowed extensions are shown, supports search filtering)
  const orchestrateFilteredFiles = computed(() => {
    const files = orchestrateFileEntries.value.filter(item => item.type === 'file' && isOrchestrateFile(item.name))
    return filterOrchestrateEntries(files)
  })
  // Unified ordered list for keyboard navigation: directories first, files after (matching the panel render order)
  const orchestrateNavItems = computed(() => [
    ...orchestrateFilteredDirs.value.map(d => ({ type: 'directory', path: d.path })),
    ...orchestrateFilteredFiles.value.map(f => ({ type: 'file', path: f.path })),
  ])
  function isOrchestrateFile(name) {
    const lower = String(name || '').toLowerCase()
    return ORCHESTRATE_FILE_EXTENSIONS.some(ext => lower.endsWith(ext))
  }
  function filterOrchestrateEntries(items) {
    const keyword = String(orchestrateDirSearchText.value || '').toLowerCase().trim()
    if (!keyword) return items
    return items.filter(item =>
      String(item.name || '').toLowerCase().includes(keyword) ||
      String(item.path || '').toLowerCase().includes(keyword)
    )
  }
  // Fetch directories and files under the given directory (keeps files, isolated from fetchDirectories' "directories only" behavior)
  async function fetchOrchestrateEntries(path = '') {
    try {
      const { host, port } = getGatewayAddress()
      const params = new URLSearchParams({ path })
      const nodeId = String(orchestrateNodeId.value || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, nodeId, `directories?${params.toString()}`))
      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        orchestrateError.value = error.error?.message || 'Failed to fetch the directory listing'
        return
      }
      const result = await response.json()
      if (result.success && result.data) {
        orchestrateCurrentDirPath.value = result.data.current_path || ''
        orchestrateFileEntries.value = Array.isArray(result.data.items) ? result.data.items : []
      }
    } catch (error) {
      orchestrateError.value = error.message || 'Error fetching the directory listing'
    }
  }
  // Expand/collapse the orchestration file browser panel
  async function toggleOrchestrateBrowser() {
    orchestrateShowBrowser.value = !orchestrateShowBrowser.value
    if (!orchestrateShowBrowser.value) return
    orchestrateDirSearchText.value = ''
    orchestrateSelectedFile.value = ''
    orchestrateSelectedIndex.value = -1
    await fetchOrchestrateEntries(orchestrateInitialBrowsePath())
  }
  // Compute the initial browse path: if the filled path is a file, use its parent directory, otherwise use itself; if empty, start from the home directory
  function orchestrateInitialBrowsePath() {
    const filled = String(orchestrateFilePath.value || '').trim()
    if (!filled) return '~'
    if (isOrchestrateFile(filled)) {
      const idx = filled.replace(/\\/g, '/').lastIndexOf('/')
      return idx > 0 ? filled.slice(0, idx) : '~'
    }
    return filled
  }
  // Enter a directory in the panel
  async function enterOrchestrateDir(path) {
    orchestrateSelectedFile.value = ''
    orchestrateDirSearchText.value = ''
    orchestrateSelectedIndex.value = -1
    await fetchOrchestrateEntries(path)
  }
  // Go to the parent directory
  async function goToOrchestrateParentDir() {
    const normalized = String(orchestrateCurrentDirPath.value || '').replace(/\\/g, '/')
    const parts = normalized.split('/').filter(p => p)
    if (!parts.length) return
    parts.pop()
    orchestrateSelectedIndex.value = -1
    await fetchOrchestrateEntries('/' + parts.join('/'))
  }
  // Select a file: fill in the orchestration file path
  function onOrchestrateSelectFile(path) {
    orchestrateSelectedFile.value = path
    orchestrateFilePath.value = path
  }
  // Open the local file picker
  function onOrchestrateLocalSelect() {
    const input = orchestrateLocalFileInput.value
    if (!input) return
    input.value = ''
    input.click()
  }
  // Local orchestration file selected: upload to the chosen node, then fill in the node path and parse
  async function onOrchestrateLocalFileChange(event) {
    const input = event?.target
    const file = input?.files?.[0]
    if (input) input.value = ''
    if (!file) return
    const nodeId = String(orchestrateNodeId.value || 'master').trim() || 'master'
    orchestrateError.value = ''
    try {
      // Upload target directory: prefer the current browse directory (when the browser panel is open); otherwise fetch the absolute path of the home directory
      let baseDir = String(orchestrateCurrentDirPath.value || '').replace(/\/+$/, '')
      if (!baseDir) {
        await fetchOrchestrateEntries('~')
        baseDir = String(orchestrateCurrentDirPath.value || '').replace(/\/+$/, '')
      }
      if (!baseDir) {
        orchestrateError.value = 'Cannot determine the upload directory; open "Browse" to select a target directory first'
        return
      }
      const data = await readFileAsDataUrl(file)
      const { host, port } = getGatewayAddress()
      const targetPath = `${baseDir}/${file.name}`
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, nodeId, 'file-upload'), {
        method: 'POST',
        body: JSON.stringify({ path: targetPath, data, node_id: nodeId }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok || !result.success) {
        throw new Error(result.error?.message || 'Upload failed')
      }
      orchestrateFilePath.value = targetPath
      showToast(`Uploaded to ${targetPath}`, 'success')
      parseOrchestrationFile()
    } catch (error) {
      orchestrateError.value = error.message || 'Failed to upload the local orchestration file'
    }
  }
  // Browser panel search box key events: Esc collapses the panel; up/down navigate the directory/file list; Enter enters a directory or selects a file
  function handleOrchestrateSearchKeydown(event) {
    if (event.key === 'Escape') {
      orchestrateShowBrowser.value = false
      event.preventDefault()
      return
    }
    // Do not navigate the list when a Ctrl/Alt/Meta modifier is held
    if (event.ctrlKey || event.altKey || event.metaKey) return
    const items = orchestrateNavItems.value
    const maxIndex = items.length - 1

    if (event.key === 'ArrowDown') {
      if (orchestrateSelectedIndex.value < maxIndex) {
        orchestrateSelectedIndex.value++
      } else if (orchestrateSelectedIndex.value === -1 && maxIndex >= 0) {
        orchestrateSelectedIndex.value = 0
      }
      syncOrchestrateKeyboardSelection()
      scrollToOrchestrateSelected()
      event.preventDefault()
      return
    }
    if (event.key === 'ArrowUp') {
      if (orchestrateSelectedIndex.value > 0) {
        orchestrateSelectedIndex.value--
      } else if (orchestrateSelectedIndex.value === -1) {
        orchestrateSelectedIndex.value = maxIndex
      } else {
        orchestrateSelectedIndex.value = -1
      }
      syncOrchestrateKeyboardSelection()
      scrollToOrchestrateSelected()
      event.preventDefault()
      return
    }
    if (event.key === 'Enter') {
      const item = items[orchestrateSelectedIndex.value]
      if (item) {
        if (item.type === 'directory') {
          enterOrchestrateDir(item.path)
        } else {
          onOrchestrateSelectFile(item.path)
        }
        event.preventDefault()
      }
    }
  }
  // Keyboard navigation highlight sync: directory items highlight via selectedDir, file items via selectedFile
  const orchestrateHighlightedDir = computed(() => {
    const item = orchestrateNavItems.value[orchestrateSelectedIndex.value]
    return item && item.type === 'directory' ? item.path : ''
  })
  const orchestrateHighlightedFile = computed(() => {
    const item = orchestrateNavItems.value[orchestrateSelectedIndex.value]
    return item && item.type === 'file' ? item.path : ''
  })
  // Sync the current keyboard selection to DirectoryDialog's highlight props
  function syncOrchestrateKeyboardSelection() {
    const item = orchestrateNavItems.value[orchestrateSelectedIndex.value]
    if (item && item.type === 'file') {
      orchestrateSelectedFile.value = item.path
    }
  }
  // Scroll to the keyboard-selected list item (.dir-item.selected inside DirectoryDialog)
  function scrollToOrchestrateSelected() {
    nextTick(() => {
      const el = orchestrateDialogRef.value?.$el?.querySelector?.('.dir-item.selected')
      el?.scrollIntoView?.({ block: 'nearest' })
    })
  }
  // Reset the keyboard selection index when the search text changes (the filtered list changed, so the old index is meaningless)
  watch(orchestrateDirSearchText, () => {
    orchestrateSelectedIndex.value = -1
  })
  // Switch orchestration node: re-fetch the file list
  async function onOrchestrateNodeChange() {
    orchestrateFilePath.value = ''
    orchestrateSelectedFile.value = ''
    orchestrateSelectedIndex.value = -1
    // After the node switch, re-fetch the plugin orchestration templates on that node
    loadOrchestratePluginTemplates()
    if (orchestrateShowBrowser.value) {
      await fetchOrchestrateEntries('~')
    }
  }

  return {
    // ref
    showOrchestrateModal,
    orchestrateNodeId,
    orchestrateFilePath,
    orchestratePluginTemplates,
    orchestratePluginTemplatesLoading,
    orchestrateRecentFiles,
    orchestrateAgents,
    orchestrateHasFlow,
    orchestrateNodes,
    orchestrateActiveIndex,
    orchestrateLoading,
    orchestrateError,
    orchestrateCreating,
    orchestrateResults,
    orchestrateRunWorkingDir,
    orchestrateRunning,
    orchestrateFileEntries,
    orchestrateSelectedFile,
    orchestrateDialogRef,
    orchestrateShowBrowser,
    orchestrateCurrentDirPath,
    orchestrateLocalFileInput,
    orchestrateDirSearchText,
    orchestrateSelectedIndex,
    orchestrateFilteredDirs,
    orchestrateFilteredFiles,
    orchestrateNavItems,
    orchestrateHighlightedDir,
    orchestrateHighlightedFile,
    // Functions
    buildOrchestrateAgentForm,
    openOrchestrateModal,
    closeOrchestrateModal,
    loadOrchestrateRecentFiles,
    saveOrchestrateRecentFile,
    removeOrchestrateRecentFile,
    selectOrchestrateRecentFile,
    loadOrchestratePluginTemplates,
    selectOrchestratePluginTemplate,
    parseOrchestrationFile,
    addOrchestrateAgent,
    removeOrchestrateAgent,
    createAllOrchestrateAgents,
    openOrchestrateDirDialog,
    runOrchestration,
    previewOrchestration,
    handleApproval,
    isOrchestrateFile,
    filterOrchestrateEntries,
    fetchOrchestrateEntries,
    toggleOrchestrateBrowser,
    orchestrateInitialBrowsePath,
    enterOrchestrateDir,
    goToOrchestrateParentDir,
    onOrchestrateSelectFile,
    onOrchestrateLocalSelect,
    onOrchestrateLocalFileChange,
    handleOrchestrateSearchKeydown,
    syncOrchestrateKeyboardSelection,
    scrollToOrchestrateSelected,
    onOrchestrateNodeChange,
    // Constants
    ORCHESTRATE_RECENT_KEY,
    ORCHESTRATE_RECENT_MAX,
    ORCHESTRATE_FILE_EXTENSIONS,
  }
}
