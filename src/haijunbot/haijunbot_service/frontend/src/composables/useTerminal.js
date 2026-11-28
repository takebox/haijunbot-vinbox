// Terminal composable.
//
// Extracted from App.vue's <script setup> (Issue #118 Step 3), keeping behavior exactly the same.
// Covers 5 subdomains:
// - execution terminal (xterm management + execution_chunks rebuild)
// - independent terminals (terminalSessions session management, create/close/switch/input)
// - terminal floating panel (position/size persistence, drag/resize)
// - terminal sharing (ACL share dialog)
// - terminal name/node (terminalName, selectedTerminalNodeId)
//
// Dependency injection:
// - socket / sockets: ref (WebSocket connections)
// - currentAgentId: ref(string)
// - currentAgent: ref(object) (the current Agent, including working_dir)
// - allOutputs: ref(Map) (list of Agent output messages)
// - isExecuting: ref(boolean) (execution state)
// - windowWidth: ref(number) (window width, for mobile narrow-screen detection)
// - activeWindow: ref(string) (currently active window, for z-index)
// - auth: ref(object) (authentication info)
// - showTerminalPanel: ref(boolean) (terminal panel visibility flag)
// - getGatewayAddress: function (returns { host, port })
// - fetchWithAuth: function (authenticated fetch wrapper)
// - getHttpProtocol: function (returns http/https)
// - sendMessageToAgentById: function (sends a message to an Agent)
// - scrollSessionToBottom: function (scrolls the session conversation container to the bottom)
// - getCurrentAgentNodeId: function (returns the current Agent's node ID)
// - showWorkspaceHostView: function (shows chat/terminal in the workspace)
// - clamp: function (numeric clamping)
// - PANEL_DRAG_ACTIVATION_DISTANCE / BASE_Z_INDEX / ACTIVE_Z_INDEX: constants
// - focusWindow: function (focuses a window)
// - fetchUserList: function (fetches the user list)
// - showToast: function (toast notifications)
// - availableUserOptions: ref(Array) (list of selectable users)
// - historyStorage: module (history storage)
import { computed, nextTick, ref, watch } from 'vue'
import { Terminal } from 'xterm'
import { FitAddon } from '@xterm/addon-fit'
import { createTerminalCreationTracker } from '../terminalCreationTracker.js'

// ===== Terminal name / node (low-coupling sub-block; must be called before useDaemonSync/useAuthBridge) =====
// Terminal name: used to distinguish different terminals on the gateway side (Agents can locate this machine by name).
// After saving to localStorage, it is also exposed to: (1) the browser extension (__haijunbotAuthBridge.getName)
// (2) the local daemon (pushed along with /api/auth). The default is the local computer name; the browser cannot read
// the system hostname directly, so it queries the local daemon's /api/status (the daemon provides it via os.Hostname()).
//
// Dependency injection:
// - auth: ref(object) (authentication info)
// - getDaemonUrl: function (returns the local daemon URL; since useDaemonSync is defined afterwards,
//   it is passed as a getter so it is evaluated only when called, avoiding TDZ)
// - syncTokenToDaemon: function (syncs the token to the local daemon; passed as a getter as above)
export function useTerminalName({ auth, getDaemonUrl, syncTokenToDaemon }) {
  const TERMINAL_NAME_STORAGE_KEY = 'haijunbot_terminal_name'
  function loadTerminalName() {
    try {
      return String(localStorage.getItem(TERMINAL_NAME_STORAGE_KEY) || '').trim()
    } catch (error) {
      console.warn('[TERMINAL] Failed to load terminal name:', error)
      return ''
    }
  }
  const terminalName = ref(loadTerminalName())
  function saveTerminalNameSetting(nextValue = terminalName.value) {
    terminalName.value = String(nextValue || '').trim()
    try {
      localStorage.setItem(TERMINAL_NAME_STORAGE_KEY, terminalName.value)
    } catch (error) {
      console.warn('[TERMINAL] Failed to save terminal name:', error)
    }
    // Re-push to the local daemon immediately after the name changes (the extension actively reads the bridge, so no push needed)
    syncTokenToDaemon()(auth.value.token, window.__haijunbotAuthBridge.getGateway())
  }
// On first entry, if the user has not configured a name, use the computer name reported by the local daemon as the default.
// Only write when unconfigured (no value in localStorage) to avoid overwriting a user-defined name.
  async function initTerminalNameFromDaemon() {
    if (loadTerminalName()) return
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 1500)
      const resp = await fetch(`${getDaemonUrl()()}/api/status`, {
        signal: controller.signal,
        credentials: 'omit',
      })
      clearTimeout(timer)
      const data = await resp.json()
      const hostname = String(data?.hostname || '').trim()
      if (hostname) saveTerminalNameSetting(hostname)
    } catch (e) {
      // A missing or stopped daemon is expected; keep the name empty (the gateway side falls back to hostname)
      console.debug('[TERMINAL] init terminal name from daemon skipped:', e?.message || e)
    }
  }
  const selectedTerminalNodeId = ref('master')
  return { terminalName, saveTerminalNameSetting, initTerminalNameFromDaemon, selectedTerminalNodeId }
}

