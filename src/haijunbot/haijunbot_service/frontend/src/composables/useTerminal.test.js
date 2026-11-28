// useTerminal unit tests
// Covers: useTerminalName (terminal name/node), useTerminal (execution terminal, independent terminals,
// floating panel, sharing, execution chunks rebuild). Mocks xterm/WebSocket/ResizeObserver/
// localStorage/DOM, consistent with the useDiff.test.js style.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useTerminal, useTerminalName } from './useTerminal.js'

// ---- mock xterm (use vi.hoisted so the factory can reference it and tests can access the same instance) ----
const { MockTerminal, MockFitAddon } = vi.hoisted(() => {
  class MockTerminal {
    constructor() {
      this.cols = 80
      this.rows = 24
      this.buffer = {
        active: {
          length: 0,
          getLine: () => null,
        },
      }
      this._handlers = {}
      this._keyHandler = null
      this._addons = []
      this.opened = false
      this.disposed = false
      this.focused = false
      this._written = []
    }
    open() { this.opened = true }
    loadAddon(addon) { this._addons.push(addon) }
    write(data) { this._written.push(data) }
    writeln(data) { this._written.push(data + '\r\n') }
    dispose() { this.disposed = true }
    focus() { this.focused = true }
    onData(handler) { this._handlers.onData = handler }
    attachCustomKeyEventHandler(handler) { this._keyHandler = handler }
    getSelection() { return '' }
    getLine() { return null }
  }

  class MockFitAddon {
    constructor() { this.fitted = 0; this.disposed = false }
    fit() { this.fitted += 1 }
    dispose() { this.disposed = true }
  }

  return { MockTerminal, MockFitAddon }
})

vi.mock('xterm', () => ({
  Terminal: MockTerminal,
}))

vi.mock('@xterm/addon-fit', () => ({
  FitAddon: MockFitAddon,
}))
// ---- mock global environment ----
function setupGlobals() {
  // WebSocket
  class MockWebSocket {
    constructor() { this.readyState = 1 } // OPEN
    send = vi.fn()
    close = vi.fn()
  }
  MockWebSocket.OPEN = 1
  MockWebSocket.CONNECTING = 0
  MockWebSocket.CLOSED = 3
  globalThis.WebSocket = MockWebSocket

  // ResizeObserver
  globalThis.ResizeObserver = class {
    constructor(cb) { this.cb = cb }
    observe = vi.fn()
    disconnect = vi.fn()
  }

  // requestAnimationFrame
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0)

  // navigator.clipboard
  if (!globalThis.navigator) globalThis.navigator = {}
  globalThis.navigator.clipboard = { writeText: vi.fn().mockResolvedValue(undefined) }

  // window.__haijunbotAuthBridge (read by saveTerminalNameSetting when pushing to the daemon to get the gateway)
  globalThis.__haijunbotAuthBridge = { getGateway: () => 'http://127.0.0.1:8000' }

  // window.innerWidth/innerHeight
  Object.defineProperty(globalThis, 'innerWidth', { value: 1400, writable: true, configurable: true })
  Object.defineProperty(globalThis, 'innerHeight', { value: 900, writable: true, configurable: true })
}

