// Agent management composable.
//
// Extracted from App.vue's <script setup> (Issue #118 Step 9) with behavior fully preserved:
// - Status text/class: getStatusText / getStatusClass / isWaitingInput / fetchAgentStatus / syncOnlineAgentStatuses
// - Directory selection: dirDialogContext / openDirDialog / fetchDirectories / selectDirectory / confirmDirectory / cancelDirDialog
// - Create Agent: openCreateAgentModal / createAgentWithOptions / afterAgentCreated / createAgent / one-liner creation
// - Completion: openCompletions / insertCompletion / keyboard navigation
// - List/add/remove/update: fetchAgentList / copyAgent / group management / renameAgent / deleteAgent / regenerateAgent / switchAgent
//
// Dependency injection (the caller passes them in setup, and they must be called after they are defined):
// - Early refs (created at the top level of App.vue): agentList / currentAgentId / agentStatuses / isStoppedAgent / currentAgent /
//   agentGroups / selectedAgents / isBatchMode / inputText / inputMode / inputRequests / inputTip /
//   panelInputTexts / panelInputModes / panelInputTips / panelConfirmData / pendingInputAgentId /
//   pendingConfirmAgentId / inputBuffers / allOutputs / outputs / outputList / panelOutputLists /
//   panels / sessionPanelRefs / showToast / showConfirm / showSettingsModal / showWorkspacePanel /
//   activeWorkspaceSession / hasNoPanel / isAutoFocusSuppressed / isAnyModalOpen / socket / sockets /
//   auth / username / getHttpProtocol / buildNodeHttpUrl / getGatewayAddress / fetchWithAuth /
//   escapeHtml / historyStorage / loadHistoryMessages / sendMessageToAgent / setupHistoryScrollListener /
//   openAgentInPanel / closePanel / closeAgentInPanel / closeOpenDirDialog / confirmOpenDir /
//   restoreWorkspacePaneContents / saveRecentWorkDir / loadRecentWorkDirs / filteredDirList /
//   sortCompletionItems / recordCompletionSelection / switchGeneration / windowWidth / workspaceAutoOpened /
//   agentListLoaded / setModalAutoFocusSuppressUntil / MODAL_AUTOFOCUS_SUPPRESS_MS / hasMoreHistory /
//   historyOffset / showCompletions / completionCursorPos / completionHasAtSymbol / completionAgentId /
//   completionSource / petLobbyRef / completions / completionSearch / fileCompletions /
//   completionSearchInput / completionsModalRef / selectedIndex / showCreateAgentModal /
//   showQuickCreateAgentModal / quickCreateAgentLoading / quickCreateAgentError / showRenameAgentModal /
//   renamingAgent / renameAgentName / showDirDialog / currentDirPath / dirList / selectedDir /
//   dirSearchText / dirSearchInput / selectedDirIndex / recentWorkDirs / renameInput / showOpenDirDialog /
//   openDirNodeId / openDirPath / openDirInput / openDirDialogRef / openDirSource / pluginPickDirResolver /
//   gitCustomDir / newAgentType / newAgentDir / newAgentName / modelGroups / newAgentModelGroup /
//   newCodeAgentWorktree / newAgentQuickMode / newAgentRestoreSession / newAgentNoInteractionMode /
//   newAgentTaskDescription / newAgentCreateError / newAgentProxyNode / newAgentAccessAclRead /
//   newAgentAccessAclInteract / availableUserOptions / filteredUserOptionsForAcl / availableNodeOptions /
//   userAccessibleNodes / userPermissions / nodeDisplayNames / getNodeDisplayName / newAgentNodeId /
//   filteredNodeOptionsForCreateAgent / getDefaultCreateAgentNodeId / generateAgentName / skipNameWatch /
//   showToolsModal / toolsContent / toolsLoading / showEditAccessModal / editingAccessAgent /
//   editAccessRead / editAccessInteract / rulesLoading / showRulesModal / rulesContent /
//   rulesLoadedContent / selectedTerminalNodeId
//
// - Composable return values (passed by reference; the call site comes before useAgents):
//   chatName (useChat) / saveToHistory / lobbyHistoryIndex / lobbyHistoryTemp (useInputHistory) /
//   maybeStartTour (useTour) / fileTreeState / fileTreeExpanded / fileTreeLoading (useFileTree)
//
// - Getter injection (the call site comes after useAgents; evaluated only when the function runs):
//   orchestrateAgents / orchestrateActiveIndex / orchestrateNodeId (useOrchestrate returns) /
//   terminals / terminalHosts / disposeExecutionTerminal (useTerminal returns) /
//   connectToAgent / autoConnectToOnlineAgents (useGatewayConnection returns) /
//   renderMessageHtml / appendOutput / sendInputDirectly / sendBufferedInput / sendConfirmResult /
//   restoreWaitingConfirmUI / pushOverlayState (functions defined later in App.vue)
//
// Note: domain refs (dirDialogContext / showToolsModal / toolsContent / toolsLoading / showEditAccessModal /
// editingAccessAgent / editAccessRead / editAccessInteract) are created and returned by this composable;
// App.vue destructures and shares them (isAnyModalOpen / template reads them, etc.).
import { ref, computed, watch, nextTick } from 'vue'