// ===== Main composable: execution terminal / independent terminals / floating panel / sharing =====
export function useTerminal({
  socket,
  sockets,
  currentAgentId,
  currentAgent,
  allOutputs,
  isExecuting,
  windowWidth,
  activeWindow,
  auth,
  showTerminalPanel,
  selectedTerminalNodeId,
  getGatewayAddress,
  fetchWithAuth,
  getHttpProtocol,
  sendMessageToAgentById,
  scrollSessionToBottom,
  getCurrentAgentNodeId,
  showWorkspaceHostView,
  clamp,
  PANEL_DRAG_ACTIVATION_DISTANCE,
  BASE_Z_INDEX,
  ACTIVE_Z_INDEX,
  focusWindow,
  fetchUserList,
  showToast,
  availableUserOptions,
  historyStorage,
}) {

  const terminalHosts = ref(new Map()) // executionSessionKey -> hostEl
  const terminals = ref([]) // [{ sessionKey, agentId, executionId, terminal, active, hostEl, resizeObserver, lastSize, ended }]

  function getExecutionSessionKey(agentId, executionId) {
    const normalizedAgentId = String(agentId || '').trim() || 'unknown-agent'
    const normalizedExecutionId = String(executionId || 'default').trim() || 'default'
    return `${normalizedAgentId}:${normalizedExecutionId}`
  }

  // Independent terminal sessions
  const terminalSessions = ref([]) // [{ terminal_id, interpreter, working_dir, terminal, hostEl, fitAddon }]
  const activeTerminalId = ref(null) // ID of the currently active terminal
  const independentTerminalHosts = ref(new Map()) // terminal_id -> hostEl
  const isCreatingTerminalSession = ref(false)
  // "Initiated by this device" tracker for terminal creation: distinguishes local creation (auto-switch) from sharing by others (no switch)
  const terminalCreationTracker = createTerminalCreationTracker()

  // Debounce for execution_chunks history updates (grouped by executionId, batched to localStorage every 500ms)
  const _execHistoryDebounceMap = new Map()
  function _debouncedSaveExecHistory(executionId, targetAgentId) {
    const key = `${targetAgentId}:${executionId}`
    if (_execHistoryDebounceMap.has(key)) return // already has a pending debounce
    _execHistoryDebounceMap.set(key, true)
    setTimeout(() => {
      _execHistoryDebounceMap.delete(key)
      const currentOutputs = allOutputs.value.get(targetAgentId) || []
      const msg = currentOutputs.find(item => item.output_type === 'execution' && item.execution_id === executionId)
      if (msg) {
        try {
          // Use the same id as appendOutput/appendExecution to update the same record instead of adding a new one
          historyStorage.saveMessage({
            id: `execution_${executionId}`,
            agent_id: targetAgentId,
            output_type: msg.output_type,
            text: msg.text || '',
            lang: msg.lang || 'text',
            agent_name: msg.agent_name,
            non_interactive: msg.non_interactive,
            agent_list: msg.agent_list,
            timestamp: msg.timestamp,
            execution_id: msg.execution_id,
            context: msg.context,
            is_finished: msg.is_finished || false,
            // Only fall back to execution_chunks for terminal_content when the execution has ended,
            // to avoid persisting data with is_finished but nothing to display after a refresh.
            // While an execution is in progress (is_finished=false), terminal_content must stay empty,
            // otherwise, when switching back to that Agent, the template would not render xterm because !item.terminal_content is false,
            // causing a running terminal to be wrongly replaced with a static "Terminal Output" text block.
            terminal_content: msg.is_finished
              ? (msg.terminal_content || (msg.execution_chunks || []).join(''))
              : '',
            execution_chunks: msg.execution_chunks || [],
            seq: msg.seq,
          })
        } catch {
          // Fail silently
        }
      }
    }, 500)
  }

  function appendExecution(payload, agentId = null) {
    const executionId = payload?.execution_id || 'default'
    const eventType = payload?.event_type
    const targetAgentId = agentId || payload?.agent_id || currentAgentId.value
  
  
    // Check whether this is output from an independent terminal (format: terminal_{terminal_id})
    if (executionId.startsWith('terminal_')) {
      const terminalId = executionId.replace('terminal_', '')
      const session = terminalSessions.value.find(t => t.terminal_id === terminalId)
    
      // Check whether the session exists
      if (!session) {
        console.warn(`[independent-terminal] No session found for ${terminalId}`)
        return
      }
    
      // Decode the data
      let data = payload?.data || ''
      if (payload?.encoded && data) {
        try {
          const binaryString = atob(data)
          const bytes = new Uint8Array(binaryString.length)
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i)
          }
          const decoder = new TextDecoder('utf-8')
          data = decoder.decode(bytes)
        } catch (error) {
          console.error('[independent-terminal] Failed to decode base64 data:', error)
          return
        }
      }
    
      // If the terminal is already initialized, write directly
      if (session.terminal) {
        try {
          session.terminal.write(data)
          // Save historical output
          session.history.push({ type: eventType, data: data })
        } catch (error) {
          console.error('[independent-terminal] Failed to write to terminal:', error)
        }
      } else {
        // The terminal is not yet initialized; buffer the output for now
        if (!session.pending_output) {
          session.pending_output = []
        }
        session.pending_output.push(data)
      }
      return
    }
  
    // Handle base64-encoded data
    let data = payload?.data || ''
    if (payload?.encoded && data) {
      try {
        // Decode base64 data
        const binaryString = atob(data)
        // Convert the binary string to a Uint8Array, then decode it as UTF-8
        const bytes = new Uint8Array(binaryString.length)
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i)
        }
        // Use TextDecoder to handle UTF-8
        const decoder = new TextDecoder('utf-8')
        data = decoder.decode(bytes)
      } catch (error) {
        console.error('[terminal] Failed to decode base64 data:', error)
        return
      }
    }
  
    const executionSessionKey = getExecutionSessionKey(targetAgentId, executionId)

    // Check whether a new terminal needs to be created
    let termInfo = terminals.value.find(t => t.sessionKey === executionSessionKey)
    if (!termInfo) {
      termInfo = {
        sessionKey: executionSessionKey,
        agentId: targetAgentId,
        executionId,
        terminal: null,
        active: true,
        hostEl: null,
        ended: false,
      }
      terminals.value.push(termInfo)
      // Terminal initialization moved to setTerminalRef to ensure the DOM element is ready
    }

  
    // Handle the execution-start event
    if (payload?.message_type === 'tool_stream_start' && !isExecuting.value) {
      isExecuting.value = true
    }
  
    // Handle the execution-end event
    if (payload?.message_type === 'tool_stream_end' && termInfo.active) {
      // If termInfo.terminal does not exist, it may be a background-executed command (the terminal was not initialized because the DOM was not rendered)
      // The background-execution case needs the execution correctly marked as finished to avoid needlessly rebuilding xterm when switching back
      if (!termInfo.terminal) {
        // Check whether the message's execution_chunks has data to determine whether this is a background-execution or reconnect case
        const currentOutputs = allOutputs.value.get(targetAgentId) || []
        const execMsg = currentOutputs.find(
          item => item.output_type === 'execution' && item.execution_id === executionId
        )
        if (execMsg?.execution_chunks?.length > 0) {
          // Background-execution case: there is data but the terminal is not initialized, so the execution needs to end correctly
        } else {
          // Reconnect case: no data, so ignore tool_stream_end
          return
        }
      }
      termInfo.active = false
      termInfo.ended = true
      isExecuting.value = false // Update execution state

      // Save the terminal content to the message list
      // Prefer getting content from the terminal buffer (in the background-execution case, join from execution_chunks)
      let terminalContent = ''
      if (termInfo.terminal) {
        terminalContent = getTerminalBufferContent(termInfo.terminal, true)
      } else {
        // Background-execution case: join from the message's execution_chunks
        const currentOutputs = allOutputs.value.get(targetAgentId) || []
        const execMsg = currentOutputs.find(
          item => item.output_type === 'execution' && item.execution_id === executionId
        )
        if (execMsg?.execution_chunks?.length > 0) {
          terminalContent = execMsg.execution_chunks.join('')
        }
      }
      // Get the terminal content and save it
      try {
        // Find and update the execution message, adding the is_finished flag and terminal_content
        const currentOutputs = allOutputs.value.get(targetAgentId) || []
        const execIndex = currentOutputs.findIndex(
          item => item.output_type === 'execution' && item.execution_id === executionId
        )
        if (execIndex !== -1) {
          // Mark the execution message as finished and save the terminal content (keeping execution_chunks to rebuild xterm)
          currentOutputs[execIndex].is_finished = true
          currentOutputs[execIndex].terminal_content = terminalContent
          currentOutputs[execIndex].timestamp = new Date().toISOString()
          // Trigger a reactive update
          allOutputs.value.set(targetAgentId, [...currentOutputs])
          // Save to history (update the existing execution message, keeping execution_chunks)
          try {
            const updatedMessage = {
              id: `execution_${executionId}`,
              agent_id: targetAgentId,
              output_type: 'execution',
              text: '',
              lang: 'text',
              agent_name: currentOutputs[execIndex].agent_name,
              non_interactive: false,
              timestamp: currentOutputs[execIndex].timestamp,
              execution_id: executionId,
              context: currentOutputs[execIndex].context,
              is_finished: true,
              terminal_content: terminalContent || (currentOutputs[execIndex].execution_chunks || []).join(''),
              execution_chunks: currentOutputs[execIndex].execution_chunks || [],
            }
            historyStorage.saveMessage(updatedMessage)
          } catch (error) {
            console.warn('[HISTORY] Failed to save terminal content:', error)
          }

        } else {
          console.warn(`🚨 [terminal] execution message ${executionId} not found`)
        }
      } catch (error) {
        console.error(`[terminal] Failed to save terminal content:`, error)
      }

      // Destroy the xterm instance and free resources (the content is already saved to the message's terminal_content and execution_chunks)
      disposeExecutionTerminal(termInfo)
      const executionSessionKey = getExecutionSessionKey(targetAgentId, executionId)
      terminalHosts.value.delete(executionSessionKey)

      // After xterm is destroyed and switched to the "Terminal Output" text block, scroll the outer session conversation container once (when auto-scroll is on)
      scrollSessionToBottom(targetAgentId)
    }
  
    // Output to the terminal
    if (eventType === 'stdout' || eventType === 'stderr') {
      if (data) {
        // Append to the message's execution_chunks and update history in real time
        const currentOutputs = allOutputs.value.get(targetAgentId) || []
        const execIndex = currentOutputs.findIndex(
          item => item.output_type === 'execution' && item.execution_id === executionId
        )
        if (execIndex !== -1) {
          if (!currentOutputs[execIndex].execution_chunks) currentOutputs[execIndex].execution_chunks = []
          currentOutputs[execIndex].execution_chunks.push(data)
          // Debounce history updates (batched every 500ms to avoid high-frequency localStorage reads/writes)
          _debouncedSaveExecHistory(executionId, targetAgentId)
        }
      }
      if (termInfo.terminal) {
        // Show the data about to be written (first 100 characters), for debugging
        const preview = data.substring(0, 100).replace(/\x1b/g, 'ESC').replace(/\r/g, 'CR').replace(/\n/g, 'LF')
        try {
          termInfo.terminal.write(data)
        } catch (error) {
          console.error('[terminal] Write failed:', error)
        }
      } else if (data) {
      }
    } else if (eventType === 'status') {
      const statusLine = `\r\n[status] ${payload.data || ''}`
      // Append to the message's execution_chunks and update history in real time
      const currentOutputs = allOutputs.value.get(targetAgentId) || []
      const execIndex = currentOutputs.findIndex(
        item => item.output_type === 'execution' && item.execution_id === executionId
      )
      if (execIndex !== -1) {
        if (!currentOutputs[execIndex].execution_chunks) currentOutputs[execIndex].execution_chunks = []
        currentOutputs[execIndex].execution_chunks.push(statusLine)
        // Debounce history updates (batched every 500ms to avoid high-frequency localStorage reads/writes)
        _debouncedSaveExecHistory(executionId, targetAgentId)
      }
      if (termInfo.terminal) {
        termInfo.terminal.writeln(statusLine)
      } else {
      }
    } else if (!termInfo.terminal && data) {
    }
  }

  // Clear the terminal cache for the specified agent
  function clearTerminalCache(agentId) {
    if (!agentId) return
    const beforeCount = terminals.value.length
    // Clear all terminal caches for that agent (finished terminals are rebuilt from history, so no termInfo needs to be kept)
    terminals.value = terminals.value.filter(t => t.agentId !== agentId)
    const afterCount = terminals.value.length
  }

  function getTerminalBufferContent(terminal, trimTrailingWhitespace = false) {
    const buffer = terminal?.buffer?.active
    if (!buffer) return ''

    const lines = []
    for (let i = 0; i < buffer.length; i++) {
      const line = buffer.getLine(i)
      if (line) {
        lines.push(line.translateToString(true))
      }
    }

    const content = lines.join('\n')
    return trimTrailingWhitespace ? content.replace(/\s+$/, '') : content
  }

  function syncTerminalSize(executionId, termInfo) {
    if (!termInfo) {
      return
    }
    if (!termInfo.terminal) {
      return
    }
    if (!termInfo.fitAddon) {
      return
    }
  
    // Use FitAddon to fit the size automatically
    const oldCols = termInfo.terminal.cols
    const oldRows = termInfo.terminal.rows
    termInfo.fitAddon.fit()
    const newCols = termInfo.terminal.cols
    const newRows = termInfo.terminal.rows
  
  
    // If the size has not changed, skip
    if (oldCols === newCols && oldRows === newRows) {
      return
    }
  
    // Send a resize message to the backend
    const message = {
      type: 'terminal_resize',
      payload: {
        execution_id: executionId,
        rows: newRows,
        cols: newCols,
      },
    }
    sendMessageToAgentById(termInfo.agentId, message)
  }

  function disposeExecutionTerminal(termInfo) {
    if (termInfo?.resizeObserver) {
      termInfo.resizeObserver.disconnect()
    }
    if (termInfo?.fitAddon) {
      try {
        termInfo.fitAddon.dispose()
      } catch (error) {
        console.warn('[terminal] Failed to dispose fitAddon', error)
      }
    }
    if (termInfo?.terminal) {
      try {
        termInfo.terminal.dispose()
      } catch (error) {
        console.warn('[terminal] Failed to dispose terminal', error)
      }
    }

    termInfo.resizeObserver = null
    termInfo.fitAddon = null
    termInfo.terminal = null
    termInfo.hostEl = null
    // Note: do not set termInfo.ended = true, because the execution may still be in progress
    // ended is set only when the backend's tool_stream_end event is received (see the handleToolStreamEnd function)
    // This way, the terminal content can be restored from execution_chunks when switching back to the Agent
  }

  function initExecutionTerminal(executionId, termInfo, el, agentId = null) {
    const targetAgentId = agentId || termInfo?.agentId || currentAgentId.value
    termInfo.hostEl = el
    termInfo.terminal = new Terminal({
      theme: {
        background: '#0b1424',
      },
      fontSize: 12,
      fontFamily: "'Consolas', 'Microsoft YaHei', monospace",
      allowProposedApi: true,
      focusOnClick: false,
    })

    // Intercept shortcuts to prevent browser default behavior from overriding terminal shortcuts
    termInfo.terminal.attachCustomKeyEventHandler((event) => {
      // Ctrl+Shift+C: copy selected text to the clipboard
      if (event.ctrlKey && event.shiftKey && event.code === 'KeyC') {
        const selection = termInfo.terminal.getSelection()
        if (selection) {
          navigator.clipboard.writeText(selection).catch(err => {
            console.warn('[terminal] Failed to copy to clipboard:', err)
          })
        }
        return false
      }
      // Ctrl+Shift+V: paste (handled by onData; here we just prevent the browser default)
      if (event.ctrlKey && event.shiftKey && event.code === 'KeyV') {
        return false
      }
      return true
    })
    termInfo.terminal.open(el)

    termInfo.fitAddon = new FitAddon()
    termInfo.terminal.loadAddon(termInfo.fitAddon)
    termInfo.fitAddon.fit()

    // Whether this execution is the last item in the current Agent's message list (a new execution was just created)
    // Used to decide whether to scroll the outer session conversation container, avoiding disturbing users viewing history when switching back to an Agent and rebuilding xterm
    const isLatestExecution = () => {
      const currentOutputs = allOutputs.value.get(targetAgentId) || []
      const lastMsg = currentOutputs[currentOutputs.length - 1]
      return !!(
        lastMsg?.output_type === 'execution' &&
        lastMsg.execution_id === executionId &&
        !lastMsg.is_finished
      )
    }

    if (typeof ResizeObserver !== 'undefined') {
      termInfo.resizeObserver = new ResizeObserver(() => {
        syncTerminalSize(executionId, termInfo)
      })
      termInfo.resizeObserver.observe(el)
    }

    termInfo.terminal.onData(data => {
      if (!termInfo.active) return
      const message = {
        type: 'terminal_input',
        payload: {
          execution_id: executionId,
          data,
        },
      }
      const ws = targetAgentId ? sockets.value.get(targetAgentId) : null
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message))
      } else {
        console.warn(`[terminal] No open WebSocket for agent ${targetAgentId}, execution ${executionId}`)
      }
    })

    requestAnimationFrame(() => {
      syncTerminalSize(executionId, termInfo)
      if (isLatestExecution()) {
        scrollSessionToBottom(targetAgentId)
      }
    })

    // xterm's height stabilizes only after its first render; scroll once more here to make sure the newly created terminal is visible
    setTimeout(() => {
      syncTerminalSize(executionId, termInfo)
      if (isLatestExecution()) {
        scrollSessionToBottom(targetAgentId)
      }
    }, 300)

    // Replay from the message's execution_chunks (when switching back)
    // If the terminal has finished, do not replay chunks, to avoid restoring a finished terminal
    if (!termInfo.ended) {
      const currentOutputs = allOutputs.value.get(targetAgentId) || []
      const execMsg = currentOutputs.find(
        item => item.output_type === 'execution' && item.execution_id === executionId
      )
      if (execMsg?.execution_chunks?.length > 0) {
        execMsg.execution_chunks.forEach((chunk, index) => {
          try {
            termInfo.terminal.write(chunk)
          } catch (error) {
            console.warn(`[terminal] Failed to replay chunk ${index}`, error)
          }
        })
      }
    }

    if (termInfo.ended) {
      getTerminalBufferContent(termInfo.terminal, true)
    }
  }

  // Dynamically bind the terminal DOM element
  function setTerminalRef(executionId, el, agentId = null) {
    const targetAgentId = agentId || currentAgentId.value
    const executionSessionKey = getExecutionSessionKey(targetAgentId, executionId)
    let termInfo = terminals.value.find(t => t.sessionKey === executionSessionKey)
    if (el) {
      if (el.parentElement) {
      }
      terminalHosts.value.set(executionSessionKey, el)
      if (!termInfo) {
        // Check whether the corresponding execution has already finished
        const agentOutputs = allOutputs.value.get(targetAgentId) || []
        const executionMessage = agentOutputs.find(
          item => item.output_type === 'execution' && item.execution_id === executionId
        )
      
        // If there is terminal_content, the execution result is already saved, so no need to create xterm (just show the text history)
        if (executionMessage?.terminal_content) {
          return
        }
        // Check whether it has finished but has no terminal_content (reconnect case); no need to recreate the terminal
        if (executionMessage?.is_finished) {
          return
        }
      
        // termInfo does not exist; create a new terminal record
        termInfo = {
          sessionKey: executionSessionKey,
          agentId: targetAgentId,
          executionId: executionId,
          terminal: null,
          active: true,
          hostEl: null,
          resizeObserver: null,
          lastSize: null,
          ended: false
        }
        terminals.value.push(termInfo)
      }

      const needsRebuild = !!termInfo.terminal && termInfo.hostEl !== el
      if (needsRebuild) {
        // Check whether the agent's last message is a command still executing; if not, no need to rebuild xterm
        const agentOutputs = allOutputs.value.get(targetAgentId) || []
        const lastMessage = agentOutputs[agentOutputs.length - 1]
        // If there is terminal_content, the execution result is already saved, so no need to rebuild xterm
        if (lastMessage?.terminal_content) {
          disposeExecutionTerminal(termInfo)
          termInfo.ended = true
          return
        }
        const isLastMessageExecution = lastMessage?.output_type === 'execution' && !lastMessage?.is_finished
        if (!isLastMessageExecution) {
          disposeExecutionTerminal(termInfo)
          termInfo.ended = true
          return
        }
        disposeExecutionTerminal(termInfo)
      }

      if (!termInfo.terminal && !termInfo.ended) {
        initExecutionTerminal(executionId, termInfo, el, targetAgentId)
      } else if (termInfo.ended) {
      } else {
        termInfo.hostEl = el
        if (!termInfo.resizeObserver && typeof ResizeObserver !== 'undefined') {
          termInfo.resizeObserver = new ResizeObserver(() => {
            syncTerminalSize(executionId, termInfo)
          })
          termInfo.resizeObserver.observe(el)
        }
        syncTerminalSize(executionId, termInfo)
      }
    } else {
      // Element-unmount callback: clean up only when the current host has left the document (or was already empty),
      // avoiding mistakenly cleaning up the same terminal that is still alive inside the editor when the editor-hosted grid instance unmounts
      if (termInfo && termInfo.hostEl && termInfo.hostEl.isConnected) {
        return
      }
      terminalHosts.value.delete(executionSessionKey)
      if (termInfo?.resizeObserver) {
        termInfo.resizeObserver.disconnect()
        termInfo.resizeObserver = null
      }
      if (termInfo) {
        termInfo.hostEl = null
      }
    }
  }

  // Independent terminal functions
  function setTerminalHostRef(terminalId, el) {
    const session = terminalSessions.value.find(t => t.terminal_id === terminalId)
    if (el) {
      // If hostEl is the same and the terminal already exists, this is a ref callback triggered by a component update and does not need re-initialization
      if (session && session.hostEl === el && session.terminal) {
        return
      }
      independentTerminalHosts.value.set(terminalId, el)
      if (session) {
        session.hostEl = el
        // Ensure xterm is created whether or not the terminal is already initialized (fixes the issue after re-login where
        // hostEl is rendered but xterm is not initialized, showing a tab with no content)
        initIndependentTerminal(terminalId, el)
      }
    } else {
      independentTerminalHosts.value.delete(terminalId)
      if (session) {
        session.hostEl = null
      }
    }
  }

  function initIndependentTerminal(terminalId, el) {
    const session = terminalSessions.value.find(t => t.terminal_id === terminalId)
    if (!session) {
      console.warn(`[independent-terminal] Session not found for ${terminalId}`)
      return
    }
  
    // If a terminal instance already exists (a panel switch rebuilt the component), dispose the old one before creating a new one
    if (session.terminal) {
      try {
        // xterm.js's Terminal.open() cannot be called twice on the same instance, so it must be disposed before creating a new one
        // Note: do not set session.terminal = null, to avoid triggering a reactive update that causes an infinite loop
        session.terminal.dispose()
        session.fitAddon = null
        if (session.resizeObserver) {
          session.resizeObserver.disconnect()
          session.resizeObserver = null
        }
      } catch (error) {
        console.warn(`[independent-terminal] Failed to dispose old terminal ${terminalId}:`, error)
      }
      // Continue with the new-instance creation logic below (session.terminal will be overwritten by the new Terminal() below)
    }

  
    // Create the terminal instance
    // Note: fitAddon.fit() is not called here because the element may be invisible initially (v-show)
    // It will be resized automatically in the ResizeObserver callback
    session.terminal = new Terminal({
      theme: {
        background: '#0b1424',
      },
      fontSize: 12,
      fontFamily: "'Consolas', 'Microsoft YaHei', monospace",
      cols: 80,
      rows: 24,
      allowProposedApi: true,
    })

    // Intercept shortcuts to prevent browser default behavior from overriding terminal shortcuts
    session.terminal.attachCustomKeyEventHandler((event) => {
      // Ctrl+Shift+C: copy selected text to the clipboard
      if (event.ctrlKey && event.shiftKey && event.code === 'KeyC') {
        const selection = session.terminal.getSelection()
        if (selection) {
          navigator.clipboard.writeText(selection).catch(err => {
            console.warn('[independent-terminal] Failed to copy to clipboard:', err)
          })
        }
        return false
      }
      // Ctrl+Shift+V: paste (handled by onData; here we just prevent the browser default)
      if (event.ctrlKey && event.shiftKey && event.code === 'KeyV') {
        return false
      }
      return true
    })
    session.terminal.open(el)
  
    // Create and load FitAddon
    session.fitAddon = new FitAddon()
    session.terminal.loadAddon(session.fitAddon)
  
    // Use FitAddon to fit the terminal size (only when the element is visible)
    if (el.offsetParent !== null) {
      session.fitAddon.fit()
    } else {
    }
  
    // Set up a ResizeObserver to watch size changes
    if (typeof ResizeObserver !== 'undefined') {
      const resizeObserver = new ResizeObserver(() => {
        if (session.fitAddon && session.terminal) {
          session.fitAddon.fit()
          // Send a resize message to the backend
          sendTerminalResize(terminalId, session.terminal.rows, session.terminal.cols)
        }
      })
      resizeObserver.observe(el)
      session.resizeObserver = resizeObserver
    }
  
    // Listen for user input
    session.terminal.onData(data => {
      // Read-only mode: do not send input (read users can only view)
      if (session.access === 'read') {
        return
      }
      sendTerminalInput(terminalId, data)
    })
  
    // Send a resize after initialization
    setTimeout(() => {
      if (session.fitAddon && session.terminal) {
        session.fitAddon.fit()
        sendTerminalResize(terminalId, session.terminal.rows, session.terminal.cols)
      
        // Write the buffered output (history + pending_output)
        const allOutputs = [
          ...(session.history || []).map(item => item.data),
          ...(session.pending_output || []),
        ]
        if (allOutputs.length > 0) {
          try {
            for (const bufferedData of allOutputs) {
              session.terminal.write(bufferedData)
            }
          } catch (error) {
            console.error('[independent-terminal] Failed to write buffered outputs:', error)
          }
          // Clear the buffer
          session.pending_output = []
        }
      }
    }, 300)
  }

  // Decode a base64 string into UTF-8 text (consistent with the decoding logic in appendExecution)
  function decodeTerminalBase64(b64) {
    try {
      const binaryString = atob(b64)
      const bytes = new Uint8Array(binaryString.length)
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i)
      }
      return new TextDecoder('utf-8').decode(bytes)
    } catch (error) {
      console.error('[independent-terminal] Failed to decode base64 data:', error)
      return ''
    }
  }

  // Take over a terminal session: have the backend record this user to receive live output and replay the output buffer
  async function attachTerminalSession(terminalId) {
    try {
      const { host, port } = getGatewayAddress()
      const baseUrl = `${getHttpProtocol()}://${host}:${port}`
      const attachResp = await fetchWithAuth(
        `${baseUrl}/api/terminals/${encodeURIComponent(terminalId)}/attach`,
        { method: 'POST' }
      )
      const attachResult = await attachResp.json()
      if (!attachResult.success || !Array.isArray(attachResult.data?.output)) return
      const bufferedOutput = attachResult.data.output.map(decodeTerminalBase64)
      if (bufferedOutput.length === 0) return
      // If xterm is initialized, write directly; otherwise store in pending_output to be replayed on initialization
      const session = terminalSessions.value.find(t => t.terminal_id === terminalId)
      if (session && session.terminal) {
        for (const data of bufferedOutput) {
          session.terminal.write(data)
        }
      } else if (session) {
        session.pending_output = [...(session.pending_output || []), ...bufferedOutput]
      }
    } catch (e) {
      console.warn('[independent-terminal] Failed to attach session:', terminalId, e)
    }
  }

  // Restore the current user's live terminal sessions after login/reconnect (Plan A: disconnect without killing the process + replay the output buffer)
  async function restoreTerminalSessions() {
    if (!socket.value) {
      console.warn('[independent-terminal] No socket connection, skip restore')
      return
    }
    try {
      const { host, port } = getGatewayAddress()
      const baseUrl = `${getHttpProtocol()}://${host}:${port}`
      const url = `${baseUrl}/api/terminals`
      const response = await fetchWithAuth(url)
      if (!response.ok) return
      const result = await response.json()
      if (!result.success || !Array.isArray(result.data)) return

      for (const s of result.data) {
        const terminalId = s.terminal_id
        if (!terminalId) continue
        // Skip already-restored sessions to avoid duplicates
        if (terminalSessions.value.find(t => t.terminal_id === terminalId)) continue

        // Take over the session and get the output buffer (for replay)
        let bufferedOutput = []
        try {
          const attachResp = await fetchWithAuth(
            `${baseUrl}/api/terminals/${encodeURIComponent(terminalId)}/attach`,
            { method: 'POST' }
          )
          const attachResult = await attachResp.json()
          if (attachResult.success && Array.isArray(attachResult.data?.output)) {
            bufferedOutput = attachResult.data.output.map(decodeTerminalBase64)
          }
        } catch (e) {
          console.warn('[independent-terminal] Failed to attach session:', terminalId, e)
        }

        // Add to the session list; the buffered output goes into pending_output to be replayed by initIndependentTerminal
        terminalSessions.value.push({
          terminal_id: terminalId,
          node_id: s.node_id || 'master',
          interpreter: s.interpreter || 'bash',
          working_dir: s.working_dir || '.',
          access: s.access || 'read',
          terminal: null,
          hostEl: null,
          fitAddon: null,
          resizeObserver: null,
          history: [],
          pending_output: bufferedOutput,
        })
        if (!activeTerminalId.value) {
          activeTerminalId.value = terminalId
        }
        // If the DOM is rendered and xterm is not yet initialized, initialize the terminal (replay the buffer).
        // If hostEl was already initialized by setTerminalHostRef, skip here to avoid creating it twice.
        nextTick(() => {
          const sessionNow = terminalSessions.value.find(t => t.terminal_id === terminalId)
          if (!sessionNow || sessionNow.terminal) return
          const hostEl = independentTerminalHosts.value.get(terminalId)
          if (hostEl) {
            initIndependentTerminal(terminalId, hostEl)
          }
        })
      }
    } catch (e) {
      console.error('[independent-terminal] Failed to restore sessions:', e)
    }
  }

  // Mark that this device initiated the terminal creation; if creation fails (no terminal_created response), it auto-resets after a timeout,
  // avoiding a leftover flag causing terminals shared from other ends to be switched to by mistake
  function markTerminalCreationPending() {
    terminalCreationTracker.mark()
  }

  function createTerminal() {
    if (!socket.value) {
      console.warn('[independent-terminal] No socket connection')
      return
    }
  
    const nodeId = getCurrentAgentNodeId() || ''
    const payload = {}
    if (nodeId) {
      payload.node_id = nodeId
    }
    const currentWorkingDir = currentAgent.value?.working_dir?.trim()
    if (currentWorkingDir) {
      payload.working_dir = currentWorkingDir
    }
    const message = {
      type: 'terminal_create',
      payload,
    }
    socket.value.send(JSON.stringify(message))
    // Mark that this device initiated the terminal creation; auto-switch when the terminal_created response arrives
    markTerminalCreationPending()
  
    // Automatically show the terminal in the workspace
    showWorkspaceHostView('terminal')
  }

  function createTerminalForSelectedNode() {
    if (!socket.value) {
      console.warn('[independent-terminal] No socket connection')
      return
    }

    const nodeId = String(selectedTerminalNodeId.value || '').trim()
    if (!nodeId) {
      console.warn('[independent-terminal] No terminal node selected')
      return
    }

    const message = {
      type: 'terminal_create',
      payload: {
        node_id: nodeId,
      },
    }
    socket.value.send(JSON.stringify(message))
    // Mark that this device initiated the terminal creation; auto-switch when the terminal_created response arrives
    markTerminalCreationPending()

    // Automatically show the terminal in the workspace
    showWorkspaceHostView('terminal')
  }

  // Create an independent terminal on the specified node (lobby node right-click menu)
  function createTerminalForNode(nodeId) {
    if (!socket.value) {
      console.warn('[independent-terminal] No socket connection')
      return
    }
    const normalizedNodeId = String(nodeId || '').trim()
    if (!normalizedNodeId) {
      console.warn('[independent-terminal] No terminal node specified')
      return
    }
    const message = {
      type: 'terminal_create',
      payload: { node_id: normalizedNodeId },
    }
    socket.value.send(JSON.stringify(message))
    // Mark that this device initiated the terminal creation; auto-switch when the terminal_created response arrives
    markTerminalCreationPending()
    // Automatically show the terminal in the workspace
    showWorkspaceHostView('terminal')
  }

  function createTerminalForAgent(agent) {
    if (!socket.value) {
      console.warn('[independent-terminal] No socket connection')
      return
    }

  
    // Create the terminal directly using the passed agent argument, without relying on an async switch
    const nodeId = String(agent?.node_id || '').trim() || ''
    const payload = {}
    if (nodeId) {
      payload.node_id = nodeId
    }
    const workingDir = agent?.working_dir?.trim()
    if (workingDir) {
      payload.working_dir = workingDir
    }
    const message = {
      type: 'terminal_create',
      payload,
    }
    socket.value.send(JSON.stringify(message))
    // Mark that this device initiated the terminal creation; auto-switch when the terminal_created response arrives
    markTerminalCreationPending()
  
    // Automatically show the terminal in the workspace
    showWorkspaceHostView('terminal')
  }

  function closeTerminal(terminalId) {
    // Closing a tab only closes the local xterm view and does not exit the actual terminal process (similar to tmux detach).
    // The backend session is preserved and can be restored via the "Sync" button (restoreTerminalSessions).
  
    // Clean up the terminal instance
    const sessionIndex = terminalSessions.value.findIndex(t => t.terminal_id === terminalId)
    if (sessionIndex !== -1) {
      const session = terminalSessions.value[sessionIndex]
      if (session.terminal) {
        try {
          session.terminal.dispose()
        } catch (error) {
          console.warn('[independent-terminal] Failed to dispose terminal', error)
        }
      }
      // Remove from the array
      terminalSessions.value.splice(sessionIndex, 1)
    }
  
    // If the one being closed is the currently active terminal, switch to another
    if (activeTerminalId.value === terminalId) {
      activeTerminalId.value = terminalSessions.value.length > 0 ? terminalSessions.value[0].terminal_id : null
    }
  
    // Clean up the ref
    independentTerminalHosts.value.delete(terminalId)
  }

  const TERMINAL_PANEL_MIN_WIDTH = 400
  const TERMINAL_PANEL_MIN_HEIGHT = 300
  const TERMINAL_PANEL_STORAGE_KEY = 'haijunbot_terminal_panel_rect'
  const terminalResizeDirections = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

  function getDefaultTerminalPanelRect() {
    return {
      top: 88,
      left: Math.max(window.innerWidth - 824, 16),
      width: 800,
      height: 500,
    }
  }

  function loadTerminalPanelRect() {
    const defaultTerminalPanelRect = getDefaultTerminalPanelRect()
    const savedValue = localStorage.getItem(TERMINAL_PANEL_STORAGE_KEY)
    if (!savedValue) {
      return defaultTerminalPanelRect
    }

    try {
      const parsedValue = JSON.parse(savedValue)
      if (
        typeof parsedValue.top !== 'number' ||
        typeof parsedValue.left !== 'number' ||
        typeof parsedValue.width !== 'number' ||
        typeof parsedValue.height !== 'number'
      ) {
        return defaultTerminalPanelRect
      }

      return parsedValue
    } catch {
      return defaultTerminalPanelRect
    }
  }

  function saveTerminalPanelRect() {
    localStorage.setItem(TERMINAL_PANEL_STORAGE_KEY, JSON.stringify(terminalPanelRect.value))
  }

  const terminalPanelRect = ref(loadTerminalPanelRect())

  const terminalPanelInteraction = ref({
    active: false,
    mode: null,
    direction: null,
    startX: 0,
    startY: 0,
    startTop: 0,
    startLeft: 0,
    startWidth: 0,
    startHeight: 0,
  })

  const terminalPanelStyle = computed(() => ({
    top: `${terminalPanelRect.value.top}px`,
    left: `${terminalPanelRect.value.left}px`,
    width: `${terminalPanelRect.value.width}px`,
    height: `${terminalPanelRect.value.height}px`,
    zIndex: activeWindow.value === 'terminal' ? ACTIVE_Z_INDEX : BASE_Z_INDEX,
  }))

  function getTerminalPanelBounds() {
    const HEADER_HEIGHT = 32 // Title bar height
    const MIN_VISIBLE_WIDTH = 100 // Keep at least 100px of panel width visible
    return {
      minTop: 0, // The title bar cannot be dragged beyond the top of the window
      minLeft: 0, // The title bar cannot be dragged beyond the left of the window
      maxLeft: window.innerWidth - MIN_VISIBLE_WIDTH, // Keep at least 100px of panel width visible
      maxTop: window.innerHeight - HEADER_HEIGHT, // Keep the title bar height visible
    }
  }

  function ensureTerminalPanelInViewport() {
    const HEADER_HEIGHT = 32 // Title bar height
    const MIN_VISIBLE_WIDTH = 100 // Keep at least 100px of panel width visible
    const maxWidth = Math.max(window.innerWidth, TERMINAL_PANEL_MIN_WIDTH)
    const maxHeight = Math.max(window.innerHeight, TERMINAL_PANEL_MIN_HEIGHT)

    terminalPanelRect.value.width = clamp(terminalPanelRect.value.width, TERMINAL_PANEL_MIN_WIDTH, maxWidth)
    terminalPanelRect.value.height = clamp(terminalPanelRect.value.height, TERMINAL_PANEL_MIN_HEIGHT, maxHeight)

    // The title bar cannot move outside the window
    terminalPanelRect.value.left = clamp(
      terminalPanelRect.value.left,
      0, // The title bar cannot be dragged beyond the left of the window
      window.innerWidth - MIN_VISIBLE_WIDTH // Keep at least 100px of panel width visible
    )
    terminalPanelRect.value.top = clamp(
      terminalPanelRect.value.top,
      0, // The title bar cannot be dragged beyond the top of the window
      window.innerHeight - HEADER_HEIGHT // Keep the title bar height visible
    )
  }

  function startTerminalPanelMove(event) {
    if (windowWidth.value <= 768) return
    if (event.target.closest('.terminal-panel-actions')) return

    focusWindow('terminal')

    terminalPanelInteraction.value = {
      active: false,
      mode: 'move',
      direction: null,
      startX: event.clientX,
      startY: event.clientY,
      startTop: terminalPanelRect.value.top,
      startLeft: terminalPanelRect.value.left,
      startWidth: terminalPanelRect.value.width,
      startHeight: terminalPanelRect.value.height,
    }

    document.addEventListener('mousemove', onTerminalPanelPointerMove)
    document.addEventListener('mouseup', stopTerminalPanelInteraction)
  }

  function startTerminalPanelResize(event, direction) {
    if (windowWidth.value <= 768) return

    terminalPanelInteraction.value = {
      active: true,
      mode: 'resize',
      direction,
      startX: event.clientX,
      startY: event.clientY,
      startTop: terminalPanelRect.value.top,
      startLeft: terminalPanelRect.value.left,
      startWidth: terminalPanelRect.value.width,
      startHeight: terminalPanelRect.value.height,
    }

    document.addEventListener('mousemove', onTerminalPanelPointerMove)
    document.addEventListener('mouseup', stopTerminalPanelInteraction)
    event.preventDefault()
    event.stopPropagation()
  }

  function onTerminalPanelPointerMove(event) {
    const deltaX = event.clientX - terminalPanelInteraction.value.startX
    const deltaY = event.clientY - terminalPanelInteraction.value.startY

    if (terminalPanelInteraction.value.mode === 'move' && !terminalPanelInteraction.value.active) {
      const dragDistance = Math.hypot(deltaX, deltaY)
      if (dragDistance < PANEL_DRAG_ACTIVATION_DISTANCE) {
        return
      }

      terminalPanelInteraction.value = {
        ...terminalPanelInteraction.value,
        active: true,
      }
      event.preventDefault()
    }

    if (!terminalPanelInteraction.value.active) return

    if (terminalPanelInteraction.value.mode === 'move') {
      const bounds = getTerminalPanelBounds()
      terminalPanelRect.value.left = clamp(terminalPanelInteraction.value.startLeft + deltaX, bounds.minLeft, bounds.maxLeft)
      terminalPanelRect.value.top = clamp(terminalPanelInteraction.value.startTop + deltaY, bounds.minTop, bounds.maxTop)
      return
    }

    const direction = terminalPanelInteraction.value.direction || ''
    const startLeft = terminalPanelInteraction.value.startLeft
    const startTop = terminalPanelInteraction.value.startTop
    const startWidth = terminalPanelInteraction.value.startWidth
    const startHeight = terminalPanelInteraction.value.startHeight

    let nextLeft = startLeft
    let nextTop = startTop
    let nextWidth = startWidth
    let nextHeight = startHeight

    if (direction.includes('e')) {
      nextWidth = clamp(startWidth + deltaX, TERMINAL_PANEL_MIN_WIDTH, Math.max(window.innerWidth - startLeft, TERMINAL_PANEL_MIN_WIDTH))
    }

    if (direction.includes('s')) {
      nextHeight = clamp(startHeight + deltaY, TERMINAL_PANEL_MIN_HEIGHT, Math.max(window.innerHeight - startTop, TERMINAL_PANEL_MIN_HEIGHT))
    }

    if (direction.includes('w')) {
      const desiredLeft = clamp(startLeft + deltaX, 0, startLeft + startWidth - TERMINAL_PANEL_MIN_WIDTH)
      nextLeft = desiredLeft
      nextWidth = startWidth - (desiredLeft - startLeft)
    }

    if (direction.includes('n')) {
      const desiredTop = clamp(startTop + deltaY, 0, startTop + startHeight - TERMINAL_PANEL_MIN_HEIGHT)
      nextTop = desiredTop
      nextHeight = startHeight - (desiredTop - startTop)
    }

    if (nextLeft + nextWidth > window.innerWidth) {
      nextWidth = Math.max(TERMINAL_PANEL_MIN_WIDTH, window.innerWidth - nextLeft)
    }

    if (nextTop + nextHeight > window.innerHeight) {
      nextHeight = Math.max(TERMINAL_PANEL_MIN_HEIGHT, window.innerHeight - nextTop)
    }

    terminalPanelRect.value.left = clamp(nextLeft, 0, Math.max(window.innerWidth - nextWidth, 0))
    terminalPanelRect.value.top = clamp(nextTop, 0, Math.max(window.innerHeight - nextHeight, 0))
    terminalPanelRect.value.width = clamp(nextWidth, TERMINAL_PANEL_MIN_WIDTH, Math.max(window.innerWidth - terminalPanelRect.value.left, TERMINAL_PANEL_MIN_WIDTH))
    terminalPanelRect.value.height = clamp(nextHeight, TERMINAL_PANEL_MIN_HEIGHT, Math.max(window.innerHeight - terminalPanelRect.value.top, TERMINAL_PANEL_MIN_HEIGHT))
  }

  function stopTerminalPanelInteraction() {
    terminalPanelInteraction.value = {
      active: false,
      mode: null,
      direction: null,
      startX: 0,
      startY: 0,
      startTop: 0,
      startLeft: 0,
      startWidth: 0,
      startHeight: 0,
    }

    document.removeEventListener('mousemove', onTerminalPanelPointerMove)
    document.removeEventListener('mouseup', stopTerminalPanelInteraction)
    saveTerminalPanelRect()
  }

  function switchTerminal(terminalId) {
    activeTerminalId.value = terminalId
  
    // Focus the selected terminal
    nextTick(() => {
      const session = terminalSessions.value.find(t => t.terminal_id === terminalId)
      if (session && session.terminal) {
        try {
          session.terminal.focus()
        } catch (error) {
          console.warn('[independent-terminal] Failed to focus terminal', error)
        }
      }
    })
  }

  function sendTerminalInput(terminalId, data) {
    if (!socket.value) {
      console.warn('[independent-terminal] No socket connection')
      return
    }
  
    const session = terminalSessions.value.find(t => t.terminal_id === terminalId)
    const payload = { terminal_id: terminalId, data }
    if (session?.node_id) {
      payload.node_id = session.node_id
    }
    const message = {
      type: 'terminal_session_input',
      payload,
    }
    socket.value.send(JSON.stringify(message))
  }

  function sendTerminalResize(terminalId, rows, cols) {
    if (!socket.value) {
      console.warn('[independent-terminal] No socket connection')
      return
    }
  
    const session = terminalSessions.value.find(t => t.terminal_id === terminalId)
    const payload = { terminal_id: terminalId, rows, cols }
    if (session?.node_id) {
      payload.node_id = session.node_id
    }
    const message = {
      type: 'terminal_session_resize',
      payload,
    }
    socket.value.send(JSON.stringify(message))
  }

  watch(showTerminalPanel, (newValue, oldValue) => {
    if (!newValue && oldValue) {
      stopTerminalPanelInteraction()
      terminalSessions.value.forEach(session => {
        if (session.resizeObserver) {
          session.resizeObserver.disconnect()
        }
      })
    } else if (newValue && !oldValue) {
      ensureTerminalPanelInViewport()
      saveTerminalPanelRect()
      nextTick(() => {
        const activeSession = terminalSessions.value.find(s => s.terminal_id === activeTerminalId.value)
        if (activeSession && activeSession.resizeObserver && activeSession.hostEl) {
          activeSession.resizeObserver.observe(activeSession.hostEl)
          if (activeSession.fitAddon && activeSession.terminal) {
            activeSession.fitAddon.fit()
            sendTerminalResize(activeSession.terminal_id, activeSession.terminal.rows, activeSession.terminal.cols)
          }
        }
      })
    }
  })

  // Watch terminal switches
  watch(activeTerminalId, (newId, oldId) => {
    if (newId !== oldId) {
      // Switch the terminal tab

      // Disable the old terminal's ResizeObserver
      const oldSession = terminalSessions.value.find(s => s.terminal_id === oldId)
      if (oldSession && oldSession.resizeObserver) {
        oldSession.resizeObserver.disconnect()
      }

      // Enable the new terminal's ResizeObserver
      const newSession = terminalSessions.value.find(s => s.terminal_id === newId)
      if (newSession && newSession.resizeObserver && newSession.hostEl) {
        nextTick(() => {
          newSession.resizeObserver.observe(newSession.hostEl)
          if (newSession.fitAddon && newSession.terminal) {
            newSession.fitAddon.fit()
            sendTerminalResize(newSession.terminal_id, newSession.terminal.rows, newSession.terminal.cols)
          }
        })
      }
    }
  })

  const showTerminalShareModal = ref(false)
  const editingShareTerminalId = ref(null)
  const terminalShareRead = ref([])
  const terminalShareInteract = ref([])

  async function openTerminalShareDialog(terminalId) {
    editingShareTerminalId.value = terminalId
    terminalShareRead.value = []
    terminalShareInteract.value = []
    showTerminalShareModal.value = true
    // Fetch the user list for selection
    await fetchUserList()
  }

  // Save the terminal share ACL: PUT /api/terminals/{id}/acl (main gateway path, not the node proxy)
  async function saveTerminalShare() {
    const terminalId = editingShareTerminalId.value
    if (!terminalId) return
    try {
      const { host, port } = getGatewayAddress()
      const response = await fetchWithAuth(`${getHttpProtocol()}://${host}:${port}/api/terminals/${encodeURIComponent(terminalId)}/acl`, {
        method: 'PUT',
        body: JSON.stringify({
          read: terminalShareRead.value,
          interact: terminalShareInteract.value,
        })
      })
      if (!response.ok) {
        const error = await response.json()
        alert(`Share failed: ${error.error?.message || error.detail || 'Unknown error'}`)
        return
      }
      showToast('Share settings saved', 'success')
      showTerminalShareModal.value = false
    } catch (error) {
      console.error('[TERMINAL] Share update failed:', error)
      alert(`Share failed: ${error.message}`)
    }
  }

  const filteredUserOptionsForTerminalShare = computed(() => {
    const ownerId = auth.value.userInfo?.user_id || ''
    return availableUserOptions.value.filter(user => {
      if (user.user_id === ownerId) return false
      if (user.is_admin) return false
      return true
    })
  })

  return {
    terminalHosts,
    terminals,
    getExecutionSessionKey,
    terminalSessions,
    activeTerminalId,
    independentTerminalHosts,
    isCreatingTerminalSession,
    terminalCreationTracker,
    _debouncedSaveExecHistory,
    appendExecution,
    clearTerminalCache,
    getTerminalBufferContent,
    syncTerminalSize,
    disposeExecutionTerminal,
    initExecutionTerminal,
    setTerminalRef,
    setTerminalHostRef,
    initIndependentTerminal,
    decodeTerminalBase64,
    attachTerminalSession,
    restoreTerminalSessions,
    markTerminalCreationPending,
    createTerminal,
    createTerminalForSelectedNode,
    createTerminalForNode,
    createTerminalForAgent,
    closeTerminal,
    TERMINAL_PANEL_MIN_WIDTH,
    TERMINAL_PANEL_MIN_HEIGHT,
    TERMINAL_PANEL_STORAGE_KEY,
    terminalResizeDirections,
    getDefaultTerminalPanelRect,
    loadTerminalPanelRect,
    saveTerminalPanelRect,
    terminalPanelRect,
    terminalPanelInteraction,
    terminalPanelStyle,
    getTerminalPanelBounds,
    ensureTerminalPanelInViewport,
    startTerminalPanelMove,
    startTerminalPanelResize,
    onTerminalPanelPointerMove,
    stopTerminalPanelInteraction,
    switchTerminal,
    sendTerminalInput,
    sendTerminalResize,
    showTerminalShareModal,
    editingShareTerminalId,
    terminalShareRead,
    terminalShareInteract,
    openTerminalShareDialog,
    saveTerminalShare,
    filteredUserOptionsForTerminalShare,
  }
}