function makeHarness() {
  setupGlobals()
  const socket = ref(null)
  const sockets = ref(new Map())
  const currentAgentId = ref('agent-1')
  const currentAgent = ref({ node_id: 'node-1', working_dir: '/tmp' })
  const allOutputs = ref(new Map())
  const isExecuting = ref(false)
  const windowWidth = ref(1400)
  const activeWindow = ref('chat')
  const auth = ref({ token: 'tok', userInfo: { user_id: 'me' } })
  const showTerminalPanel = ref(false)
  const selectedTerminalNodeId = ref('master')
  const availableUserOptions = ref([])

  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const fetchWithAuth = vi.fn()
  const getHttpProtocol = vi.fn(() => 'http')
  const sendMessageToAgentById = vi.fn()
  const scrollSessionToBottom = vi.fn()
  const getCurrentAgentNodeId = vi.fn(() => 'node-1')
  const showWorkspaceHostView = vi.fn()
  const clamp = (v, min, max) => Math.min(Math.max(v, min), max)
  const PANEL_DRAG_ACTIVATION_DISTANCE = 5
  const BASE_Z_INDEX = 100
  const ACTIVE_Z_INDEX = 200
  const focusWindow = vi.fn()
  const fetchUserList = vi.fn()
  const showToast = vi.fn()
  const historyStorage = { saveMessage: vi.fn() }

  const api = useTerminal({
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
  })

  return {
    api, socket, sockets, currentAgentId, currentAgent, allOutputs, isExecuting,
    windowWidth, activeWindow, auth, showTerminalPanel, selectedTerminalNodeId,
    availableUserOptions, getGatewayAddress, fetchWithAuth, getHttpProtocol,
    sendMessageToAgentById, scrollSessionToBottom, getCurrentAgentNodeId,
    showWorkspaceHostView, focusWindow, fetchUserList, showToast, historyStorage,
  }
}

function makeNameHarness() {
  setupGlobals()
  const auth = ref({ token: 'tok', userInfo: { user_id: 'me' } })
  // getDaemonUrl/syncTokenToDaemon are passed as getters (functions returning functions),
  // consistent with how useTerminalName internally calls getDaemonUrl()() / syncTokenToDaemon()()
  const getDaemonUrl = vi.fn(() => () => 'http://127.0.0.1:17800')
  const syncTokenToDaemon = vi.fn(() => vi.fn())
  const api = useTerminalName({ auth, getDaemonUrl, syncTokenToDaemon })
  return { api, auth, getDaemonUrl, syncTokenToDaemon }
}

describe('useTerminalName', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('exposes the expected interface', () => {
    const { api } = makeNameHarness()
    expect(typeof api.terminalName).toBe('object')
    expect(typeof api.saveTerminalNameSetting).toBe('function')
    expect(typeof api.initTerminalNameFromDaemon).toBe('function')
    expect(typeof api.selectedTerminalNodeId).toBe('object')
  })

  it('selectedTerminalNodeId defaults to master', () => {
    const { api } = makeNameHarness()
    expect(api.selectedTerminalNodeId.value).toBe('master')
  })

  it('saveTerminalNameSetting saves and writes to localStorage', () => {
    const { api, syncTokenToDaemon } = makeNameHarness()
    api.saveTerminalNameSetting('my-host')
    expect(api.terminalName.value).toBe('my-host')
    expect(localStorage.getItem('haijunbot_terminal_name')).toBe('my-host')
    expect(syncTokenToDaemon).toHaveBeenCalled()
  })

  it('saveTerminalNameSetting falls back to an empty string for empty values', () => {
    const { api } = makeNameHarness()
    api.saveTerminalNameSetting('  ')
    expect(api.terminalName.value).toBe('')
  })

  it('initTerminalNameFromDaemon: does not overwrite an existing config', async () => {
    localStorage.setItem('haijunbot_terminal_name', 'custom')
    const { api, getDaemonUrl } = makeNameHarness()
    await api.initTerminalNameFromDaemon()
    expect(getDaemonUrl).not.toHaveBeenCalled()
    expect(api.terminalName.value).toBe('custom')
  })

  it('initTerminalNameFromDaemon: fetches the hostname from the daemon when unconfigured', async () => {
    const { api } = makeNameHarness()
    globalThis.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue({ hostname: 'daemon-host' }),
    })
    await api.initTerminalNameFromDaemon()
    expect(api.terminalName.value).toBe('daemon-host')
    expect(localStorage.getItem('haijunbot_terminal_name')).toBe('daemon-host')
  })

  it('initTerminalNameFromDaemon: stays empty when the daemon is unavailable', async () => {
    const { api } = makeNameHarness()
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('down'))
    await api.initTerminalNameFromDaemon()
    expect(api.terminalName.value).toBe('')
  })
})