export function useAgents({
  // Early refs (passed by reference directly)
  agentList,
  currentAgentId,
  agentStatuses,
  isStoppedAgent,
  currentAgent,
  agentGroups,
  selectedAgents,
  isBatchMode,
  inputText,
  inputMode,
  inputRequests,
  inputTip,
  panelInputTexts,
  panelInputModes,
  panelInputTips,
  panelConfirmData,
  pendingInputAgentId,
  pendingConfirmAgentId,
  inputBuffers,
  allOutputs,
  outputs,
  outputList,
  panelOutputLists,
  panels,
  sessionPanelRefs,
  showToast,
  showConfirm,
  showSettingsModal,
  showWorkspacePanel,
  activeWorkspaceSession,
  hasNoPanel,
  isAutoFocusSuppressed,
  isAnyModalOpen,
  socket,
  sockets,
  auth,
  username,
  getHttpProtocol,
  buildNodeHttpUrl,
  getGatewayAddress,
  fetchWithAuth,
  escapeHtml,
  historyStorage,
  loadHistoryMessages,
  sendMessageToAgent,
  setupHistoryScrollListener,
  openAgentInPanel,
  closePanel,
  closeAgentInPanel,
  closeOpenDirDialog,
  confirmOpenDir,
  restoreWorkspacePaneContents,
  saveRecentWorkDir,
  loadRecentWorkDirs,
  filteredDirList,
  sortCompletionItems,
  recordCompletionSelection,
  switchGeneration,
  windowWidth,
  agentListLoaded,
  setModalAutoFocusSuppressUntil,
  MODAL_AUTOFOCUS_SUPPRESS_MS,
  hasMoreHistory,
  historyOffset,
  showCompletions,
  completionCursorPos,
  completionHasAtSymbol,
  completionAgentId,
  completionSource,
  petLobbyRef,
  completions,
  completionSearch,
  fileCompletions,
  completionSearchInput,
  completionsModalRef,
  selectedIndex,
  showCreateAgentModal,
  showQuickCreateAgentModal,
  quickCreateAgentLoading,
  quickCreateAgentError,
  showRenameAgentModal,
  renamingAgent,
  renameAgentName,
  showDirDialog,
  currentDirPath,
  dirList,
  selectedDir,
  dirSearchText,
  dirSearchInput,
  selectedDirIndex,
  dirDialogRef,
  saveAgentGroups,
  renameInput,
  openDirNodeId,
  openDirPath,
  openDirDialogRef,
  newAgentType,
  newAgentDir,
  newAgentName,
  modelGroups,
  newAgentModelGroup,
  newCodeAgentWorktree,
  newAgentQuickMode,
  newAgentRestoreSession,
  newAgentNoInteractionMode,
  newAgentTaskDescription,
  newAgentCreateError,
  newAgentProxyNode,
  newAgentAccessAclRead,
  newAgentAccessAclInteract,
  availableUserOptions,
  availableNodeOptions,
  userAccessibleNodes,
  userPermissions,
  getNodeDisplayName,
  newAgentNodeId,
  filteredNodeOptionsForCreateAgent,
  getDefaultCreateAgentNodeId,
  generateAgentName,
  skipNameWatch,
  rulesLoading,
  showRulesModal,
  rulesContent,
  rulesLoadedContent,
  selectedTerminalNodeId,
  // Composable return values (passed by reference)
  chatName,
  saveToHistory,
  lobbyHistoryIndex,
  lobbyHistoryTemp,
  maybeStartTour,
  fileTreeState,
  fileTreeExpanded,
  fileTreeLoading,
  // Getter injection (returned by useOrchestrate / useTerminal / useGatewayConnection; lazily evaluated)
  orchestrateAgents: getOrchestrateAgents,
  orchestrateActiveIndex: getOrchestrateActiveIndex,
  orchestrateNodeId: getOrchestrateNodeId,
  terminals: getTerminals,
  terminalHosts: getTerminalHosts,
  disposeExecutionTerminal: getDisposeExecutionTerminal,
  connectToAgent: getConnectToAgent,
  autoConnectToOnlineAgents: getAutoConnectToOnlineAgents,
  // Getter injection (functions defined later in App.vue)
  renderMessageHtml: getRenderMessageHtml,
  appendOutput: getAppendOutput,
  sendInputDirectly: getSendInputDirectly,
  sendBufferedInput: getSendBufferedInput,
  sendConfirmResult: getSendConfirmResult,
  restoreWaitingConfirmUI: getRestoreWaitingConfirmUI,
  pushOverlayState: getPushOverlayState,
}) {
  // -- Domain refs (created and returned by this composable; App.vue destructures and shares them) --
  // Directory-selection dialog usage scenarios: 'create-agent' (choose a workdir when creating an Agent) / 'open-dir' (open a directory on a node) / 'orchestrate' (choose a workdir for orchestration)
  // All three reuse the same directory filtering logic (fetchDirectories / filteredDirList / keyboard navigation, etc.); only the node source and the destination after confirmation differ
  const dirDialogContext = ref('create-agent')
  // View tools
  const showToolsModal = ref(false)
  const toolsContent = ref({ all_tools: [], allowed_tools: null })
  const toolsLoading = ref(false)
  // Agent ACL editing
  const showEditAccessModal = ref(false)
  const editingAccessAgent = ref(null)
  const editAccessRead = ref([])
  const editAccessInteract = ref([])
  // Flag to auto-open the editor (the single container) after the first Agent fetch (originally App.vue line 2880 let; no references outside this scope, moved into this composable)
  let workspaceAutoOpened = false
  // ========== Agent management methods ==========


  // Get status text (combined display)
  function getStatusText(agent) {
    const statusData = agentStatuses.value.get(agent.agent_id)

    // Agent status (process level)
    const agentStatus = agent.status || 'running'

    // If the Agent has stopped, only show the stopped status
    if (agentStatus === 'stopped') {
      return 'Completed'
    }

    // If there is no running-status data, show the Agent status
    if (!statusData) {
      return 'Running'
    }

    // Combined display: Agent status + execution status
    const executionStatus = statusData.execution_status || 'running'

    // If the execution status is running, only show "Running"
    if (executionStatus === 'running') {
      return 'Running'
    }

    // If the execution status is not running, show a combined display
    const labels = {
      'running': 'Running',
      'waiting_multi': 'Waiting for multi-line input',
      'waiting_single': 'Awaiting confirmation',
      'waiting_confirm': 'Awaiting confirmation'
    }
    const executionStatusText = labels[executionStatus] || 'Running'

    // Combined display: Running (waiting status)
    return `Running (${executionStatusText})`
  }

  // Get the status CSS class name
  function getStatusClass(agent) {
    const statusData = agentStatuses.value.get(agent.agent_id)

    // Prefer the agent status: if the agent has stopped, directly return "stopped"
    if (agent.status === 'stopped') {
      return 'stopped'
    }

    // Non-stopped status: use execution_status
    if (statusData && statusData.execution_status) {
      return statusData.execution_status
    }

    // Default to running
    return 'running'
  }

  // Determine whether the agent is in a waiting-for-input state
  function isWaitingInput(agent) {
    const statusClass = getStatusClass(agent)
    return statusClass === 'waiting_multi' || statusClass === 'waiting_single' || statusClass === 'waiting_confirm'
  }

  // Query the Agent status (proxied through the gateway)
  async function fetchAgentStatus(agent) {
    if (!agent || !agent.agent_id) {
      console.warn('[AGENT STATUS] Invalid agent:', agent)
      return 'running' // Default to returning "running"
    }

    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agent/${agent.agent_id}/status`))

      if (!response.ok) {
        console.warn(`[AGENT STATUS] Failed to fetch status for agent ${agent.agent_id}:`, response.status)
        return 'running' // Default to returning "running"
      }

      const result = await response.json()
      // execution_status is a task-level status (running/waiting_multi/waiting_single)
      let executionStatus = result.execution_status || 'running'

      // [Race protection] input_request arrives in real time over WebSocket and is more
      // authoritative than /status HTTP polling. If a local unfinished input request exists,
      // the backend is currently waiting for the input of that request; the /status response
      // may have been read mid-command (running) and thus be stale. Typical scenario: on the
      // first <SwitchModelGroup> run the backend publishes input_request(single) and then
      // _update_status(waiting_single); the polling HTTP response arrives later than the
      // input_request, so it reads a stale "running". In that case trust the input request's
      // mode, so an already-switched single-line input is not overwritten back to multi-line,
      // and agentStatuses is not wrongly written as running.
      //
      // Note: we cannot rely on inputRequests alone. When the user sends a command, the backend
      // is still running and the command first enters inputBuffers; when input_request arrives
      // afterwards, it takes the "buffered branch" (early return in handleMessage) and is NOT
      // written into inputRequests (sendInputResult also deletes it). Therefore we also use the
      // already-recorded waiting state in agentStatuses (written when input_request/confirm is
      // handled) as a basis: as long as the local state is already waiting for input/confirmation
      // while polling reads a stale running, the local waiting state wins, guaranteeing the
      // single-line input box is not overwritten back to multi-line by an in-flight poll.
      const pendingInputRequest = inputRequests.value.get(agent.agent_id)
      if (pendingInputRequest && executionStatus === 'running') {
        executionStatus = pendingInputRequest.mode === 'single' ? 'waiting_single' : 'waiting_multi'
      }
      const localWaitingStatus = agentStatuses.value.get(agent.agent_id)?.execution_status
      if (executionStatus === 'running' && ['waiting_single', 'waiting_multi', 'waiting_confirm'].includes(localWaitingStatus)) {
        executionStatus = localWaitingStatus
      }

      // Update the status map (stored object format)
      // While a local confirm bar still exists (e.g. completeFromPanel already entered the
      // confirm state locally), the backend execution_status may still be waiting_multi; in that
      // case the local status must not be overwritten, otherwise the y/n/Enter keys would stop
      // working.
      const hasLocalConfirm = panelConfirmData.value.has(agent.agent_id)
      if (!hasLocalConfirm) {
        agentStatuses.value.set(agent.agent_id, {execution_status: executionStatus, non_interactive: !!result.non_interactive})
      }

      // Restore the input UI from execution_status after the current Agent connects
      if (agent.agent_id === currentAgentId.value) {
        if (executionStatus === 'waiting_single') {
          inputMode.value = 'single'
          panelInputModes.value.set(agent.agent_id, 'single')
          // Focus the input box (do not steal focus while a modal or the pet ring menu is open)
          const targetPanel = panels.value.find(p => p.agentId === agent.agent_id)
          const sp = targetPanel ? sessionPanelRefs.get(targetPanel.id) : null
          if (sp?.focusInput && !isAutoFocusSuppressed()) sp.focusInput()
        } else if (executionStatus === 'waiting_multi') {
          // While a local confirm bar still exists (e.g. completeFromPanel already entered the
          // confirm state locally), the backend execution_status may still be waiting_multi; in
          // that case the input box must not be reset to multi-line, otherwise the confirm bar
          // remains while the input box has already switched back to multi-line.
          // After the user confirms/cancels, panelConfirmData is cleared and the next poll syncs normally.
          if (hasLocalConfirm) {
            return executionStatus
          }
          inputMode.value = 'multi'
          panelInputModes.value.set(agent.agent_id, 'multi')
          // Focus the input box (do not steal focus while a modal or the pet ring menu is open)
          const targetPanel = panels.value.find(p => p.agentId === agent.agent_id)
          const sp = targetPanel ? sessionPanelRefs.get(targetPanel.id) : null
          if (sp?.focusInput && !isAutoFocusSuppressed()) sp.focusInput()
        } else if (executionStatus === 'waiting_confirm') {
          // Get pending_confirm from the status response and show the dialog
          const pendingConfirm = result.pending_confirm
          if (pendingConfirm && pendingConfirm.payload) {
            const payload = pendingConfirm.payload
            pendingConfirmAgentId.value = agent.agent_id
            // Update the panel-embedded confirm data (isolated by agentId)
            panelConfirmData.value.set(agent.agent_id, {
              message: payload.message || 'Please confirm',
              defaultConfirm: payload.default !== undefined ? payload.default : true
            })
            // Confirm requests use single-line input mode
            inputMode.value = 'single'
            panelInputModes.value.set(agent.agent_id, 'single')
            inputTip.value = payload.message || 'Please confirm (y/n/Enter)'
            panelInputTips.value.set(agent.agent_id, payload.message || 'Please confirm (y/n/Enter)')
            // Focus the input box (do not steal focus while a modal or the pet ring menu is open)
            const targetPanel = panels.value.find(p => p.agentId === agent.agent_id)
            const sp = targetPanel ? sessionPanelRefs.get(targetPanel.id) : null
            if (sp?.focusInput && !isAutoFocusSuppressed()) sp.focusInput()
            // With no panel, no global dialog is shown; the confirm request waits silently and the confirm control is visible once the user opens a panel
          } else {
            console.warn('[AGENT STATUS] waiting_confirm but no pending_confirm payload found')
          }
        } else {
          // Running: the input box is still usable (type ahead; Ctrl+Enter sends/buffers), so like
          // waiting_multi the focus goes to the multi-line input box, saving the user from clicking manually.
          inputMode.value = 'multi'
          panelInputModes.value.set(agent.agent_id, 'multi')
          const targetPanel = panels.value.find(p => p.agentId === agent.agent_id)
          const sp = targetPanel ? sessionPanelRefs.get(targetPanel.id) : null
          if (sp?.focusInput && !isAutoFocusSuppressed()) sp.focusInput()
        }
      } else {
      }

      return executionStatus
    } catch (error) {
      console.error(`[AGENT STATUS] Error fetching status for agent ${agent.agent_id}:`, error)
      return 'running' // return the default status on error
    }
  }

  // Actively sync the execution status of online agents (so waiting-for-input states are not missed by relying only on WebSocket pushes)
  const syncingAgentStatuses = new Set()
  let lastStatusSyncAt = 0
  const STATUS_SYNC_INTERVAL = 5000 // Minimum status-sync interval (ms)

  function syncOnlineAgentStatuses() {
    const now = Date.now()
    if (now - lastStatusSyncAt < STATUS_SYNC_INTERVAL) {
      return
    }
    lastStatusSyncAt = now

    for (const agent of agentList.value) {
      if (agent.status !== 'running') continue
      if (syncingAgentStatuses.has(agent.agent_id)) continue
      syncingAgentStatuses.add(agent.agent_id)
      fetchAgentStatus(agent)
        .catch((error) => {
          console.warn(`[AGENT STATUS] Sync failed for ${agent.agent_id}:`, error?.message)
        })
        .finally(() => {
          syncingAgentStatuses.delete(agent.agent_id)
        })
    }
  }

  // Session restoration logic has been extracted to composables/useSession.js (see the useSession call below)


  function getCreateAgentDirectoryNodeId() {
    if (dirDialogContext.value === 'open-dir') {
      return (openDirNodeId.value || '').trim()
    }
    if (dirDialogContext.value === 'orchestrate') {
      return (getOrchestrateNodeId().value || '').trim()
    }
    return (newAgentNodeId.value || '').trim()
  }

  function resetDirectorySelectionState() {
    showDirDialog.value = false
    currentDirPath.value = ''
    dirList.value = []
    selectedDir.value = null
    dirSearchText.value = ''
    selectedDirIndex.value = -1
  }

  watch(newAgentNodeId, (newNodeId) => {
    newAgentDir.value = '~'
    resetDirectorySelectionState()
    // When switching nodes, re-fetch the model-group list of that node (skipped when copying an Agent)
    if (!skipNameWatch.value) {
      fetchModelGroups(newNodeId || 'master')
    }
  }, { flush: 'sync' })

  async function openDirDialog() {
    // All three scenarios (create Agent / open directory / orchestration workdir selection) show directory selection in a standalone dialog
    const isOpenDir = dirDialogContext.value === 'open-dir'
    showDirDialog.value = true
    if (isOpenDir) {
      // "Open directory": browse from the root, and after confirming, fill the result back into the "Open directory" overlay
      selectedDir.value = '~'
    } else if (dirDialogContext.value === 'orchestrate') {
      // Orchestration scenario: browse from the node selected in the orchestration dialog; the initial path is the workdir of the Agent currently being edited
      const active = getOrchestrateAgents().value[getOrchestrateActiveIndex().value]
      selectedDir.value = (active && active.workingDir) || '~'
    } else {
      dirDialogContext.value = 'create-agent'
      selectedDir.value = newAgentDir.value || '~'
    }
    dirSearchText.value = '' // Clear the search
    selectedDirIndex.value = -1
    await fetchDirectories(selectedDir.value)
    // Focus the search box automatically on PC; do not focus on mobile
    if (windowWidth.value > 768) {
      nextTick(() => {
        dirSearchInput.value?.focus()
      })
    }
  }

  async function fetchDirectories(path = '') {
    try {
      const { host, port } = getGatewayAddress()
      const params = new URLSearchParams({ path })
      const nodeId = String(getCreateAgentDirectoryNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, nodeId, `directories?${params.toString()}`))

      if (!response.ok) {
        const error = await response.json()
        console.error('[DIR] Failed to fetch directory list:', error)
        alert(`Failed to fetch directory list: ${error.error?.message || 'Unknown error'}`)
        return
      }

      const result = await response.json()
      if (result.success && result.data) {
        currentDirPath.value = result.data.current_path
        // Show directories only, filtering out files (the workdir picker does not need to show files)
        dirList.value = (result.data.items || []).filter(item => item.type === 'directory')
      }
    } catch (error) {
      console.error('[DIR] Error fetching directory list:', error)
      alert(`Error fetching directory list: ${error.message}`)
    }
  }

  function selectDirectory(path) {
    selectedDir.value = path
    // Also update the index
    const index = filteredDirList.value.findIndex(dir => dir.path === path)
    if (index !== -1) {
      selectedDirIndex.value = index
    }
  }

  // Handle keyboard events on the directory search box
  function handleDirSearchKeydown(event) {
    const maxIndex = filteredDirList.value.length - 1

    if (event.key === 'Escape') {
      // ESC closes the dialog for the current scenario
      if (dirDialogContext.value === 'open-dir') {
        closeOpenDirDialog()
      } else {
        cancelDirDialog()
      }
      event.preventDefault()
      return
    }

    // With Ctrl/Alt/Meta modifiers, let the global shortcuts handle it; do not navigate the list
    if (event.ctrlKey || event.altKey || event.metaKey) return

    if (event.key === 'ArrowDown') {
      // ArrowDown: select the next directory
      if (selectedDirIndex.value < maxIndex) {
        selectedDirIndex.value++
      } else if (selectedDirIndex.value === -1) {
        selectedDirIndex.value = 0
      }
      // Also set the selected directory as selectedDir
      if (selectedDirIndex.value >= 0 && selectedDirIndex.value <= maxIndex) {
        selectedDir.value = filteredDirList.value[selectedDirIndex.value].path
      }
      // Scroll to the selected item
      scrollToDirSelected()
      event.preventDefault()
      return
    }

    if (event.key === 'ArrowUp') {
      // ArrowUp: select the previous directory
      if (selectedDirIndex.value > 0) {
        selectedDirIndex.value--
      } else if (selectedDirIndex.value === -1) {
        selectedDirIndex.value = maxIndex
      } else {
        // Moving up again from item 0: return to the "unselected" state; selectedDir must be
        // cleared in sync, otherwise Enter would treat a stale selectedDir as "confirm the
        // current selection" instead of "enter the directory"
        selectedDirIndex.value = -1
        selectedDir.value = null
      }
      // Also set the selected directory as selectedDir
      if (selectedDirIndex.value >= 0 && selectedDirIndex.value <= maxIndex) {
        selectedDir.value = filteredDirList.value[selectedDirIndex.value].path
      }
      // Scroll to the selected item
      scrollToDirSelected()
      event.preventDefault()
      return
    }

    if (event.key === 'Enter') {
      // Enter: if a list item is selected, enter that directory; otherwise confirm the current selection
      if (selectedDirIndex.value >= 0 && selectedDirIndex.value <= maxIndex) {
        // A list item is selected; enter that directory
        const selectedPath = filteredDirList.value[selectedDirIndex.value].path
        selectDirectory(selectedPath)
        enterDirectory(selectedPath)
        event.preventDefault()
      } else if (selectedDir.value) {
        // No list item is selected, but a directory is already chosen; confirm the current selection
        if (dirDialogContext.value === 'open-dir') {
          // "Open directory" scenario: open directly with the currently selected directory
          confirmOpenDir()
        } else {
          confirmDirectory()
        }
        event.preventDefault()
      }
      return
    }
  }

  async function enterDirectory(path, shouldFocus = true) {
    await fetchDirectories(path)
    // Clear the search
    dirSearchText.value = ''
    selectedDirIndex.value = -1
    // Decide whether to focus the search box based on the parameter
    if (shouldFocus) {
      nextTick(() => {
        dirSearchInput.value?.focus()
      })
    }
  }

  async function goToParentDir() {
    try {
      // Path handling in the browser environment
      const normalizedPath = currentDirPath.value.replace(/\\/g, '/')
      const parts = normalizedPath.split('/').filter(p => p)

      if (parts.length > 0) {
        parts.pop() // Remove the last part
        const parentPath = '/' + parts.join('/')
        await fetchDirectories(parentPath)
      }
    } catch (error) {
      console.error('[DIR] Failed to go to the parent directory:', error)
    }
  }

  async function confirmDirectory() {
    if (selectedDir.value) {
      if (dirDialogContext.value === 'open-dir') {
        // "Open directory" scenario: fill the selected directory back into the "Open directory" overlay without closing it
        openDirPath.value = selectedDir.value
      } else if (dirDialogContext.value === 'orchestrate') {
        // Orchestration scenario: fill the selected directory into the workdir of the current Agent tab
        const active = getOrchestrateAgents().value[getOrchestrateActiveIndex().value]
        if (active) active.workingDir = selectedDir.value
      } else {
        newAgentDir.value = selectedDir.value
      }
      // Save the workdir to history (separated by node)
      saveRecentWorkDir(selectedDir.value, getCreateAgentDirectoryNodeId())
      showDirDialog.value = false
    }
  }

  function cancelDirDialog() {
    showDirDialog.value = false
    selectedDir.value = null
    dirSearchText.value = ''
    selectedDirIndex.value = -1
    // Reset the scenario so later "Choose directory" for creating an Agent is not misinterpreted as the "Open directory"/"Orchestration" scenario
    dirDialogContext.value = 'create-agent'
  }

  // Open the create-Agent dialog (an initial node can be specified, e.g. from double-clicking a node in the lobby)
  async function openCreateAgentModal(initialNodeId = '') {
    // Refresh the model-group list first to ensure the latest configuration
    await Promise.all([
      fetchModelGroups(),
      fetchNodeStatus(),
      fetchUserList(),
      fetchUserAccessibleNodes(),
    ])
    // Load recently used working directories
    loadRecentWorkDirs()
    const target = typeof initialNodeId === 'string' ? initialNodeId.trim() : ''
    // Verify the target node is in the creatable range; otherwise fall back to the default node (master)
    const allowed = filteredNodeOptionsForCreateAgent.value.some(n => n.node_id === target)
    newAgentNodeId.value = allowed ? target : getDefaultCreateAgentNodeId()
    newAgentDir.value = '~'
    newAgentCreateError.value = ''
    resetDirectorySelectionState()
    showCreateAgentModal.value = true
  }

  // Double-clicking a node in the lobby: open the create-Agent dialog and preselect that node
  function onLobbyCreateAgentOnNode(nodeId) {
    openCreateAgentModal(nodeId)
  }

  // Fetch the model-group list
  async function fetchModelGroups(nodeId = 'master', autoSelect = true) {
    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(nodeId || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'model-groups'))
      if (!response.ok) {
        console.error('[MODEL GROUP] Failed to fetch the model-group list:', response.status)
        return
      }
      const result = await response.json()
      if (result.success && result.data) {
        modelGroups.value = result.data
        // If the model-group list is not empty, prefer the configured default model group
        if (autoSelect && modelGroups.value.length > 0) {
          const defaultGroup = result.default_llm_group || ''
          const hasDefaultGroup = defaultGroup && modelGroups.value.some(g => g.name === defaultGroup)
          const hasCurrentGroup = modelGroups.value.some(g => g.name === newAgentModelGroup.value)
          if (hasDefaultGroup) {
            // Use the configured default model group
            newAgentModelGroup.value = defaultGroup
          } else if (!hasCurrentGroup) {
            // If there is no default model group or it is not in the list, select the first one
            newAgentModelGroup.value = modelGroups.value[0].name
          }
        }
      }
    } catch (error) {
      console.error('[MODEL GROUP] Error fetching the model-group list:', error)
    }
  }

  async function fetchUserAccessibleNodes() {
    try {
      const { host, port } = getGatewayAddress()
      const userId = auth.value.userInfo?.user_id
      if (!userId) { userAccessibleNodes.value = []; return }
      const response = await fetchWithAuth(`${getHttpProtocol()}://${host}:${port}/api/permissions/user/${encodeURIComponent(userId)}/accessible-nodes`)
      if (!response.ok) {
        console.warn('[PERM] Failed to fetch accessible nodes:', response.status)
        userAccessibleNodes.value = []
        return
      }
      const result = await response.json()
      if (result.success && result.data) {
        userAccessibleNodes.value = result.data.accessible_nodes || []
      } else {
        userAccessibleNodes.value = []
      }
    } catch (error) {
      console.error('[PERM] Error fetching accessible nodes:', error)
      userAccessibleNodes.value = []
    }
  }

  // Fetch the current user's permissions (allowed/denied are permission pattern lists)
  async function fetchUserPermissions() {
    try {
      const { host, port } = getGatewayAddress()
      const userId = auth.value.userInfo?.user_id
      if (!userId) { userPermissions.value = { allowed: [], denied: [] }; return }
      const response = await fetchWithAuth(`${getHttpProtocol()}://${host}:${port}/api/permissions/user/${encodeURIComponent(userId)}`)
      if (!response.ok) {
        console.warn('[PERM] Failed to fetch user permissions:', response.status)
        userPermissions.value = { allowed: [], denied: [] }
        return
      }
      const result = await response.json()
      if (result.success && result.data?.permissions) {
        userPermissions.value = {
          allowed: result.data.permissions.allowed || [],
          denied: result.data.permissions.denied || []
        }
      } else {
        userPermissions.value = { allowed: [], denied: [] }
      }
    } catch (error) {
      console.error('[PERM] Error fetching user permissions:', error)
      userPermissions.value = { allowed: [], denied: [] }
    }
  }

  // Permission pattern matching: supports '*:*', exact matches, and 'prefix:*' wildcards
  function matchPermissionPattern(pattern, permission) {
    if (!pattern || !permission) return false
    if (pattern === '*:*' || pattern === permission) return true
    const parts = String(pattern).split(':')
    if (parts.length === 2 && parts[1] === '*') {
      return String(permission).startsWith(parts[0] + ':')
    }
    return false
  }

  // Determine whether the current user has the given permission (admins pass directly; denied takes precedence over allowed)
  function hasPermission(permission) {
    if (!permission) return false
    if (auth.value.userInfo?.is_admin) return true
    const perms = userPermissions.value
    if (!perms) return false
    const denied = Array.isArray(perms.denied) ? perms.denied : []
    if (denied.some(p => matchPermissionPattern(p, permission))) return false
    const allowed = Array.isArray(perms.allowed) ? perms.allowed : []
    return allowed.some(p => matchPermissionPattern(p, permission))
  }

  async function fetchNodeStatus() {
    try {
      const { host, port } = getGatewayAddress()
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, 'master', 'node/status'))
      if (!response.ok) {
        console.warn('[NODE] Failed to get node status:', response.status)
        availableNodeOptions.value = []
        return
      }
      const result = await response.json()
      const nodes = Array.isArray(result?.data?.nodes) ? result.data.nodes : []
      const processedNodes = nodes
        .filter(node => node && String(node.node_id || '').trim())
        .map(node => ({
          ...node,
          node_id: String(node.node_id || '').trim(),
        }))
      // Ensure the master node is always in the option list
      if (!processedNodes.some(n => n.node_id === 'master')) {
        processedNodes.unshift({ node_id: 'master', status: 'running' })
      }
      availableNodeOptions.value = processedNodes
    } catch (error) {
      console.error('[NODE] Error getting node status:', error)
      availableNodeOptions.value = []
    }
  }

  // Periodically refresh node status (so offline nodes are reflected in the topology promptly)
  let nodeStatusRefreshInterval = null

  function startNodeStatusRefresh() {
    if (nodeStatusRefreshInterval) {
      clearInterval(nodeStatusRefreshInterval)
    }
    // Refresh every 10 seconds (node status changes infrequently; a wider interval reduces requests)
    nodeStatusRefreshInterval = setInterval(() => {
      fetchNodeStatus()
    }, 10000)
  }

  function stopNodeStatusRefresh() {
    if (nodeStatusRefreshInterval) {
      clearInterval(nodeStatusRefreshInterval)
      nodeStatusRefreshInterval = null
    }
  }

  async function fetchUserList() {
    try {
      const { host, port } = getGatewayAddress()
      const response = await fetchWithAuth(`${getHttpProtocol()}://${host}:${port}/api/users/brief`)
      if (!response.ok) {
        console.warn('[USER] Failed to get the user list:', response.status)
        availableUserOptions.value = []
        return
      }
      const result = await response.json()
      availableUserOptions.value = result?.data?.users || []
    } catch (err) {
      console.warn('[USER] Error getting the user list:', err)
      availableUserOptions.value = []
    }
  }

  function formatNodeOptionLabel(node) {
    const nodeId = String(node?.node_id || '').trim()
    const displayName = getNodeDisplayName(nodeId)
    const status = String(node?.status || node?.runtime_status || '').trim()
    return status ? `${displayName} (${status})` : displayName
  }

  function getDefaultTerminalNodeId(nodes = []) {
    if (nodes.some(node => node.node_id === 'master')) {
      return 'master'
    }
    return nodes[0]?.node_id || ''
  }

  watch(availableNodeOptions, (nodes) => {
    const hasSelectedNode = nodes.some(node => node.node_id === selectedTerminalNodeId.value)
    if (!hasSelectedNode) {
      selectedTerminalNodeId.value = getDefaultTerminalNodeId(nodes)
    }
  }, { immediate: true })

  function getAgentNodeLabel(agent) {
    return String(agent?.node_id || '').trim() || 'master'
  }

  // Display name of the node an Agent belongs to (custom display names take priority); for UI display only
  function getAgentNodeDisplayLabel(agent) {
    return getNodeDisplayName(getAgentNodeLabel(agent))
  }

  function getAgentProxyNodeLabel(agent) {
    return String(agent?.proxy_node || '').trim()
  }

  function getCurrentAgentNodeId() {
    return String(currentAgent.value?.node_id || '').trim()
  }

  // Get the editor target node ID (prefer the node ID of the agent the editor belongs to)
  function getWorkspaceTargetNodeId() {
    const workspaceAgentNodeId = activeWorkspaceSession.value?.agent?.node_id
    return String(workspaceAgentNodeId || getCurrentAgentNodeId() || 'master').trim() || 'master'
  }

  // Validation: no two code_agents without an enabled worktree may share the same node and working directory.
  // Returns a conflict message; returns an empty string when there is no conflict.
  function checkCodeAgentDirConflict({ agentType, worktree, workingDir, nodeId }) {
    if (agentType !== 'code_agent' || worktree) return ''
    const targetNodeId = String(nodeId || 'master').trim() || 'master'
    const normalizedDir = String(workingDir || '').trim()
    const conflictingAgent = agentList.value.find(agent => {
      if (isStoppedAgent(agent)) return false  // Stopped agents do not conflict
      if (agent.agent_type !== 'code_agent') return false
      if (agent.worktree) return false  // Agents with an enabled worktree do not conflict
      const agentNodeId = String(agent.node_id || '').trim() || 'master'
      if (agentNodeId !== targetNodeId) return false
      if (agent.working_dir?.trim() !== normalizedDir) return false
      return true
    })
    if (!conflictingAgent) return ''
    const conflictName = conflictingAgent.name || conflictingAgent.agent_id || 'Unnamed'
    return `Working directory conflict: node ${targetNodeId} already has a code Agent "${conflictName}" without worktree enabled.\nOnly one code Agent without worktree can share the same working directory.\nPlease enable worktree or choose another working directory.`
  }

  // Parameterized Agent creation: only validates and sends the request, returning { ok, agent, error }; no UI side effects.
  // Shared by the "New Agent" dialog and "one-liner creation".
  async function createAgentWithOptions(options = {}) {
    const {
      agentType = 'agent',
      workingDir = '~',
      name = '',
      llmGroup = 'default',
      worktree = false,
      quickMode = false,
      restoreSession = false,
      noInteractionMode = false,
      task = '',
      nodeId = '',
      proxyNode = '',
      accessAclRead = [],
      accessAclInteract = [],
      toolGroup = '',
      configFile = '',
      additionalArgs = '',
    } = options

    const trimmedDir = String(workingDir || '').trim()
    if (!trimmedDir) return { ok: false, error: 'Working directory cannot be empty' }
    const trimmedTask = String(task || '').trim()
    if (noInteractionMode && !trimmedTask) {
      return { ok: false, error: 'A task description is required in no-interaction mode' }
    }
    const conflict = checkCodeAgentDirConflict({
      agentType,
      worktree: agentType === 'code_agent' ? worktree : false,
      workingDir: trimmedDir,
      nodeId,
    })
    if (conflict) return { ok: false, error: conflict }

    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(nodeId || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'agents'), {
        method: 'POST',
        body: JSON.stringify({
          agent_type: agentType,
          working_dir: trimmedDir,
          name: name || undefined,
          llm_group: llmGroup,
          worktree: agentType === 'code_agent' ? worktree : false,
          quick_mode: quickMode,
          restore_session: restoreSession,
          no_interaction_mode: noInteractionMode,
          task: trimmedTask || undefined,
          node_id: targetNodeId,
          proxy_node: proxyNode || undefined,
          access_acl: (accessAclRead.length || accessAclInteract.length) ? {
            read: accessAclRead,
            interact: accessAclInteract,
          } : undefined,
          // Fields specific to the orchestration scenario: only written to the body when non-empty, to avoid overriding backend defaults
          tool_group: String(toolGroup || '').trim() || undefined,
          config_file: String(configFile || '').trim() || undefined,
          additional_args: String(additionalArgs || '').trim() || undefined,
        })
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        return { ok: false, error: error.error?.message || error.detail || 'Unknown error' }
      }
      const result = await response.json()
      if (!result.success || !result.data) {
        return { ok: false, error: 'Invalid response data format' }
      }
      const agent = {
        ...result.data,
        node_id: String(result.data?.node_id || '').trim() || 'master',
      }
      return { ok: true, agent }
    } catch (error) {
      console.error('[AGENT] Create failed:', error)
      return { ok: false, error: error.message }
    }
  }

  // Common finalization after successful creation: add to the list, refresh, open a Panel or stay in the lobby per the current scenario, and show the guide.
  async function afterAgentCreated(agent) {
    // Add to the start of the list (so newly created agents come first)
    agentList.value.unshift(agent)
    // If currently in the pet lobby (no visible Panel), stay in the lobby instead of switching to a Panel;
    // otherwise (a Panel is already open) open the Agent in a new Panel as before
    if (!hasNoPanel.value) {
      await openAgentInPanel(agent)
    }
    // Refresh the list
    await fetchAgentList()
    // Start the periodic list refresh
    startAgentListRefresh()
    // Show the Agent-scenario guide after the first Agent is created.
    // openAgentInPanel schedules the Panel-scenario guide in a next tick; registering another
    // nextTick here (registered later, so its callback runs later) lets the Agent guide clear the
    // Panel guide's timer and be displayed first, preventing the stronger "create Agent" guide
    // from being swallowed by the Panel guide.
    nextTick(() => maybeStartTour('agent'))
  }

  async function createAgent() {
    if (!newAgentDir.value.trim()) return
    // A task description is required in no-interaction mode
    if (newAgentNoInteractionMode.value && !newAgentTaskDescription.value.trim()) {
      alert('A task description is required in no-interaction mode')
      return
    }
    const result = await createAgentWithOptions({
      agentType: newAgentType.value,
      workingDir: newAgentDir.value,
      name: newAgentName.value,
      llmGroup: newAgentModelGroup.value,
      worktree: newCodeAgentWorktree.value,
      quickMode: newAgentQuickMode.value,
      restoreSession: newAgentRestoreSession.value,
      noInteractionMode: newAgentNoInteractionMode.value,
      // The task description is unrelated to no-interaction mode: pass it whenever filled in (no-interaction mode only additionally requires the task)
      task: newAgentTaskDescription.value,
      nodeId: newAgentNodeId.value,
      proxyNode: newAgentProxyNode.value,
      accessAclRead: newAgentAccessAclRead.value,
      accessAclInteract: newAgentAccessAclInteract.value,
    })
    if (!result.ok) {
      // Workdir conflict messages go to the in-dialog error area; the rest go through alert (preserving the original behavior)
      if (result.error && result.error.includes('Working directory conflict')) {
        newAgentCreateError.value = result.error
      } else {
        alert(`Creation failed: ${result.error}`)
      }
      return
    }
    // Close the create dialog
    showCreateAgentModal.value = false
    newAgentDir.value = '~' // Reset to the default value
    newAgentCreateError.value = '' // Reset the error message
    newCodeAgentWorktree.value = false
    newAgentQuickMode.value = false
    newAgentRestoreSession.value = false
    newAgentNoInteractionMode.value = false
    newAgentTaskDescription.value = ''
    newAgentNodeId.value = getDefaultCreateAgentNodeId()
    newAgentAccessAclRead.value = []
    newAgentAccessAclInteract.value = []
    // Reset to the default name (based on the currently selected agent type)
    newAgentName.value = generateAgentName(newAgentType.value)
    await afterAgentCreated(result.agent)
  }
  // Open the "one-liner create Agent" dialog (defaults for everything except the task)
  function openQuickCreateAgent() {
    quickCreateAgentError.value = ''
    quickCreateAgentLoading.value = false
    showQuickCreateAgentModal.value = true
    getPushOverlayState()()
  }

  // Switch from "one-liner creation" to the full creation panel: close the quick dialog and open the full one
  async function openFullCreateAgentFromQuick() {
    showQuickCreateAgentModal.value = false
    await openCreateAgentModal()
  }

  // Submit "one-liner create Agent": the Agent runs the task right after creation while keeping interactive confirmation (no_interaction_mode=false)
  async function submitQuickCreateAgent({ task, agentType = 'agent', workingDir = '~' } = {}) {
    const trimmedTask = String(task || '').trim()
    if (!trimmedTask) return
    quickCreateAgentLoading.value = true
    quickCreateAgentError.value = ''
    try {
      const result = await createAgentWithOptions({
        agentType,
        workingDir,
        name: generateAgentName(agentType),
        llmGroup: 'default',
        noInteractionMode: false,
        task: trimmedTask,
        nodeId: 'master',
      })
      if (!result.ok) {
        quickCreateAgentError.value = result.error || 'Creation failed'
        return
      }
      showQuickCreateAgentModal.value = false
      await afterAgentCreated(result.agent)
    } finally {
      quickCreateAgentLoading.value = false
    }
  }
  // Open the completion list
  async function openCompletions() {
    if (!currentAgent.value) {
      alert('Please select an Agent first')
      return
    }

    completionAgentId.value = currentAgentId.value
    completionSearch.value = ''
    selectedIndex.value = -1
    showCompletions.value = true

    // Fetch the completion list
    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `completions/${currentAgent.value.agent_id}`))

      const result = await response.json()

      if (!response.ok) {
        alert(`Failed to fetch the completion list: ${result.error?.message || result.detail || 'Unknown error'}`)
        return
      }

      if (result.success && result.data) {
        completions.value = sortCompletionItems(result.data)
      } else {
        console.error('[COMPLETIONS] Invalid format:', result)
        alert('Failed to fetch the completion list: invalid response data format')
      }
    } catch (error) {
      console.error('[COMPLETIONS] Fetch failed:', error)
      alert(`Failed to fetch the completion list: ${error.message}`)
    }

    // Focus the search box on PC; do not focus on mobile
    if (windowWidth.value > 768) {
      nextTick(() => {
        completionSearchInput.value?.focus()
      })
    }
  }

  // Filter the completion list
  const filteredCompletions = computed(() => {
    if (!completionSearch.value) {
      return sortCompletionItems(completions.value)
    }

    const search = completionSearch.value.toLowerCase()
    // Filter the original completion items
    const filteredOriginal = completions.value.filter(item => {
      const displayText = String(item.display || '').toLowerCase()
      const descriptionText = String(item.description || '').toLowerCase()
      const valueText = String(item.value || '').toLowerCase()
      return displayText.includes(search) || descriptionText.includes(search) || valueText.includes(search)
    })

    // Merge file completion results (if there is a search term)
    if (fileCompletions.value.length > 0) {
      return sortCompletionItems([...filteredOriginal, ...fileCompletions.value])
    }

    return sortCompletionItems(filteredOriginal)
  })

  // Close the completions dialog (cancel selection): keep the @ symbol when it was triggered by typing @; insert nothing when triggered by a button
  function closeCompletionsWithoutSelect() {
    if (completionHasAtSymbol.value && completionSource.value !== 'lobby') {
      insertAtPosition('@', completionCursorPos.value, completionAgentId.value)
    }
    showCompletions.value = false
    selectedIndex.value = -1
    completionCursorPos.value = -1
    completionHasAtSymbol.value = false
    completionAgentId.value = null
    completionSource.value = 'panel'
  }

  // Handle keyboard events on the completions dialog
  function handleCompletionKeydown(event) {
    const maxIndex = filteredCompletions.value.length - 1

    if (event.key === 'Escape') {
      // ESC closes the dialog
      closeCompletionsWithoutSelect()
      event.preventDefault()
      return
    }

    // With Ctrl/Alt/Meta modifiers, let the global shortcuts handle it; do not navigate the list
    if (event.ctrlKey || event.altKey || event.metaKey) return

    if (event.key === 'ArrowDown') {
      // ArrowDown: select the next item
      if (selectedIndex.value < maxIndex) {
        selectedIndex.value++
      } else if (selectedIndex.value === -1) {
        selectedIndex.value = 0
      }
      scrollToSelected()
      event.preventDefault()
      return
    }

    if (event.key === 'ArrowUp') {
      // ArrowUp: select the previous item
      if (selectedIndex.value > 0) {
        selectedIndex.value--
      } else if (selectedIndex.value === -1) {
        selectedIndex.value = maxIndex
      } else {
        selectedIndex.value = -1
      }
      scrollToSelected()
      event.preventDefault()
      return
    }

    if (event.key === 'Enter') {
      // Enter: if an item is selected, insert it
      if (selectedIndex.value >= 0 && selectedIndex.value <= maxIndex) {
        insertCompletion(filteredCompletions.value[selectedIndex.value], completionAgentId.value)
        event.preventDefault()
      }
      return
    }
  }

  // Scroll to the selected item
  function scrollToSelected() {
    nextTick(() => {
      const modal = completionsModalRef.value
      if (!modal) return
      const selectedItem = modal.itemRefs?.[selectedIndex.value]
      if (selectedItem) {
        selectedItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      }
    })
  }

  // Scroll to the selected directory item
  function scrollToDirSelected() {
    nextTick(() => {
      // "Open directory" uses the inline DirectoryDialog; "Create Agent" uses a separate modal
      const dialog = dirDialogContext.value === 'open-dir' ? openDirDialogRef.value : dirDialogRef.value
      if (!dialog) return
      const listContainer = dialog.dirListRef
      if (!listContainer) return

      // Find the DOM element of the selected item
      const items = listContainer.querySelectorAll('.dir-item')
      const selectedItem = items[selectedDirIndex.value]
      if (selectedItem) {
        selectedItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      }
    })
  }

  // Find the session input textarea: the same Agent may have multiple instances (the grid version
  // and the editor-embedded version); duplicates hidden by v-show remain in the DOM and come first,
  // so a plain querySelector would hit one whose focus() is a no-op (display:none elements cannot
  // receive focus), leaving focus unable to return to the input after completion.
  // Therefore prefer the visible instance and fall back to the first match only when none are visible.
  function findVisiblePanelTextarea(agentId) {
    const selector = agentId
      ? `.input-wrapper textarea[data-agent-id="${agentId}"]`
      : '.input-wrapper textarea'
    const candidates = Array.from(document.querySelectorAll(selector))
    const visible = candidates.find(el => el.getClientRects().length > 0)
    return visible || candidates[0] || null
  }

  // Insert text at the specified position
  function insertAtPosition(text, position, agentId = null) {
    const targetAgentId = agentId || currentAgentId.value
    const textarea = findVisiblePanelTextarea(targetAgentId)
    if (!textarea || position === -1) return

    const currentText = targetAgentId
      ? (panelInputTexts.value.get(targetAgentId) || '')
      : inputText.value
    // Insert text at the specified position
    const newText = currentText.substring(0, position) + text + currentText.substring(position)
    if (targetAgentId) {
      panelInputTexts.value.set(targetAgentId, newText)
    }
    inputText.value = newText

    // Update the textarea and set the cursor position
    textarea.value = newText
    const newCursorPos = position + text.length
    textarea.setSelectionRange(newCursorPos, newCursorPos)
    textarea.focus()
  }
  // Insert the selected completion
  function insertCompletion(item, agentId = null) {
    const targetAgentId = agentId || currentAgentId.value

    // From the pet lobby: write back to PetLobby's internal input box
    if (completionSource.value === 'lobby') {
      recordCompletionSelection(item)
      petLobbyRef.value?.insertCompletionText?.(
        targetAgentId,
        item.value,
        completionCursorPos.value,
        completionHasAtSymbol.value,
      )
      showCompletions.value = false
      selectedIndex.value = -1
      completionCursorPos.value = -1
      completionHasAtSymbol.value = false
      completionAgentId.value = null
      completionSource.value = 'panel'
      return
    }

    const textarea = findVisiblePanelTextarea(targetAgentId)

    // The source of truth is panelInputTexts / inputText; the textarea is only used to sync the cursor.
    // On mobile, tapping a completion may leave the textarea blurred or even unfindable;
    // that alone must not abort the insertion.
    const text = targetAgentId
      ? (panelInputTexts.value.get(targetAgentId) || '')
      : (textarea ? textarea.value : inputText.value)

    recordCompletionSelection(item)

    // Completions triggered by typing @: delete the @ symbol; completions triggered by a button: there is no @ in the input, so just insert at the cursor
    let deleteStart
    if (completionHasAtSymbol.value && completionCursorPos.value !== -1) {
      deleteStart = completionCursorPos.value
    } else {
      // No @ to delete: prefer the cursor position recorded when the completion was opened; otherwise fall back to the end
      deleteStart = completionCursorPos.value === -1 ? text.length : completionCursorPos.value
    }
    if (deleteStart > text.length) deleteStart = text.length

    // Insert the completion at deleteStart (wrapping the value in single quotes)
    const valueToInsert = `'${item.value}'`
    const newText = text.substring(0, deleteStart) + valueToInsert + text.substring(deleteStart)
    if (targetAgentId) {
      // Replace the whole Map to trigger Vue reactivity (Map.set does not)
      const nextMap = new Map(panelInputTexts.value)
      nextMap.set(targetAgentId, newText)
      panelInputTexts.value = nextMap
    }
    inputText.value = newText

    // Sync the DOM and cursor position (only when the textarea exists)
    if (textarea) {
      textarea.value = newText
      const newCursorPos = deleteStart + valueToInsert.length
      textarea.setSelectionRange(newCursorPos, newCursorPos)
      textarea.focus()
    }

    // Close the dialog
    showCompletions.value = false
    selectedIndex.value = -1
    completionCursorPos.value = -1
    completionHasAtSymbol.value = false
    completionAgentId.value = null
  }

  // Fetch the Agent list
  async function fetchAgentList() {
    try {
      const { host, port } = getGatewayAddress()
      // Always use the 'master' node to fetch the agent list across all nodes
      const targetNodeId = 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'agents'))

      if (!response.ok) return

      const result = await response.json()


      // Update the list (backend response format: { success: true, data: agents })
      if (result.success && result.data) {
        // Reverse the array so newly created agents come first
        agentList.value = result.data.slice().reverse().map(agent => ({
          ...agent,
          node_id: String(agent?.node_id || '').trim() || 'master',
        }))

        // Ensure every online agent has a connection (internally skips already-connected ones, so
        // repeated calls are safe), letting agents that were never clicked also receive status updates.
        getAutoConnectToOnlineAgents()()

        // Actively sync the execution status of online agents (e.g. waiting for input),
        // so a missed WebSocket push does not leave the status stuck at running.
        syncOnlineAgentStatuses()

        // After the first Agent fetch, auto-open the editor (the single container) so the user
        // lands directly in the workspace; when there are no Agents, keep it closed to reveal the
        // pet lobby as a welcome page.
        if (!workspaceAutoOpened && agentList.value.length > 0) {
          workspaceAutoOpened = true
          showWorkspacePanel.value = true
        }
      }

      // Update the current Agent status
      const currentAgent = agentList.value.find(a => a.agent_id === currentAgentId.value)
      if (currentAgent && currentAgent.status !== 'running') {
      }
    } catch (error) {
      console.error('[AGENT] Fetch list failed:', error)
    } finally {
      // After the first fetch finishes (success or failure), release the lobby empty-state guide to prevent it flashing when Agents exist
      agentListLoaded.value = true
      // After the first Agent-list fetch, restore each pane's content (stage B; idempotent, runs once).
      // Runs only when the socket is connected: content restoration depends on auth capabilities such as filesystem/Git/terminal.
      if (socket.value) {
        restoreWorkspacePaneContents()
      }
    }
  }

  // Build the request payload for copying an Agent
  function buildCopiedAgentPayload(agent, copiedName, targetNodeId = undefined) {
    return {
      agent_type: agent.agent_type,
      working_dir: agent.working_dir,
      name: copiedName,
      llm_group: agent.llm_group || 'default',
      worktree: agent.agent_type === 'code_agent' ? Boolean(agent.worktree) : false,
      quick_mode: Boolean(agent.quick_mode),
      restore_session: Boolean(agent.restore_session),
      no_interaction_mode: Boolean(agent.no_interaction_mode),
      task: agent.task || '',
      node_id: targetNodeId || agent.node_id || undefined,
      proxy_node: agent.proxy_node || undefined,
    }

  }

  // Copy an Agent - open the create panel with pre-filled parameters
  async function copyAgent(agent) {
    // Set the flag first to skip the name-setting and automatic model-group selection in the watchers
    skipNameWatch.value = true

    // Refresh the model-group list and node status (without auto-selecting a model group)
    await Promise.all([
      fetchModelGroups(agent?.node_id || 'master', false),
      fetchNodeStatus(),
      fetchUserList(),
      fetchUserAccessibleNodes(),
    ])

    // Fill in the form variables
    newAgentType.value = agent.agent_type || 'code_agent'
    newAgentModelGroup.value = agent.llm_group || 'default'
    newCodeAgentWorktree.value = agent.agent_type === 'code_agent' ? Boolean(agent.worktree) : false
    newAgentQuickMode.value = Boolean(agent.quick_mode)
    newAgentRestoreSession.value = Boolean(agent.restore_session)
    newAgentNoInteractionMode.value = Boolean(agent.no_interaction_mode)
    newAgentTaskDescription.value = agent.task || ''
    newAgentProxyNode.value = agent.proxy_node || ''
    // Set node_id first (triggers the watch that resets the directory), then set the correct directory
    newAgentNodeId.value = String(agent?.node_id || '').trim() || getDefaultCreateAgentNodeId()
    newAgentDir.value = agent.working_dir || '~'
    // Set the correct name (Agent type - creation time format)
    newAgentName.value = generateAgentName(agent.agent_type || 'code_agent')

    // Reset the directory selection state
    resetDirectorySelectionState()
    newAgentCreateError.value = ''

    // Open the create dialog
    showCreateAgentModal.value = true

    // Wait for the DOM to update, then reset the flag
    await nextTick()
    skipNameWatch.value = false
  }


  // Batch-copy Agents
  async function batchCopyAgents() {
    const selectedIds = Array.from(selectedAgents.value)
    if (selectedIds.length === 0) {
      showToast('Please select an Agent to copy first', 'warning')
      return
    }
    const selectedAgentList = agentList.value.filter(agent => selectedAgents.value.has(agent.agent_id))
    try {
      let successCount = 0
      let failCount = 0
      for (const agent of selectedAgentList) {
        try {
          const { host, port } = getGatewayAddress()
          const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'
          const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'agents'), {
            method: 'POST',
            body: JSON.stringify(
              buildCopiedAgentPayload(agent, generateAgentName(agent.agent_type || 'code_agent'), targetNodeId)
            )
          })
          if (response.ok) {
            successCount++
          } else {
            failCount++
          }
        } catch (error) {
          console.error(`[AGENT] Failed to copy agent ${agent.agent_id}:`, error)
          failCount++
        }
      }
      await fetchAgentList()
      selectedAgents.value.clear()
      selectedAgents.value = new Set()
      isBatchMode.value = false
      if (failCount === 0) {
        showToast(`Successfully copied ${successCount} Agent(s)`, 'success')
      } else {
        showToast(`Copy finished: ${successCount} succeeded, ${failCount} failed`, 'warning')
      }
    } catch (error) {
      console.error('[AGENT] Batch copy failed:', error)
      showToast('Batch copy failed', 'error')
    }
  }

  // Agent group operations
  // From the pet-lobby right-click menu: add a single Agent to a group or create a new group
  function onLobbyAddAgentToGroup({ agentId, groupId, newGroupName } = {}) {
    if (!agentId) return
    const agent = agentList.value.find(a => a.agent_id === agentId)
    if (!agent) {
      showToast('Agent does not exist', 'error')
      return
    }
    if (isStoppedAgent(agent)) {
      showToast('Stopped Agents cannot be added to a group', 'warning')
      return
    }

    let group = null
    if (groupId) {
      group = agentGroups.value.find(g => g.id === groupId)
      if (!group) {
        showToast('Group does not exist', 'error')
        return
      }
    } else {
      const trimmedName = String(newGroupName || '').trim()
      if (!trimmedName) {
        showToast('Please enter a group name', 'warning')
        return
      }
      group = {
        id: `group-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: trimmedName,
        agentIds: [],
      }
      agentGroups.value.push(group)
    }

    if (!group.agentIds) group.agentIds = []
    if (group.agentIds.includes(agentId)) {
      showToast(`This Agent is already in "${group.name}"`, 'info')
      return
    }
    group.agentIds.push(agentId)
    saveAgentGroups()
    showToast(`Added to "${group.name}"`, 'success')
  }

  // From the pet-lobby right-click menu: remove a single Agent from a group
  function onLobbyRemoveAgentFromGroup({ agentId, groupId } = {}) {
    if (!agentId || !groupId) return
    const group = agentGroups.value.find(g => g.id === groupId)
    if (!group || !Array.isArray(group.agentIds)) return
    const index = group.agentIds.indexOf(agentId)
    if (index === -1) {
      showToast('This Agent is not in this group', 'info')
      return
    }
    group.agentIds.splice(index, 1)
    saveAgentGroups()
    showToast(`Removed from "${group.name}"`, 'success')
  }

  function addSelectedToGroup(groupId) {
    const group = agentGroups.value.find(g => g.id === groupId)
    if (!group) return
    if (!group.agentIds) group.agentIds = []
    // Only add active agents; filter out stopped ones
    const selectedIds = Array.from(selectedAgents.value).filter(agentId => {
      const agent = agentList.value.find(a => a.agent_id === agentId)
      return agent && !isStoppedAgent(agent)
    })
    if (selectedIds.length === 0) {
      showToast('No active Agents available to add to the group', 'warning')
      return
    }
    let added = 0
    selectedIds.forEach(agentId => {
      if (!group.agentIds.includes(agentId)) {
        group.agentIds.push(agentId)
        added++
      }
    })
    saveAgentGroups()
    selectedAgents.value.clear()
    selectedAgents.value = new Set()
    isBatchMode.value = false
    showToast(`Added ${added} Agent(s) to "${group.name}"`, 'success')
  }

  function createGroupWithAgents(name) {
    const trimmedName = String(name || '').trim()
    if (!trimmedName) {
      showToast('Please enter a group name', 'warning')
      return
    }
    const group = {
      id: `group-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name: trimmedName,
      agentIds: [],
    }
    const selectedIds = Array.from(selectedAgents.value).filter(agentId => {
      const agent = agentList.value.find(a => a.agent_id === agentId)
      return agent && !isStoppedAgent(agent)
    })
    selectedIds.forEach(agentId => {
      if (!group.agentIds.includes(agentId)) {
        group.agentIds.push(agentId)
      }
    })
    agentGroups.value.push(group)
    saveAgentGroups()
    selectedAgents.value.clear()
    selectedAgents.value = new Set()
    isBatchMode.value = false
    showToast(`Created group "${group.name}" with ${group.agentIds.length} Agent(s)`, 'success')
  }

  // Rename a group
  function renameAgentGroup({ groupId, name } = {}) {
    if (!groupId) return
    const trimmedName = String(name || '').trim()
    if (!trimmedName) {
      showToast('Group name cannot be empty', 'warning')
      return
    }
    const group = agentGroups.value.find(g => g.id === groupId)
    if (!group) return
    if (group.name === trimmedName) return
    group.name = trimmedName
    saveAgentGroups()
    showToast(`Group renamed to "${trimmedName}"`, 'success')
  }

  // Delete a group (deletes only the group itself; the Agents in it are unaffected)
  function deleteAgentGroup(groupId) {
    if (!groupId) return
    const group = agentGroups.value.find(g => g.id === groupId)
    if (!group) return
    showConfirm(
      `Are you sure you want to delete the group "${group.name}"?`,
      () => {
        const index = agentGroups.value.findIndex(g => g.id === groupId)
        if (index === -1) return
        agentGroups.value.splice(index, 1)
        saveAgentGroups()
        showToast(`Deleted group "${group.name}"`, 'success')
      },
      null,
      false
    )
  }



  // View rules
  async function viewRules(agent) {
    if (!agent || !agent.agent_id) {
      console.warn('[RULES] Invalid agent:', agent)
      return
    }

    rulesLoading.value = true
    showRulesModal.value = true
    rulesContent.value = []
    rulesLoadedContent.value = ''

    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agent/${agent.agent_id}/rules`))

      if (!response.ok) {
        console.warn(`[RULES] Failed to fetch rules for agent ${agent.agent_id}:`, response.status)
        rulesContent.value = []
        rulesLoadedContent.value = ''
        return
      }

      const result = await response.json()
      const rules = result.rules || []
      // Loaded rules go to the top
      rulesContent.value = rules.sort((a, b) => {
        if (a.is_loaded === b.is_loaded) return 0
        return a.is_loaded ? -1 : 1
      })
      rulesLoadedContent.value = result.loaded_rules_content || ''
    } catch (error) {
      console.error('[RULES] Error fetching rules:', error)
      rulesContent.value = []
      rulesLoadedContent.value = ''
    } finally {
      rulesLoading.value = false
    }
  }

  async function exitNonInteractiveMode(agent) {
    if (!agent || !agent.agent_id) {
      console.warn('[EXIT NON-INTERACTIVE] Invalid agent:', agent)
      return
    }

    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agent/${agent.agent_id}/exit_non_interactive`), {
        method: 'POST'
      })

      if (!response.ok) {
        console.warn(`[EXIT NON-INTERACTIVE] Failed for agent ${agent.agent_id}:`, response.status)
        return
      }

      const result = await response.json()
      if (result.success) {
        // Update the local status
        const current = agentStatuses.value.get(agent.agent_id) || {}
        agentStatuses.value.set(agent.agent_id, {...current, non_interactive: false})
      } else {
        console.warn(`[EXIT NON-INTERACTIVE] Failed for agent ${agent.agent_id}:`, result.error || 'Unknown error')
      }
    } catch (error) {
      console.error(`[EXIT NON-INTERACTIVE] Error for agent ${agent.agent_id}:`, error)
    }
  }

  async function viewTools(agent) {
    if (!agent || !agent.agent_id) {
      console.warn('[TOOLS] Invalid agent:', agent)
      return
    }

    toolsLoading.value = true
    showToolsModal.value = true
    toolsContent.value = { all_tools: [], allowed_tools: null }

    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agent/${agent.agent_id}/tools`))

      if (!response.ok) {
        console.warn(`[TOOLS] Failed to fetch tools for agent ${agent.agent_id}:`, response.status)
        toolsContent.value = { all_tools: [], allowed_tools: null }
        return
      }

      const result = await response.json()
      const allTools = result.all_tools || []
      const allowedTools = result.allowed_tools

      // If there are allowed_tools, sort the allowed tools to the top
      if (allowedTools && allowedTools.length > 0) {
        const allowedSet = new Set(allowedTools)
        allTools.sort((a, b) => {
          const aAllowed = allowedSet.has(a.name)
          const bAllowed = allowedSet.has(b.name)
          if (aAllowed && !bAllowed) return -1
          if (!aAllowed && bAllowed) return 1
          return 0
        })
      }

      toolsContent.value = {
        all_tools: allTools,
        allowed_tools: allowedTools
      }
    } catch (error) {
      console.error('[TOOLS] Error fetching tools:', error)
      toolsContent.value = { all_tools: [], allowed_tools: null }
    } finally {
      toolsLoading.value = false
    }
  }



  // Rename an Agent
  function renameAgent(agent) {
    renamingAgent.value = agent
    renameAgentName.value = agent.name || ''
    showRenameAgentModal.value = true

    // Auto-focus the input box
    nextTick(() => {
      if (renameInput.value) {
        renameInput.value.focus()
        // Select all text
        renameInput.value.select()
      }
    })
  }

  // Confirm the rename
  async function confirmRename() {
    const agent = renamingAgent.value
    if (!agent) return

    const newName = renameAgentName.value.trim()

    try {
      const { host, port } = getGatewayAddress()

      const body = newName === '' 
        ? { name: null } 
        : { name: newName }

      const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agents/${agent.agent_id}`), {
        method: 'PATCH',
        body: JSON.stringify({ ...body, node_id: targetNodeId })
      })

      if (!response.ok) {
        const error = await response.json()
        alert(`Rename failed: ${error.error?.message || error.detail || 'Unknown error'}`)
        showRenameAgentModal.value = false
        return
      }

      await fetchAgentList()
      showToast('Rename successful', 'success')
      showRenameAgentModal.value = false
    } catch (error) {
      console.error('[AGENT] Rename failed:', error)
      alert(`Rename failed: ${error.message}`)
      showRenameAgentModal.value = false
    }
  }


  // After a dialog closes, start an auto-focus suppression window:
  // this prevents a pending async status sync (fetchAgentStatus) from stealing focus back to the
  // input box at the moment of closing.
  // Note: this must come after all watched refs and the modalAutoFocusSuppressUntil declaration,
  // otherwise the immediately-evaluated getter at watch registration would hit the let/const
  // temporal dead zone (TDZ) and throw.
  watch([showRenameAgentModal, showEditAccessModal, showCreateAgentModal, showSettingsModal], (values, prevValues) => {
    const anyClosed = values.some((v, i) => !v && prevValues[i])
    if (anyClosed) {
      setModalAutoFocusSuppressUntil(Date.now() + MODAL_AUTOFOCUS_SUPPRESS_MS)
    }
  })

  async function editAgentAccess(agent) {
    editingAccessAgent.value = agent
    const acl = agent.access_acl || {}
    editAccessRead.value = Array.isArray(acl.read) ? [...acl.read] : []
    editAccessInteract.value = Array.isArray(acl.interact) ? [...acl.interact] : []
    showEditAccessModal.value = true
    // Fetch the user list for selection
    await fetchUserList()
  }

  async function saveAgentAccess() {
    const agent = editingAccessAgent.value
    if (!agent) return
    try {
      const { host, port } = getGatewayAddress()
      const targetNodeId = String(agent?.node_id || '').trim() || 'master'
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agents/${agent.agent_id}/access`), {
        method: 'PUT',
        body: JSON.stringify({
          access_acl: {
            read: editAccessRead.value,
            interact: editAccessInteract.value,
          }
        })
      })
      if (!response.ok) {
        const error = await response.json()
        alert(`Permission update failed: ${error.error?.message || error.detail || 'Unknown error'}`)
        return
      }
      await fetchAgentList()
      showToast('Permission update successful', 'success')
      showEditAccessModal.value = false
    } catch (error) {
      console.error('[AGENT] Access update failed:', error)
      alert(`Permission update failed: ${error.message}`)
    }
  }



  // Delete an Agent
  async function deleteAgent(agentId) {
    showConfirm(
      'Delete this Agent? This cannot be undone and all history will be cleared.',
      async () => {
        try {
          const { host, port } = getGatewayAddress()
          const agent = agentList.value.find(item => item.agent_id === agentId)
          const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'

          // First delete the Agent history data on the server
          try {
            const historyKey = `agent_history_${agentId}`
            await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `data/${historyKey}`), {
              method: 'DELETE'
            })
          } catch (historyError) {
            console.warn('[HISTORY] Failed to delete server history for', agentId, ':', historyError.message)
            // A history deletion failure does not affect the subsequent agent deletion flow
          }

          // Delete the Agent
          const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agents/${agentId}`), {
            method: 'DELETE'
          })

          const result = await response.json()

          if (!response.ok || !result.success) {
            alert(`Delete failed: ${result.error?.message || 'Unknown error'}`)
            return
          }


          // Clear this Agent's history
          historyStorage.clearHistoryForAgent(agentId)
          // Prune orphaned messages and oversized history
          historyStorage.pruneHistory()

          // Clear this Agent's file-tree state
          fileTreeState.value.delete(agentId)
          fileTreeExpanded.value.delete(agentId)
          fileTreeLoading.value.delete(agentId)

          // Destroy the Panel(s) of this Agent
          for (const panel of [...panels.value]) {
            if (panel.agentId === agentId) {
              closePanel(panel.id)
            }
          }

          // If it is the current Agent, clear the current Agent ID
          if (currentAgentId.value === agentId) {
            currentAgentId.value = null
            outputs.value = []
            // Clear the currently displayed history offset
            historyOffset.value = 0
            hasMoreHistory.value = true
          }

          // Refresh the list
          await fetchAgentList()
        } catch (error) {
          console.error('[AGENT] Delete failed:', error)
          alert(`Delete failed: ${error.message}`)
        }
      }
    )
  }

  // Lossless Agent regeneration - save session → delete → rebuild → restore session
  async function regenerateAgent(agent) {
    if (!agent || !agent.agent_id) return
    showConfirm(
      `Regenerate Agent "${agent.name || agent.agent_id}" without loss?\n\nIt will save the current session, then delete and rebuild the Agent; the configuration (model group / tool group / task, etc.) will be kept.`,
      async () => {
        try {
          const { host, port } = getGatewayAddress()
          const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'

          // Step 1: save the session
          let sessionFile = null
          try {
            const saveResp = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agent/${agent.agent_id}/sessions/save`), {
              method: 'POST'
            })
            const saveResult = await saveResp.json()
            if (saveResp.ok && saveResult.success) {
              sessionFile = saveResult.session_file || saveResult.data?.session_file || null
            } else {
              console.warn('[REGENERATE] Session save failed:', saveResult)
            }
          } catch (saveError) {
            console.warn('[REGENERATE] Session save error:', saveError.message)
          }

          // Step 2: delete the old Agent
          const delResp = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agents/${agent.agent_id}`), {
            method: 'DELETE'
          })
          const delResult = await delResp.json()
          if (!delResp.ok || !delResult.success) {
            alert(`Regeneration failed (deletion stage): ${delResult.error?.message || 'Unknown error'}`)
            return
          }

          // Record whether the Agent was in a Panel before regeneration, so the original state can be restored afterward
          const originalPanelId = panels.value.find(p => p.agentId === agent.agent_id)?.id || null

          // Clear the local state
          historyStorage.clearHistoryForAgent(agent.agent_id)
          // Prune orphaned messages and oversized history
          historyStorage.pruneHistory()
          fileTreeState.value.delete(agent.agent_id)
          fileTreeExpanded.value.delete(agent.agent_id)
          fileTreeLoading.value.delete(agent.agent_id)
          // Only unbind the Panel from the Agent while keeping the Panel itself, so it can be restored in place after regeneration
          if (originalPanelId) {
            closeAgentInPanel(originalPanelId)
          }
          if (currentAgentId.value === agent.agent_id) {
            currentAgentId.value = null
            outputs.value = []
            historyOffset.value = 0
            hasMoreHistory.value = true
          }

          // Step 3: rebuild with the original configuration (including session restore)
          const payload = {
            agent_type: agent.agent_type,
            working_dir: agent.working_dir,
            name: agent.name || undefined,
            llm_group: agent.llm_group || 'default',
            tool_group: agent.tool_group || 'default',
            config_file: agent.config_file || undefined,
            worktree: agent.agent_type === 'code_agent' ? Boolean(agent.worktree) : false,
            quick_mode: Boolean(agent.quick_mode),
            restore_session: sessionFile || Boolean(agent.restore_session),
            no_interaction_mode: Boolean(agent.no_interaction_mode),
            task: agent.task || undefined,
            node_id: targetNodeId,
            proxy_node: agent.proxy_node || undefined,
            access_acl: agent.access_acl || undefined,
          }
          const createResp = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'agents'), {
            method: 'POST',
            body: JSON.stringify(payload)
          })
          const createResult = await createResp.json()
          if (!createResp.ok || !createResult.success) {
            alert(`Regeneration failed (rebuild stage): ${createResult.error?.message || createResult.detail || 'Unknown error'}`)
            return
          }

          showToast('Agent regenerated without loss', 'success')
          // Refresh the list
          await fetchAgentList()
          // Only reopen the Agent in its original Panel position if it was in a Panel before regeneration
          if (createResult.data && originalPanelId) {
            const newAgent = {
              ...createResult.data,
              node_id: String(createResult.data?.node_id || '').trim() || 'master',
            }
            await openAgentInPanel(newAgent, originalPanelId)
          }
        } catch (error) {
          console.error('[REGENERATE] Failed:', error)
          alert(`Regeneration failed: ${error.message}`)
        }
      }
    )
  }

  // Batch-delete Agents
  async function batchDeleteAgents() {
    const selectedIds = Array.from(selectedAgents.value)
    if (selectedIds.length === 0) {
      showToast('Please select an Agent to delete first', 'warning')
      return
    }
    showConfirm(
      `Delete the ${selectedIds.length} selected Agent(s)? This cannot be undone and all history will be cleared.`,
      async () => {
        try {
          let successCount = 0
          let failCount = 0
          for (const agentId of selectedIds) {
            try {
              const { host, port } = getGatewayAddress()
              const agent = agentList.value.find(item => item.agent_id === agentId)
              const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'

              // First delete the Agent history data on the server
              try {
                const historyKey = `agent_history_${agentId}`
                await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `data/${historyKey}`), {
                  method: 'DELETE'
                })
              } catch (historyError) {
                console.warn('[HISTORY] Failed to delete server history for', agentId, ':', historyError.message)
                // A history deletion failure does not affect the subsequent agent deletion flow
              }

              // Delete the Agent
              const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agents/${agentId}`), {
                method: 'DELETE'
              })
              const result = await response.json()
              if (response.ok && result.success) {
                successCount++
                // Clear this Agent's history
                historyStorage.clearHistoryForAgent(agentId)
                // Prune orphaned messages and oversized history
                historyStorage.pruneHistory()
                // Clear this Agent's file-tree state
                fileTreeState.value.delete(agentId)
                fileTreeExpanded.value.delete(agentId)
                fileTreeLoading.value.delete(agentId)
                // Destroy the Panel(s) of this Agent
                for (const panel of [...panels.value]) {
                  if (panel.agentId === agentId) {
                    closePanel(panel.id)
                  }
                }
                // If it is the current Agent, clear the current Agent ID
                if (currentAgentId.value === agentId) {
                  currentAgentId.value = null
                  outputs.value = []
                  historyOffset.value = 0
                  hasMoreHistory.value = true
                }
              } else {
                failCount++
              }
            } catch (error) {
              console.error(`[AGENT] Failed to delete agent ${agentId}:`, error)
              failCount++
            }
          }

          // Refresh the list
          await fetchAgentList()
          // Clear the selection and exit batch mode
          selectedAgents.value.clear()
          selectedAgents.value = new Set()
          isBatchMode.value = false
          // Show a result toast
          if (failCount === 0) {
            showToast(`Successfully deleted ${successCount} Agent(s)`, 'success')
          } else {
            showToast(`Deletion finished: ${successCount} succeeded, ${failCount} failed`, 'warning')
          }
        } catch (error) {
          console.error('[AGENT] Batch delete failed:', error)
          showToast('Batch delete failed', 'error')
        }
      }
    )
  }

  // Pet lobby: clicking a pet opens that Agent's detail view (opens a panel)
  function onLobbySelectAgent(agentId) {
    const agent = agentList.value.find(a => a.agent_id === agentId)
    if (!agent) return
    openAgentInPanel(agent)
  }

  // Pet lobby: get an Agent's input state (for the lobby pet input box)
  // Returns { mode: 'multi'|'single'|'confirm', tip, preset, isPassword, confirmMessage, confirmDefault }
  function getLobbyInputState(agentId) {
    const statusData = agentStatuses.value.get(agentId)
    const executionStatus = statusData?.execution_status || 'running'
    const confirmData = panelConfirmData.value.get(agentId)
    // Only execution_status determines the confirm state; panelConfirmData is only used to fill in
    // the prompt text and is not an independent trigger, so stale data cannot make the lobby show
    // the default "Please confirm".
    if (executionStatus === 'waiting_confirm') {
      return {
        mode: 'confirm',
        tip: confirmData?.message || 'Please confirm (y/n)',
        preset: '',
        isPassword: false,
        confirmMessage: confirmData?.message || 'Please confirm',
        confirmDefault: confirmData?.defaultConfirm !== false,
        // Whether there is a pending input/confirm request: the lobby uses this to decide whether to auto-focus the input box when a pet is expanded
        hasRequest: true,
      }
    }
    const request = inputRequests.value.get(agentId)
    if (request) {
      return {
        mode: request.mode === 'single' ? 'single' : 'multi',
        tip: request.tip || '',
        preset: request.preset || '',
        isPassword: !!request.is_password,
        confirmMessage: '',
        confirmDefault: true,
        hasRequest: true,
      }
    }
    return { mode: 'multi', tip: '', preset: '', isPassword: false, confirmMessage: '', confirmDefault: true, hasRequest: false }
  }

  // Pet lobby: send input to the given Agent
  // mode: 'multi'|'single' goes through input_result; 'confirm' goes through confirm_result
  // The decision logic matches panel's sendFromPanel: based on execution_status, send directly or write to the buffer
  function sendLobbyInput(agentId, text, mode = 'multi') {
    if (!agentId) return
    if (mode === 'confirm') {
      // Empty input counts as confirming (same as the panel behavior)
      const trimmed = String(text || '').trim().toLowerCase()
      const confirmed = trimmed === '' || trimmed === 'y' || trimmed === 'yes' || trimmed === 'confirm' || trimmed === 'true'
      getSendConfirmResult()(confirmed, agentId)
      return
    }
    // Record it in input history (same as panel's sendFromPanel; empty text is skipped internally by saveToHistory)
    saveToHistory(text)
    // Reset this Agent's history-browsing cursor so it does not stay at the old position after sending
    lobbyHistoryIndex.set(agentId, -1)
    lobbyHistoryTemp.delete(agentId)
    const statusData = agentStatuses.value.get(agentId)
    const executionStatus = statusData?.execution_status || 'running'
    const hasBuffered = inputBuffers.value.has(agentId) && (inputBuffers.value.get(agentId) || '').trim()
    // Single-line input, or the backend is waiting for multi-line input: send directly
    if (mode === 'single' || executionStatus === 'waiting_multi') {
      let sendText = text
      if (hasBuffered) {
        const bufferedText = inputBuffers.value.get(agentId)
        inputBuffers.value.delete(agentId)
        sendText = text ? `${bufferedText}\n${text}` : bufferedText
      }
      getSendInputDirectly()(sendText, mode, agentId)
      return
    }
    // There is buffered content and the backend is not waiting for input: send the buffer first, then send this input directly
    if (hasBuffered) {
      getSendBufferedInput()(agentId)
      if (text) {
        getSendInputDirectly()(text, mode, agentId)
      }
      return
    }
    // The backend is not waiting for input (e.g. running): send directly without writing to the buffer
    getSendInputDirectly()(text, mode, agentId)
  }

  // Pet lobby: get the latest displayable output of an Agent (markdown-rendered html)
  function getLobbyLatestOutput(agentId) {
    const list = allOutputs.value.get(agentId)
    if (list && list.length > 0) {
      // Prefer showing the Agent's reply (STREAM)
      for (let i = list.length - 1; i >= 0; i--) {
        const item = list[i]
        if (item.output_type !== 'STREAM') continue
        if (!item.text) continue
        return { html: item.html || escapeHtml(item.text), outputType: item.output_type }
      }
      // With no STREAM, fall back to the latest message that has text (visible right after connecting)
      for (let i = list.length - 1; i >= 0; i--) {
        const item = list[i]
        if (!item.text) continue
        return { html: item.html || escapeHtml(item.text), outputType: item.output_type }
      }
    }
    // Background Agent history is only written to historyStorage and not synced to allOutputs; fall back to reading it here
    const history = historyStorage.getHistoryForAgent(agentId)
    if (history && history.length > 0) {
      for (let i = history.length - 1; i >= 0; i--) {
        const item = history[i]
        if (!item.text) continue
        return { html: item.html || getRenderMessageHtml()(item), outputType: item.output_type }
      }
    }
    return null
  }

  // Pet lobby: send the completion signal (same behavior as Panel's completeFromPanel)
  function onLobbyComplete(agentId) {
    if (!agentId) return
    const statusData = agentStatuses.value.get(agentId)
    const executionStatus = statusData?.execution_status || 'running'
    if (executionStatus === 'waiting_multi') {
      const message = {
        type: 'input_result',
        payload: {
          text: '__CTRL_C_PRESSED__',
          agent_id: agentId,
          display_name: chatName.value || username.value || '',
          input_mode: 'single',
        },
      }
      sendMessageToAgent(message, agentId)
    } else if (executionStatus === 'running') {
      // Same as Panel's Ctrl+C behavior: send a manual-interrupt message when running and the input is empty
      sendMessageToAgent({ type: 'manual_interrupt', payload: {} }, agentId)
    } else {
      inputBuffers.value.set(agentId, '__CTRL_C_PRESSED__')
      getAppendOutput()({
        output_type: 'system',
        agent_name: 'system',
        text: '✅ Completion signal saved to the buffer; it will be triggered automatically when input is needed next time',
        lang: 'text',
      }, agentId)
    }
  }

  // Switch the current working Agent
  async function switchAgent(agent) {
    // Increment the switch generation so stale switchAgent operations become invalid
    const thisGeneration = ++switchGeneration.value

    // If the Agent has stopped, do not trigger any network activity (no status polling, no WebSocket connection)
    if (agent.status === 'stopped') {
      // Only update the current agent ID so the user can still see this agent's local history
      currentAgentId.value = agent.agent_id
      // Point outputList at the new Panel's .messages element and re-attach the scroll listener
      const stoppedTargetPanel = panels.value.find(p => p.agentId === agent.agent_id)
      const stoppedTargetOutputList = stoppedTargetPanel ? panelOutputLists.get(stoppedTargetPanel.id) : null
      if (stoppedTargetOutputList) {
        outputList.value = stoppedTargetOutputList
        setupHistoryScrollListener(stoppedTargetOutputList)
      }
      historyOffset.value = 0
      hasMoreHistory.value = true
      // Load history messages from local storage (no network requests)
      loadHistoryMessages(false)
      return
    }

    if (agent.agent_id === currentAgentId.value) {
      const ws = sockets.value.get(agent.agent_id)
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        try {
          await getConnectToAgent()(agent)
          // After reconnecting, message sync fully relies on the sync_request mechanism; no manual history loading
        } catch (error) {
          console.error(`[AGENT] Failed to reconnect:`, error)
          // Do not abort the flow; let the user see the error
        }
      } else {
        // Check the locally recorded status and restore the UI if needed
        const localStatus = agentStatuses.value.get(agent.agent_id)
        if (localStatus?.execution_status) {
          // Restore the various user-interaction states
          if (localStatus.execution_status === 'waiting_confirm') {
            getRestoreWaitingConfirmUI()(agent.agent_id)
          } else if (localStatus.execution_status === 'waiting_single' || localStatus.execution_status === 'waiting_multi') {
            // Get the Agent's input request from the Map
            const inputRequest = inputRequests.value.get(agent.agent_id)
            if (inputRequest) {
              inputTip.value = inputRequest.tip || ''
              inputMode.value = inputRequest.mode || 'multi'
              inputText.value = inputText.value || inputRequest.preset || ''
              pendingInputAgentId.value = agent.agent_id
              if (!isAnyModalOpen()) {
                nextTick(() => {
                  if (isAnyModalOpen()) return
                  const inputEl = document.querySelector(inputMode.value === 'multi' ? 'textarea' : 'input[type="text"]')
                  inputEl?.focus()
                })
              }
            } else {
              console.warn('[AGENT] No input request found in Map for this agent')
            }
          }
        }
      }
      return
    }

    // Note: do not close the old Agent's WebSocket connection; keep it so it can be reused when switching back.
    // When an old connection drops, onclose checks currentAgentId and does not reconnect unless it is the current Agent.
    const previousAgentId = currentAgentId.value

    // Clean up the current Agent's terminal instances (they are rebuilt from historical execution_chunks when switching away)
    if (previousAgentId) {
      let cleanedCount = 0
      getTerminals().value.forEach((termInfo) => {
        if (termInfo.agentId === previousAgentId && termInfo.terminal) {
          getDisposeExecutionTerminal()(termInfo)
          cleanedCount++
        }
      })
    }

    // Clear the previous Agent's terminalHosts references
    if (previousAgentId) {
      let cleanedHostsCount = 0
      for (const [sessionKey, hostEl] of getTerminalHosts().value.entries()) {
        // sessionKey format is agentId:executionId
        const [agentId] = sessionKey.split(':')
        if (agentId === previousAgentId) {
          getTerminalHosts().value.delete(sessionKey)
          cleanedHostsCount++
        }
      }
    }


    // Clear the current Agent's input state (remove it from the Map)
    const oldAgentId = currentAgentId.value
    if (oldAgentId) {
      inputRequests.value.delete(oldAgentId)
    }
    inputText.value = ''
    inputTip.value = ''
    inputMode.value = 'multi'

    // Update the current Agent ID
    currentAgentId.value = agent.agent_id

    // Point outputList at the new Panel's .messages element and re-attach the scroll listener
    const targetPanel = panels.value.find(p => p.agentId === agent.agent_id)
    const targetOutputList = targetPanel ? panelOutputLists.get(targetPanel.id) : null
    if (targetOutputList) {
      outputList.value = targetOutputList
      setupHistoryScrollListener(targetOutputList)
    }

    // Reset the history offset and message state
    historyOffset.value = 0
    hasMoreHistory.value = true
    // Load this Agent's history messages from local storage immediately to avoid a blank page while switching
    loadHistoryMessages(false)

    // Connect to the Agent first and load history only after the ready event
    // This avoids duplicate rendering between history messages and WebSocket-pushed cached messages
    try {
      // Query the status immediately after switching (even if WebSocket is not connected)
      await fetchAgentStatus(agent)
      // If the Agent has stopped (finished), do not try to connect WebSocket
      if (agent.status === 'stopped') {
        return
      }
      // Wait for the connection to stabilize (Agent startup takes time; bounded retries)
      let stableConnection = false
      let retryCount = 0
      const maxStabilityRetries = 20 // maximum stability verification retries

      while (!stableConnection && retryCount < maxStabilityRetries) {
        // Check whether a newer switchAgent call exists
        if (switchGeneration.value !== thisGeneration) {
          return
        }

        // Only create a new connection if none exists or it is disconnected
        const existingWs = sockets.value.get(agent.agent_id)
        if (!existingWs || existingWs.readyState !== WebSocket.OPEN) {
          // Clean up the disconnected old connection
          if (existingWs && existingWs.readyState !== WebSocket.CLOSED) {
            existingWs.close()
          }
          if (existingWs) {
            sockets.value.delete(agent.agent_id)
          }
          try {
            await getConnectToAgent()(agent)
          } catch (e) {
            console.warn(`[AGENT] connectToAgent failed: ${e.message}`)
          }

          // Check whether the generation has changed
          if (switchGeneration.value !== thisGeneration) {
            return
          }
        }

        // Verify whether the connection is stable
        const ws = sockets.value.get(agent.agent_id)
        if (ws && ws.readyState === WebSocket.OPEN) {
          // Wait 2000ms to ensure the connection is stable
          await new Promise(resolve => setTimeout(resolve, 2000))

          // Check whether the generation has changed
          if (switchGeneration.value !== thisGeneration) {
            return
          }

          // Check again whether the connection is still valid
          if (ws.readyState === WebSocket.OPEN) {
            stableConnection = true
          } else {
            retryCount++
            console.warn(`[AGENT] Connection not stable after ${retryCount} tries, retrying...`)
            await new Promise(resolve => setTimeout(resolve, 2000))
          }
        } else {
          retryCount++
          console.warn(`[AGENT] Connection not established after ${retryCount} tries, retrying...`)
          await new Promise(resolve => setTimeout(resolve, 2000))
        }
      }

      if (!stableConnection) {
        console.warn(`[AGENT] Failed to establish stable connection after ${maxStabilityRetries} retries`)
      }


      // Final check that the WebSocket is really connected
      const ws = sockets.value.get(agent.agent_id)
      if (ws && ws.readyState === WebSocket.OPEN) {
        // Query the status again after connecting, to keep it in sync
        await fetchAgentStatus(agent)

        // The session-restore dialog is disabled (users reported it popping up with a list selector unexpectedly)
        // Original logic: if history is empty, detect restorable sessions and show the SessionDialog
        // To enable it again, uncomment the block below
        /*
        const currentOutputs = allOutputs.value.get(agent.agent_id) || []
        if (currentOutputs.length === 0) {
          try {
            const { host, port } = getGatewayAddress()
            const targetNodeId = String(agent?.node_id || '').trim() || String(getCurrentAgentNodeId() || 'master').trim() || 'master'
            const sessionsResponse = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `agents/${agent.agent_id}/sessions`))
            const sessionsData = await sessionsResponse.json()
            if (sessionsData.success && sessionsData.data && sessionsData.data.length > 0) {
              availableSessions.value = sessionsData.data
              showSessionDialog.value = true
            } else {
            }
          } catch (error) {
            console.error('[AGENT] Failed to fetch sessions:', error)
          }
        } else {
        }
        */
      } else {
        console.warn('[AGENT] Connection verification failed, WebSocket not in OPEN state')
        // WebSocket is not connected, but the status has already been fetched over HTTP
      }
    } catch (error) {
      console.error('[AGENT] Failed to connect to agent:', error)
      // Connection failed: do not load history messages, but keep the current state
      // The user can see the error and retry manually
      // Even on connection failure, the status has already been queried over HTTP
    }
  }

  // Auto-connect to all online Agents (without switching the currently selected Agent)

  // Periodically refresh the Agent list
  let agentListRefreshInterval = null

  function startAgentListRefresh() {
    if (agentListRefreshInterval) {
      clearInterval(agentListRefreshInterval)
    }

    // Refresh every 3 seconds
    agentListRefreshInterval = setInterval(() => {
      fetchAgentList()
    }, 3000)

    // Run once immediately
    fetchAgentList()
  }

  function stopAgentListRefresh() {
    if (agentListRefreshInterval) {
      clearInterval(agentListRefreshInterval)
      agentListRefreshInterval = null
    }
  }

  // ========== End of Agent management methods ==========

  return {
    // In-scope refs (shared via destructuring in App.vue)
    dirDialogContext,
    showToolsModal,
    toolsContent,
    toolsLoading,
    showEditAccessModal,
    editingAccessAgent,
    editAccessRead,
    editAccessInteract,
    // Functions
    getStatusText,
    getStatusClass,
    isWaitingInput,
    fetchAgentStatus,
    syncOnlineAgentStatuses,
    getCreateAgentDirectoryNodeId,
    resetDirectorySelectionState,
    openDirDialog,
    fetchDirectories,
    selectDirectory,
    handleDirSearchKeydown,
    enterDirectory,
    goToParentDir,
    confirmDirectory,
    cancelDirDialog,
    openCreateAgentModal,
    onLobbyCreateAgentOnNode,
    fetchModelGroups,
    fetchUserAccessibleNodes,
    fetchUserPermissions,
    matchPermissionPattern,
    hasPermission,
    fetchNodeStatus,
    startNodeStatusRefresh,
    stopNodeStatusRefresh,
    fetchUserList,
    formatNodeOptionLabel,
    getDefaultTerminalNodeId,
    getAgentNodeLabel,
    getAgentNodeDisplayLabel,
    getAgentProxyNodeLabel,
    getCurrentAgentNodeId,
    getWorkspaceTargetNodeId,
    checkCodeAgentDirConflict,
    createAgentWithOptions,
    afterAgentCreated,
    createAgent,
    openQuickCreateAgent,
    openFullCreateAgentFromQuick,
    submitQuickCreateAgent,
    openCompletions,
    closeCompletionsWithoutSelect,
    handleCompletionKeydown,
    scrollToSelected,
    scrollToDirSelected,
    findVisiblePanelTextarea,
    insertAtPosition,
    insertCompletion,
    fetchAgentList,
    buildCopiedAgentPayload,
    copyAgent,
    batchCopyAgents,
    onLobbyAddAgentToGroup,
    onLobbyRemoveAgentFromGroup,
    addSelectedToGroup,
    createGroupWithAgents,
    renameAgentGroup,
    deleteAgentGroup,
    viewRules,
    exitNonInteractiveMode,
    viewTools,
    renameAgent,
    confirmRename,
    editAgentAccess,
    saveAgentAccess,
    deleteAgent,
    regenerateAgent,
    batchDeleteAgents,
    onLobbySelectAgent,
    getLobbyInputState,
    sendLobbyInput,
    getLobbyLatestOutput,
    onLobbyComplete,
    switchAgent,
    startAgentListRefresh,
    stopAgentListRefresh,
  }
}