describe('useTerminal', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('exposes the expected interface', () => {
    const { api } = makeHarness()
    expect(typeof api.terminalHosts).toBe('object')
    expect(typeof api.terminals).toBe('object')
    expect(typeof api.getExecutionSessionKey).toBe('function')
    expect(typeof api.terminalSessions).toBe('object')
    expect(typeof api.activeTerminalId).toBe('object')
    expect(typeof api.appendExecution).toBe('function')
    expect(typeof api.setTerminalRef).toBe('function')
    expect(typeof api.closeTerminal).toBe('function')
    expect(typeof api.createTerminal).toBe('function')
    expect(typeof api.switchTerminal).toBe('function')
    expect(typeof api.sendTerminalInput).toBe('function')
    expect(typeof api.sendTerminalResize).toBe('function')
    expect(typeof api.terminalPanelRect).toBe('object')
    expect(typeof api.terminalPanelStyle).toBe('object')
    expect(typeof api.startTerminalPanelMove).toBe('function')
    expect(typeof api.openTerminalShareDialog).toBe('function')
    expect(typeof api.saveTerminalShare).toBe('function')
  })

  describe('getExecutionSessionKey', () => {
    it('concatenates agentId and executionId', () => {
      const { api } = makeHarness()
      expect(api.getExecutionSessionKey('agent-1', 'exec-1')).toBe('agent-1:exec-1')
    })
    it('falls back to the default for empty values', () => {
      const { api } = makeHarness()
      expect(api.getExecutionSessionKey('', '')).toBe('unknown-agent:default')
    })
  })

  describe('getTerminalBufferContent', () => {
    it('returns an empty string when there is no buffer', () => {
      const { api } = makeHarness()
      expect(api.getTerminalBufferContent(null)).toBe('')
      expect(api.getTerminalBufferContent({})).toBe('')
    })
    it('concatenates multiple lines of content', () => {
      const { api } = makeHarness()
      const terminal = {
        buffer: {
          active: {
            length: 2,
            getLine: (i) => (i === 0 ? { translateToString: () => 'hello' } : { translateToString: () => 'world' }),
          },
        },
      }
      expect(api.getTerminalBufferContent(terminal)).toBe('hello\nworld')
    })
    it('trimTrailingWhitespace removes trailing whitespace', () => {
      const { api } = makeHarness()
      const terminal = {
        buffer: {
          active: {
            length: 1,
            getLine: () => ({ translateToString: () => 'hello   ' }),
          },
        },
      }
      expect(api.getTerminalBufferContent(terminal, true)).toBe('hello')
    })
  })

  describe('clearTerminalCache', () => {
    it('clears the terminal cache for the specified agent', () => {
      const { api } = makeHarness()
      api.terminals.value = [
        { agentId: 'agent-1', sessionKey: 'a' },
        { agentId: 'agent-2', sessionKey: 'b' },
      ]
      api.clearTerminalCache('agent-1')
      expect(api.terminals.value).toEqual([{ agentId: 'agent-2', sessionKey: 'b' }])
    })
    it('does nothing when there is no agentId', () => {
      const { api } = makeHarness()
      api.terminals.value = [{ agentId: 'agent-1' }]
      api.clearTerminalCache('')
      expect(api.terminals.value).toHaveLength(1)
    })
  })

  describe('decodeTerminalBase64', () => {
    it('decodes base64 UTF-8', () => {
      const { api } = makeHarness()
      expect(api.decodeTerminalBase64(btoa('hello'))).toBe('hello')
    })
    it('returns an empty string for invalid base64', () => {
      const { api } = makeHarness()
      expect(api.decodeTerminalBase64('!!!not-base64!!!')).toBe('')
    })
  })

  describe('createTerminal / createTerminalForSelectedNode / createTerminalForNode / createTerminalForAgent', () => {
    it('createTerminal skips when there is no socket', () => {
      const { api, showWorkspaceHostView } = makeHarness()
      api.createTerminal()
      expect(showWorkspaceHostView).not.toHaveBeenCalled()
    })
    it('createTerminal sends terminal_create and shows the workspace terminal', () => {
      const { api, socket, showWorkspaceHostView } = makeHarness()
      socket.value = new globalThis.WebSocket()
      api.createTerminal()
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'terminal_create',
        payload: { node_id: 'node-1', working_dir: '/tmp' },
      }))
      expect(showWorkspaceHostView).toHaveBeenCalledWith('terminal')
    })
    it('createTerminalForSelectedNode sends the selected node', () => {
      const { api, socket, selectedTerminalNodeId, showWorkspaceHostView } = makeHarness()
      socket.value = new globalThis.WebSocket()
      selectedTerminalNodeId.value = 'node-9'
      api.createTerminalForSelectedNode()
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'terminal_create',
        payload: { node_id: 'node-9' },
      }))
      expect(showWorkspaceHostView).toHaveBeenCalledWith('terminal')
    })
    it('createTerminalForNode sends the specified node', () => {
      const { api, socket, showWorkspaceHostView } = makeHarness()
      socket.value = new globalThis.WebSocket()
      api.createTerminalForNode('node-7')
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'terminal_create',
        payload: { node_id: 'node-7' },
      }))
      expect(showWorkspaceHostView).toHaveBeenCalledWith('terminal')
    })
    it('createTerminalForAgent uses the agent node_id and working_dir', () => {
      const { api, socket, showWorkspaceHostView } = makeHarness()
      socket.value = new globalThis.WebSocket()
      api.createTerminalForAgent({ node_id: 'node-3', working_dir: '/home/x' })
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'terminal_create',
        payload: { node_id: 'node-3', working_dir: '/home/x' },
      }))
      expect(showWorkspaceHostView).toHaveBeenCalledWith('terminal')
    })
  })

  describe('sendTerminalInput / sendTerminalResize', () => {
    it('sendTerminalInput sends terminal_session_input (including node_id)', () => {
      const { api, socket } = makeHarness()
      socket.value = new globalThis.WebSocket()
      api.terminalSessions.value.push({ terminal_id: 't1', node_id: 'node-1' })
      api.sendTerminalInput('t1', 'ls')
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'terminal_session_input',
        payload: { terminal_id: 't1', data: 'ls', node_id: 'node-1' },
      }))
    })
    it('sendTerminalInput skips when there is no socket', () => {
      const { api, socket } = makeHarness()
      api.sendTerminalInput('t1', 'ls')
      expect(socket.value).toBeNull()
    })
    it('sendTerminalResize sends terminal_session_resize', () => {
      const { api, socket } = makeHarness()
      socket.value = new globalThis.WebSocket()
      api.terminalSessions.value.push({ terminal_id: 't1', node_id: 'node-1' })
      api.sendTerminalResize('t1', 24, 80)
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'terminal_session_resize',
        payload: { terminal_id: 't1', rows: 24, cols: 80, node_id: 'node-1' },
      }))
    })
  })

  describe('switchTerminal / closeTerminal', () => {
    it('switchTerminal switches the active terminal and focuses it', async () => {
      const { api } = makeHarness()
      const term = new MockTerminal()
      api.terminalSessions.value.push({ terminal_id: 't1', terminal: term })
      api.switchTerminal('t1')
      expect(api.activeTerminalId.value).toBe('t1')
      await nextTick()
      expect(term.focused).toBe(true)
    })
    it('closeTerminal removes the session and switches the active one', () => {
      const { api } = makeHarness()
      const term = new MockTerminal()
      api.terminalSessions.value.push(
        { terminal_id: 't1', terminal: term },
        { terminal_id: 't2', terminal: new MockTerminal() },
      )
      api.activeTerminalId.value = 't1'
      api.closeTerminal('t1')
      expect(api.terminalSessions.value).toHaveLength(1)
      expect(api.terminalSessions.value[0].terminal_id).toBe('t2')
      expect(api.activeTerminalId.value).toBe('t2')
      expect(term.disposed).toBe(true)
    })
    it('closeTerminal clears activeTerminalId when closing the last terminal', () => {
      const { api } = makeHarness()
      api.terminalSessions.value.push({ terminal_id: 't1', terminal: new MockTerminal() })
      api.activeTerminalId.value = 't1'
      api.closeTerminal('t1')
      expect(api.terminalSessions.value).toHaveLength(0)
      expect(api.activeTerminalId.value).toBeNull()
    })
  })

  describe('floating panel (loadTerminalPanelRect / saveTerminalPanelRect / interaction)', () => {
    it('uses the default rect when there is no saved value', () => {
      const { api } = makeHarness()
      expect(api.terminalPanelRect.value).toEqual({
        top: 88,
        left: Math.max(1400 - 824, 16),
        width: 800,
        height: 500,
      })
    })
    it('reads the rect saved in localStorage', () => {
      localStorage.setItem('haijunbot_terminal_panel_rect', JSON.stringify({ top: 10, left: 20, width: 600, height: 400 }))
      const { api } = makeHarness()
      expect(api.terminalPanelRect.value).toEqual({ top: 10, left: 20, width: 600, height: 400 })
    })
    it('falls back to the default for a corrupted localStorage value', () => {
      localStorage.setItem('haijunbot_terminal_panel_rect', 'not-json')
      const { api } = makeHarness()
      expect(api.terminalPanelRect.value.width).toBe(800)
    })
    it('saveTerminalPanelRect writes to localStorage', () => {
      const { api } = makeHarness()
      api.terminalPanelRect.value = { top: 5, left: 6, width: 700, height: 300 }
      api.saveTerminalPanelRect()
      expect(JSON.parse(localStorage.getItem('haijunbot_terminal_panel_rect'))).toEqual({ top: 5, left: 6, width: 700, height: 300 })
    })
    it('terminalPanelStyle computes z-index (active window)', () => {
      const { api, activeWindow } = makeHarness()
      activeWindow.value = 'terminal'
      expect(api.terminalPanelStyle.value.zIndex).toBe(200)
      activeWindow.value = 'chat'
      expect(api.terminalPanelStyle.value.zIndex).toBe(100)
    })
    it('startTerminalPanelMove is ignored on mobile', () => {
      const { api, windowWidth } = makeHarness()
      windowWidth.value = 500
      api.startTerminalPanelMove({ target: { closest: () => null }, clientX: 0, clientY: 0 })
      expect(api.terminalPanelInteraction.value.mode).toBeNull()
    })
    it('startTerminalPanelMove records the start position and listens for events', () => {
      const { api } = makeHarness()
      const addSpy = vi.spyOn(document, 'addEventListener')
      api.startTerminalPanelMove({ target: { closest: () => null }, clientX: 100, clientY: 50 })
      expect(api.terminalPanelInteraction.value.mode).toBe('move')
      expect(api.terminalPanelInteraction.value.startX).toBe(100)
      expect(addSpy).toHaveBeenCalledWith('mousemove', expect.any(Function))
      expect(addSpy).toHaveBeenCalledWith('mouseup', expect.any(Function))
    })
    it('onTerminalPanelPointerMove moves the panel', () => {
      const { api } = makeHarness()
      api.startTerminalPanelMove({ target: { closest: () => null }, clientX: 100, clientY: 50 })
      // First exceed the activation distance
      api.onTerminalPanelPointerMove({ clientX: 120, clientY: 60, preventDefault: () => {} })
      expect(api.terminalPanelInteraction.value.active).toBe(true)
      expect(api.terminalPanelRect.value.left).toBeGreaterThan(0)
    })
    it('stopTerminalPanelInteraction resets and saves', () => {
      const { api } = makeHarness()
      api.startTerminalPanelMove({ target: { closest: () => null }, clientX: 100, clientY: 50 })
      api.stopTerminalPanelInteraction()
      expect(api.terminalPanelInteraction.value.active).toBe(false)
      expect(api.terminalPanelInteraction.value.mode).toBeNull()
      // saveTerminalPanelRect is an internal closure function; verify its side effect of writing to localStorage
      expect(localStorage.getItem('haijunbot_terminal_panel_rect')).toBeTruthy()
    })
  })

  describe('setTerminalRef (execution terminal binding)', () => {
    it('creates and initializes xterm when there is no terminal_content/is_finished', () => {
      const { api, allOutputs } = makeHarness()
      allOutputs.value.set('agent-1', [])
      const el = { parentElement: null, isConnected: true, offsetParent: {} }
      api.setTerminalRef('exec-1', el, 'agent-1')
      expect(api.terminalHosts.value.has('agent-1:exec-1')).toBe(true)
      expect(api.terminals.value).toHaveLength(1)
      const termInfo = api.terminals.value[0]
      expect(termInfo.terminal).toBeInstanceOf(MockTerminal)
      expect(termInfo.terminal.opened).toBe(true)
    })
    it('does not create xterm when the execution already has terminal_content', () => {
      const { api, allOutputs } = makeHarness()
      allOutputs.value.set('agent-1', [
        { output_type: 'execution', execution_id: 'exec-1', terminal_content: 'done' },
      ])
      const el = { parentElement: null, isConnected: true }
      api.setTerminalRef('exec-1', el, 'agent-1')
      expect(api.terminals.value).toHaveLength(0)
    })
    it('does not create xterm when the execution is finished and has no content', () => {
      const { api, allOutputs } = makeHarness()
      allOutputs.value.set('agent-1', [
        { output_type: 'execution', execution_id: 'exec-1', is_finished: true },
      ])
      const el = { parentElement: null, isConnected: true }
      api.setTerminalRef('exec-1', el, 'agent-1')
      expect(api.terminals.value).toHaveLength(0)
    })
    it('cleans up the host reference on element unmount', () => {
      const { api, allOutputs } = makeHarness()
      allOutputs.value.set('agent-1', [])
      // isConnected=false means the element has left the document (unmount scenario)
      const el = { parentElement: null, isConnected: false }
      api.setTerminalRef('exec-1', el, 'agent-1')
      expect(api.terminalHosts.value.size).toBe(1)
      // Unmount: clear when null is passed and the original host has left the document
      api.setTerminalRef('exec-1', null, 'agent-1')
      expect(api.terminalHosts.value.size).toBe(0)
    })
  })

  describe('appendExecution', () => {
    it('writes independent terminal output (terminal_ prefix) to the session', () => {
      const { api } = makeHarness()
      const term = new MockTerminal()
      api.terminalSessions.value.push({ terminal_id: 't1', terminal: term, history: [] })
      api.appendExecution({ execution_id: 'terminal_t1', event_type: 'stdout', data: 'hi' })
      expect(term._written).toContain('hi')
      expect(api.terminalSessions.value[0].history).toEqual([{ type: 'stdout', data: 'hi' }])
    })
    it('skips independent terminal output when there is no session', () => {
      const { api } = makeHarness()
      api.appendExecution({ execution_id: 'terminal_none', event_type: 'stdout', data: 'hi' })
      expect(api.terminalSessions.value).toHaveLength(0)
    })
    it('writes execution output to xterm and appends to execution_chunks', () => {
      const { api, allOutputs } = makeHarness()
      const term = new MockTerminal()
      allOutputs.value.set('agent-1', [
        { output_type: 'execution', execution_id: 'exec-1', execution_chunks: [] },
      ])
      api.terminals.value.push({
        sessionKey: 'agent-1:exec-1', agentId: 'agent-1', executionId: 'exec-1',
        terminal: term, active: true, ended: false,
      })
      api.appendExecution({ execution_id: 'exec-1', event_type: 'stdout', data: 'out' })
      expect(term._written).toContain('out')
      expect(allOutputs.value.get('agent-1')[0].execution_chunks).toEqual(['out'])
    })
    it('decodes base64-encoded data', () => {
      const { api, allOutputs } = makeHarness()
      const term = new MockTerminal()
      allOutputs.value.set('agent-1', [
        { output_type: 'execution', execution_id: 'exec-1', execution_chunks: [] },
      ])
      api.terminals.value.push({
        sessionKey: 'agent-1:exec-1', agentId: 'agent-1', executionId: 'exec-1',
        terminal: term, active: true, ended: false,
      })
      api.appendExecution({ execution_id: 'exec-1', event_type: 'stdout', data: btoa('decoded'), encoded: true })
      expect(term._written).toContain('decoded')
    })
    it('tool_stream_end marks the end and saves terminal_content', () => {
      const { api, allOutputs, isExecuting } = makeHarness()
      const term = new MockTerminal()
      term.buffer = {
        active: {
          length: 1,
          getLine: () => ({ translateToString: () => 'final output' }),
        },
      }
      allOutputs.value.set('agent-1', [
        { output_type: 'execution', execution_id: 'exec-1', execution_chunks: [] },
      ])
      api.terminals.value.push({
        sessionKey: 'agent-1:exec-1', agentId: 'agent-1', executionId: 'exec-1',
        terminal: term, active: true, ended: false,
      })
      isExecuting.value = true
      api.appendExecution({ execution_id: 'exec-1', event_type: 'stdout', message_type: 'tool_stream_end' })
      const msg = allOutputs.value.get('agent-1')[0]
      expect(msg.is_finished).toBe(true)
      expect(msg.terminal_content).toBe('final output')
      expect(isExecuting.value).toBe(false)
      expect(api.terminals.value[0].ended).toBe(true)
    })
  })
  describe('sharing (openTerminalShareDialog / saveTerminalShare)', () => {
    it('openTerminalShareDialog opens the modal and fetches the user list', async () => {
      const { api, fetchUserList, availableUserOptions } = makeHarness()
      availableUserOptions.value = [{ user_id: 'u1', is_admin: false }]
      await api.openTerminalShareDialog('t1')
      expect(api.showTerminalShareModal.value).toBe(true)
      expect(api.editingShareTerminalId.value).toBe('t1')
      expect(fetchUserList).toHaveBeenCalled()
    })
    it('filteredUserOptionsForTerminalShare excludes owner and admin', () => {
      const { api, availableUserOptions } = makeHarness()
      availableUserOptions.value = [
        { user_id: 'me', is_admin: false },
        { user_id: 'admin1', is_admin: true },
        { user_id: 'u2', is_admin: false },
      ]
      const ids = api.filteredUserOptionsForTerminalShare.value.map(u => u.user_id)
      expect(ids).toEqual(['u2'])
    })
    it('saveTerminalShare returns early when there is no terminalId', async () => {
      const { api, fetchWithAuth } = makeHarness()
      await api.saveTerminalShare()
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('saveTerminalShare sends an ACL update', async () => {
      const { api, fetchWithAuth, showToast } = makeHarness()
      api.editingShareTerminalId.value = 't1'
      api.terminalShareRead.value = ['u1']
      api.terminalShareInteract.value = ['u2']
      fetchWithAuth.mockResolvedValue({ ok: true })
      await api.saveTerminalShare()
      expect(fetchWithAuth).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/terminals/t1/acl',
        expect.objectContaining({ method: 'PUT' })
      )
      expect(showToast).toHaveBeenCalledWith('Share settings saved', 'success')
      expect(api.showTerminalShareModal.value).toBe(false)
    })
  })
})
