// useGatewayConnection unit tests
// Covers: connection state derivation / connect / disconnect / reconnect / gateway restart /
// connectToAgent / autoConnectToOnlineAgents / heartbeat (sendHeartbeat / checkHeartbeatTimeout)
// Mocks WebSocket / window.location / localStorage, consistent with the useTerminal.test.js style.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useGatewayConnection } from './useGatewayConnection.js'

// ---- Mock the global environment ----
function setupGlobals() {
  // WebSocket
  class MockWebSocket {
    constructor(url, protocols) {
      this.url = url
      this.protocols = protocols
      this.readyState = 1 // OPEN
      this.send = vi.fn()
      this.close = vi.fn()
      this.onopen = null
      this.onmessage = null
      this.onclose = null
      this.onerror = null
      this._connectionCompleted = false // Pre-declared so it can still be assigned after preventExtensions
      // Prevent deep reactive proxying by vue refs so socket.value === ws (matching real browser behavior)
      Object.preventExtensions(this)
      MockWebSocket.instances.push(this)
    }
  }
  MockWebSocket.OPEN = 1
  MockWebSocket.CONNECTING = 0
  MockWebSocket.CLOSED = 3
  MockWebSocket.instances = []
  globalThis.WebSocket = MockWebSocket

  // window.location (used by buildDefaultGatewayUrl)
  Object.defineProperty(globalThis, 'location', {
    value: { protocol: 'http:', hostname: 'localhost', reload: vi.fn() },
    writable: true,
    configurable: true,
  })

  // window.confirm (used by disconnectAll)
  globalThis.confirm = vi.fn(() => true)
  globalThis.alert = vi.fn()
}

function makeHarness() {
  setupGlobals()
  const socket = ref(null)
  const sockets = ref(new Map())
  const auth = ref({ password: 'pw', token: '', userInfo: null })
  const username = ref('tester')
  const myClientId = ref('')
  const terminalSessions = ref([])
  const allOutputs = ref(new Map())
  const currentAgentId = ref('agent-1')
  const agentList = ref([])
  const agentStatuses = ref(new Map())
  const showConnectModal = ref(true)
  const showSettingsModal = ref(false)
  const autoLoginEnabled = ref(false)
  const userAccessibleNodes = ref(null)
  const gitCustomDir = ref(null)

  const parseGatewayAddress = vi.fn((address) => {
    const m = address.match(/^ws:\/\/([^:/]+):(\d+)$/)
    return m ? { host: m[1], port: m[2], protocol: null } : null
  })
  const buildWebSocketUrl = vi.fn((host, port, protocol) => `ws://${host}:${port}`)
  const buildWebSocketProtocols = vi.fn(() => [])
  const buildAgentWebSocketUrl = vi.fn((host, agentId, protocol, port, nodeId) => `ws://${host}:${port}/agent/${agentId}?node=${nodeId}`)
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const buildNodeHttpUrl = vi.fn((host, port, nodeId, path) => `http://${host}:${port}/api/node/${nodeId}/${path}`)
  const fetchWithAuth = vi.fn()
  const loginWithPassword = vi.fn(async () => {})
  const hasAuthToken = vi.fn(() => true)
  const startAgentListRefresh = vi.fn()
  const startNodeStatusRefresh = vi.fn()
  const restoreVirtualWorkspaceDirs = vi.fn()
  const loadGitCustomDir = vi.fn(() => null)
  const refreshUserInfo = vi.fn(async () => {})
  const fetchUserPermissions = vi.fn()
  const fetchModelGroups = vi.fn()
  const fetchNodeStatus = vi.fn()
  const fetchUserAccessibleNodes = vi.fn()
  const restoreTerminalSessions = vi.fn()
  const getOrCreateClientId = vi.fn(() => 'client-test')
  const sendChatMessageToServer = vi.fn()
  const loadHistoryMessages = vi.fn()
  const closeTerminal = vi.fn()
  const handleMessage = vi.fn()
  const getAgentLastSeq = vi.fn(() => 0)
  const showToast = vi.fn()
  const showConfirm = vi.fn()

  const api = useGatewayConnection({
    socket,
    sockets,
    auth,
    username,
    myClientId,
    terminalSessions,
    allOutputs,
    currentAgentId,
    agentList,
    agentStatuses,
    showConnectModal,
    showSettingsModal,
    autoLoginEnabled,
    userAccessibleNodes,
    gitCustomDir,
    parseGatewayAddress,
    buildWebSocketUrl,
    buildWebSocketProtocols,
    buildAgentWebSocketUrl,
    getGatewayAddress,
    buildNodeHttpUrl,
    fetchWithAuth,
    loginWithPassword,
    hasAuthToken,
    startAgentListRefresh,
    startNodeStatusRefresh,
    restoreVirtualWorkspaceDirs,
    loadGitCustomDir,
    refreshUserInfo,
    fetchUserPermissions,
    fetchModelGroups,
    fetchNodeStatus,
    fetchUserAccessibleNodes,
    restoreTerminalSessions,
    getOrCreateClientId,
    sendChatMessageToServer,
    loadHistoryMessages,
    closeTerminal,
    handleMessage,
    getAgentLastSeq,
    showToast,
    showConfirm,
  })

  return {
    api, socket, sockets, auth, username, myClientId, terminalSessions, allOutputs,
    currentAgentId, agentList, agentStatuses, showConnectModal, showSettingsModal,
    autoLoginEnabled, userAccessibleNodes, gitCustomDir,
    lastPongTime: api.lastPongTime, connectingAgents: api.connectingAgents,
    userDisconnected: api.userDisconnected, isAutoConnecting: api.isAutoConnecting,
    reconnecting: api.reconnecting, reconnectAttempts: api.reconnectAttempts,
    reconnectTimer: api.reconnectTimer, connecting: api.connecting,
    agentConnecting: api.agentConnecting, connectErrorMessage: api.connectErrorMessage,
    isRestartingGateway: api.isRestartingGateway, restartNodeId: api.restartNodeId,
    restartFrontendService: api.restartFrontendService,
    parseGatewayAddress, buildWebSocketUrl, buildWebSocketProtocols, buildAgentWebSocketUrl,
    getGatewayAddress, buildNodeHttpUrl, fetchWithAuth, loginWithPassword, hasAuthToken,
    startAgentListRefresh, startNodeStatusRefresh, restoreVirtualWorkspaceDirs, loadGitCustomDir,
    refreshUserInfo, fetchUserPermissions, fetchModelGroups, fetchNodeStatus, fetchUserAccessibleNodes,
    restoreTerminalSessions, getOrCreateClientId, sendChatMessageToServer, loadHistoryMessages,
    closeTerminal, handleMessage, getAgentLastSeq, showToast, showConfirm,
  }
}

describe('useGatewayConnection', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('exposes the expected interface', () => {
    const { api } = makeHarness()
    expect(typeof api.connect).toBe('function')
    expect(typeof api.disconnect).toBe('function')
    expect(typeof api.reconnect).toBe('function')
    expect(typeof api.disconnectAll).toBe('function')
    expect(typeof api.handleRestartGateway).toBe('function')
    expect(typeof api.confirmRestartGateway).toBe('function')
    expect(typeof api.restartGateway).toBe('function')
    expect(typeof api.connectToAgent).toBe('function')
    expect(typeof api.autoConnectToOnlineAgents).toBe('function')
    expect(typeof api.checkHeartbeatTimeout).toBe('function')
    expect(typeof api.sendHeartbeat).toBe('function')
  })

  it('initial state: offline and disconnected', () => {
    const { api } = makeHarness()
    expect(api.connectionStatus.value).toBe('offline')
    expect(api.connectionLabel.value).toBe('Disconnected')
    expect(api.connecting.value).toBe(false)
    expect(api.reconnecting.value).toBe(false)
    expect(api.userDisconnected.value).toBe(false)
    expect(api.HEARTBEAT_INTERVAL).toBe(5000)
    expect(api.HEARTBEAT_TIMEOUT).toBe(15000)
    expect(api.reconnectInterval).toBe(5000)
  })

  it('gatewayUrl defaults to localStorage or the current domain', () => {
    const { api } = makeHarness()
    // When localStorage has no value, use buildDefaultGatewayUrl: ws://localhost:8000
    expect(api.gatewayUrl.value).toBe('ws://localhost:8000')
  })

  it('gatewayUrl prefers the saved localStorage value', () => {
    localStorage.setItem('haijunbot_gateway_url', 'ws://myhost:9000')
    const { api } = makeHarness()
    expect(api.gatewayUrl.value).toBe('ws://myhost:9000')
  })

  describe('connectionStatus / connectionLabel', () => {
    it('shows Connecting while connecting', () => {
      const { api } = makeHarness()
      api.connecting.value = true
      expect(api.connectionStatus.value).toBe('connecting')
      expect(api.connectionLabel.value).toBe('Connecting')
    })

    it('shows Reconnecting while reconnecting', () => {
      const { api } = makeHarness()
      api.reconnecting.value = true
      expect(api.connectionStatus.value).toBe('reconnecting')
      expect(api.connectionLabel.value).toBe('Reconnecting')
    })

    it('shows Connected when a socket exists', () => {
      const { api, socket } = makeHarness()
      socket.value = { readyState: 1 }
      expect(api.connectionStatus.value).toBe('online')
      expect(api.connectionLabel.value).toBe('Connected')
    })
  })

  describe('connect', () => {
    it('does not reconnect when already connected', async () => {
      const { api, socket, parseGatewayAddress } = makeHarness()
      socket.value = { readyState: 1 }
      await api.connect()
      expect(parseGatewayAddress).not.toHaveBeenCalled()
    })

    it('sets an error message for an invalid gateway address', async () => {
      const { api } = makeHarness()
      api.gatewayUrl.value = 'invalid-address'
      await api.connect()
      expect(api.connectErrorMessage.value).toBe('Invalid gateway address format')
    })

    it('calls loginWithPassword when there is no token', async () => {
      const { api, hasAuthToken, loginWithPassword, socket, showConnectModal } = makeHarness()
      hasAuthToken.mockReturnValue(false)
      await api.connect()
      expect(loginWithPassword).toHaveBeenCalledWith('pw')
      // Still no token after login → login failed
      expect(api.connectErrorMessage.value).toBe('Login failed, please try again')
      expect(socket.value).toBe(null)
      expect(showConnectModal.value).toBe(true)
    })

    it('sets an error message on login failure and does not establish a connection', async () => {
      const { api, hasAuthToken, loginWithPassword, socket } = makeHarness()
      hasAuthToken.mockReturnValue(false)
      loginWithPassword.mockRejectedValue(new Error('bad credentials'))
      await api.connect()
      expect(api.connectErrorMessage.value).toBe('bad credentials')
      expect(socket.value).toBe(null)
    })

    it('success: onopen establishes the socket and starts the initialization flow', async () => {
      const { api, socket, showConnectModal, startAgentListRefresh, startNodeStatusRefresh,
        restoreVirtualWorkspaceDirs, loadGitCustomDir, refreshUserInfo, fetchUserPermissions,
        fetchModelGroups, fetchNodeStatus, fetchUserAccessibleNodes,
        restoreTerminalSessions, myClientId, getOrCreateClientId, sendChatMessageToServer,
        loadHistoryMessages } = makeHarness()
      await api.connect()
      // Trigger onopen to establish the connection
      const ws = globalThis.WebSocket.instances[0]
      ws.onopen()
      // Wait for async callbacks such as refreshUserInfo().finally(...) to complete
      await new Promise(r => setTimeout(r, 0))
      // socket.value is a deeply reactive ref proxy, so it cannot be compared with the raw ws using toBe; assert the url instead
      expect(socket.value).not.toBe(null)
      expect(socket.value.url).toBe(ws.url)
      expect(showConnectModal.value).toBe(false)
      expect(api.connectionStatus.value).toBe('online')
      expect(startAgentListRefresh).toHaveBeenCalled()
      expect(startNodeStatusRefresh).toHaveBeenCalled()
      expect(restoreVirtualWorkspaceDirs).toHaveBeenCalled()
      expect(loadGitCustomDir).toHaveBeenCalled()
      expect(refreshUserInfo).toHaveBeenCalled()
      expect(fetchUserPermissions).toHaveBeenCalled()
      // autoConnectToOnlineAgents is an internal closure function that cannot be spied directly,
      // so the flow is verified through initialization side effects like fetchModelGroups/fetchNodeStatus
      expect(fetchModelGroups).toHaveBeenCalled()
      expect(fetchNodeStatus).toHaveBeenCalled()
      expect(fetchUserAccessibleNodes).toHaveBeenCalled()
      expect(restoreTerminalSessions).toHaveBeenCalled()
      // Auto-register the chat room
      expect(getOrCreateClientId).toHaveBeenCalled()
      expect(myClientId.value).toBe('client-test')
      expect(sendChatMessageToServer).toHaveBeenCalledWith('chat_register', { client_id: 'client-test', name: 'tester' })
      // Load history messages when there is no historical output
      expect(loadHistoryMessages).toHaveBeenCalledWith(false)
    })

    it('onmessage parses JSON and passes it to handleMessage', async () => {
      const { api, socket, handleMessage } = makeHarness()
      await api.connect()
      const ws = globalThis.WebSocket.instances[0]
      ws.onopen()
      ws.onmessage({ data: JSON.stringify({ type: 'hello', payload: {} }) })
      expect(handleMessage).toHaveBeenCalledWith({ type: 'hello', payload: {} })
    })

    it('onmessage ignores messages from the old connection', async () => {
      const { api, socket, handleMessage } = makeHarness()
      await api.connect()
      const oldWs = globalThis.WebSocket.instances[0]
      oldWs.onopen()
      // Simulate a reconnect where socket points to the new connection; messages received by the old connection should be ignored
      socket.value = { readyState: 1 }
      oldWs.onmessage({ data: JSON.stringify({ type: 'stale' }) })
      expect(handleMessage).not.toHaveBeenCalled()
    })

    it('onclose destroys all standalone terminals', async () => {
      const { api, socket, terminalSessions, closeTerminal } = makeHarness()
      terminalSessions.value = [{ terminal_id: 't1' }, { terminal_id: 't2' }]
      await api.connect()
      const ws = globalThis.WebSocket.instances[0]
      ws.onopen()
      ws.onclose({ code: 1000, reason: 'bye' })
      expect(closeTerminal).toHaveBeenCalledTimes(2)
      expect(closeTerminal).toHaveBeenCalledWith('t1')
      expect(closeTerminal).toHaveBeenCalledWith('t2')
    })

    it('onclose triggers auto-reconnect when the user did not disconnect and a token exists', async () => {
      const { api, socket, reconnectTimer } = makeHarness()
      await api.connect()
      const ws = globalThis.WebSocket.instances[0]
      ws.onopen()
      ws.onclose({ code: 1006, reason: '' })
      expect(api.reconnecting.value).toBe(true)
      expect(api.reconnectAttempts.value).toBe(1)
      expect(reconnectTimer.value).not.toBe(null)
    })

    it('onclose does not reconnect when the user disconnected', async () => {
      const { api, socket, userDisconnected } = makeHarness()
      await api.connect()
      const ws = globalThis.WebSocket.instances[0]
      ws.onopen()
      userDisconnected.value = true
      ws.onclose({ code: 1000, reason: 'bye' })
      expect(api.reconnecting.value).toBe(false)
      expect(api.reconnectAttempts.value).toBe(0)
      expect(api.reconnectAttempts.value).toBe(0)
    })
  })

  describe('disconnect', () => {
    it('sets the user-initiated disconnect flag and closes the connection', () => {
      const { api, socket, userDisconnected } = makeHarness()
      socket.value = { readyState: 1, close: vi.fn() }
      api.disconnect()
      expect(userDisconnected.value).toBe(true)
      expect(socket.value.close).toHaveBeenCalled()
    })

    it('is safe to call with no connection', () => {
      const { api } = makeHarness()
      api.disconnect()
      expect(api.userDisconnected.value).toBe(true)
    })
  })

  describe('reconnect', () => {
    it('closes the existing connection and reconnects', async () => {
      const { api, socket, showSettingsModal } = makeHarness()
      socket.value = { readyState: 1, close: vi.fn() }
      await api.reconnect()
      expect(socket.value.close).toHaveBeenCalled()
      expect(showSettingsModal.value).toBe(false)
      // reconnect internally calls connect, which creates a new connection
      expect(socket.value).not.toBe(null)
    })
  })

  describe('disconnectAll', () => {
    it('does not disconnect when the user cancels', () => {
      const { api, socket } = makeHarness()
      globalThis.confirm.mockReturnValue(false)
      socket.value = { readyState: 1, close: vi.fn() }
      api.disconnectAll()
      expect(socket.value.close).not.toHaveBeenCalled()
    })

    it('closes all connections and clears state after confirmation', () => {
      const { api, socket, sockets, currentAgentId, agentList, agentStatuses, auth, userAccessibleNodes, autoLoginEnabled } = makeHarness()
      const agentWs = { readyState: 1, close: vi.fn() }
      sockets.value.set('agent-1', agentWs)
      const mainWs = { readyState: 1, close: vi.fn() }
      socket.value = mainWs
      currentAgentId.value = 'agent-1'
      agentList.value = [{ agent_id: 'agent-1' }]
      agentStatuses.value.set('agent-1', {})
      auth.value.token = 'tok'
      userAccessibleNodes.value = ['n1']
      autoLoginEnabled.value = true
      api.disconnectAll()
      expect(agentWs.close).toHaveBeenCalled()
      expect(mainWs.close).toHaveBeenCalled()
      expect(sockets.value.size).toBe(0)
      expect(currentAgentId.value).toBe(null)
      expect(agentList.value).toEqual([])
      expect(agentStatuses.value.size).toBe(0)
      expect(auth.value.token).toBe('')
      expect(userAccessibleNodes.value).toBe(null)
      expect(autoLoginEnabled.value).toBe(false)
      expect(localStorage.getItem('haijunbot_auth_token')).toBe(null)
    })
  })

  describe('handleRestartGateway / confirmRestartGateway', () => {
    it('handleRestartGateway records the node and shows the confirm dialog', () => {
      const { api, restartNodeId, restartFrontendService, showConfirm } = makeHarness()
      api.handleRestartGateway({ nodeId: 'node-9', restartFrontend: true })
      expect(restartNodeId.value).toBe('node-9')
      expect(restartFrontendService.value).toBe(true)
      expect(showConfirm).toHaveBeenCalled()
    })

    it('confirmRestartGateway calls restartGateway after confirmation', async () => {
      const { api, showConfirm, fetchWithAuth, buildNodeHttpUrl, getGatewayAddress, showToast } = makeHarness()
      // restartGateway is an internal closure function that cannot be spied directly, so verify its side effects:
      // once the confirm callback fires, restartGateway sends an HTTP restart request
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { message: 'Restarting' } }),
      })
      api.confirmRestartGateway()
      expect(showConfirm).toHaveBeenCalled()
      // Extract and run the confirm callback
      const confirmCb = showConfirm.mock.calls[0][1]
      confirmCb()
      await new Promise(r => setTimeout(r, 0))
      expect(getGatewayAddress).toHaveBeenCalled()
      expect(buildNodeHttpUrl).toHaveBeenCalledWith('127.0.0.1', '8000', 'master', 'service/restart')
      expect(showToast).toHaveBeenCalledWith('Restarting', 'success')
    })

    it('does not show the dialog twice while a restart is in progress', () => {
      const { api, showConfirm, isRestartingGateway } = makeHarness()
      isRestartingGateway.value = true
      api.confirmRestartGateway()
      expect(showConfirm).not.toHaveBeenCalled()
    })
  })

  describe('restartGateway', () => {
    it('sends the restart request and reports success', async () => {
      const { api, fetchWithAuth, buildNodeHttpUrl, getGatewayAddress, showToast, isRestartingGateway } = makeHarness()
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, data: { message: 'Restarting' } }),
      })
      await api.restartGateway()
      expect(getGatewayAddress).toHaveBeenCalled()
      expect(buildNodeHttpUrl).toHaveBeenCalledWith('127.0.0.1', '8000', 'master', 'service/restart')
      expect(showToast).toHaveBeenCalledWith('Restarting', 'success')
    })

    it('reports an error when the backend returns failure', async () => {
      const { api, fetchWithAuth, showToast } = makeHarness()
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ success: false, error: { message: 'Service is not running' } }),
      })
      await api.restartGateway()
      expect(showToast).toHaveBeenCalledWith('Service is not running', 'error')
    })

    it('reports an error when the request throws', async () => {
      const { api, fetchWithAuth, showToast } = makeHarness()
      fetchWithAuth.mockRejectedValue(new Error('network down'))
      await api.restartGateway()
      expect(showToast).toHaveBeenCalledWith('network down', 'error')
    })
  })

  describe('connectToAgent', () => {
    it('returns null directly when the connection lock exists', async () => {
      const { api, connectingAgents } = makeHarness()
      connectingAgents.value.add('agent-1')
      const result = await api.connectToAgent({ agent_id: 'agent-1' })
      expect(result).toBe(null)
    })

    it('reuses an existing valid connection and sends get_status', async () => {
      const { api, sockets } = makeHarness()
      const existingWs = { readyState: 1, send: vi.fn() }
      sockets.value.set('agent-1', existingWs)
      const result = await api.connectToAgent({ agent_id: 'agent-1' })
      // result is the reactive proxy of existingWs in sockets.value and cannot be compared with toBe; assert behavior instead
      expect(result.readyState).toBe(1)
      expect(result.send).toHaveBeenCalledWith(JSON.stringify({ type: 'get_status', payload: {} }))
    })

    it('successfully establishes a connection: saves the socket, sends sync_request, and resolves ws', async () => {
      const { api, sockets, getAgentLastSeq, allOutputs, agentConnecting } = makeHarness()
      const promise = api.connectToAgent({ agent_id: 'agent-1', node_id: 'node-1' })
      const ws = globalThis.WebSocket.instances[globalThis.WebSocket.instances.length - 1]
      // Trigger onopen
      ws.onopen()
      const result = await promise
      expect(result).toBe(ws)
      // sockets.value stores the reactive proxy of ws; assert the url matches
      expect(sockets.value.get('agent-1').url).toBe(ws.url)
      expect(agentConnecting.value).toBe(false)
      expect(allOutputs.value.has('agent-1')).toBe(true)
      expect(ws.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'sync_request',
        payload: { agent_seqs: { 'agent-1': 0 } },
      }))
    })

    it('onmessage updates lastPongTime on a pong and does not pass it to handleMessage', async () => {
      const { api, sockets, lastPongTime, handleMessage } = makeHarness()
      const promise = api.connectToAgent({ agent_id: 'agent-1' })
      const ws = globalThis.WebSocket.instances[globalThis.WebSocket.instances.length - 1]
      ws.onopen()
      await promise
      // lastPongTime is not recorded when the connection is established; a received pong should write the timestamp
      expect(lastPongTime.value.has('agent-1')).toBe(false)
      ws.onmessage({ data: JSON.stringify({ type: 'pong' }) })
      expect(lastPongTime.value.get('agent-1')).toBeTypeOf('number')
      expect(handleMessage).not.toHaveBeenCalled()
    })

    it('onmessage passes ordinary messages to handleMessage (with agentId)', async () => {
      const { api, sockets, handleMessage } = makeHarness()
      const promise = api.connectToAgent({ agent_id: 'agent-1' })
      const ws = globalThis.WebSocket.instances[globalThis.WebSocket.instances.length - 1]
      ws.onopen()
      await promise
      ws.onmessage({ data: JSON.stringify({ type: 'output', payload: {} }) })
      expect(handleMessage).toHaveBeenCalledWith({ type: 'output', payload: {} }, 'agent-1')
    })

    it('connection timeout: rejects and cleans up the connection state', async () => {
      const { api, sockets, connectingAgents, agentConnecting } = makeHarness()
      // Use fake timers to speed up the timeout
      vi.useFakeTimers()
      const promise2 = api.connectToAgent({ agent_id: 'agent-2' })
      vi.advanceTimersByTime(10000)
      await expect(promise2).rejects.toThrow('Connection timeout')
      expect(sockets.value.has('agent-2')).toBe(false)
      expect(connectingAgents.value.has('agent-2')).toBe(false)
      expect(agentConnecting.value).toBe(false)
      vi.useRealTimers()
    })
  })

  describe('autoConnectToOnlineAgents', () => {
    it('returns directly when there are no online agents', async () => {
      const { api, agentList, sockets } = makeHarness()
      agentList.value = [{ agent_id: 'a1', status: 'stopped' }]
      await api.autoConnectToOnlineAgents()
      // No connections are established when there are no online agents
      expect(sockets.value.size).toBe(0)
      expect(globalThis.WebSocket.instances.length).toBe(0)
    })
    it('connects to online agents one by one and keeps the current selection unchanged', async () => {
      const { api, agentList, sockets, currentAgentId } = makeHarness()
      agentList.value = [
        { agent_id: 'a1', status: 'running' },
        { agent_id: 'a2', status: 'running' },
      ]
      currentAgentId.value = 'keep-me'
      // autoConnectToOnlineAgents awaits connectToAgent one by one internally (with a 500ms interval),
      // so each agent's onopen must be triggered step by step
      const p = api.autoConnectToOnlineAgents()
      // The first agent's ws is created synchronously
      const wsA1 = globalThis.WebSocket.instances[0]
      wsA1.onopen()
      // Wait for the 500ms interval before the second agent's ws is created
      await new Promise(r => setTimeout(r, 600))
      const wsA2 = globalThis.WebSocket.instances[1]
      wsA2.onopen()
      await p
      expect(currentAgentId.value).toBe('keep-me')
      expect(sockets.value.has('a1')).toBe(true)
      expect(sockets.value.has('a2')).toBe(true)
    })
  })

  describe('heartbeat', () => {
    it('sendHeartbeat sends a ping to all open connections and records the time', () => {
      const { api, sockets, lastPongTime } = makeHarness()
      const ws1 = { readyState: 1, send: vi.fn() }
      const ws2 = { readyState: 1, send: vi.fn() }
      sockets.value.set('a1', ws1)
      sockets.value.set('a2', ws2)
      api.sendHeartbeat()
      expect(ws1.send).toHaveBeenCalledWith(JSON.stringify({ type: 'ping' }))
      expect(ws2.send).toHaveBeenCalledWith(JSON.stringify({ type: 'ping' }))
      expect(lastPongTime.value.has('a1')).toBe(true)
      expect(lastPongTime.value.has('a2')).toBe(true)
    })

    it('sendHeartbeat skips connections that are not open', () => {
      const { api, sockets } = makeHarness()
      const wsClosed = { readyState: 3, send: vi.fn() }
      sockets.value.set('a1', wsClosed)
      api.sendHeartbeat()
      expect(wsClosed.send).not.toHaveBeenCalled()
    })

    it('checkHeartbeatTimeout cleans up timed-out connections and triggers a reconnect of the current Agent', () => {
      const { api, sockets, lastPongTime, connectingAgents, currentAgentId, agentList } = makeHarness()
      const ws = { readyState: 1, close: vi.fn() }
      sockets.value.set('a1', ws)
      // Timeout: no lastPong
      lastPongTime.value.delete('a1')
      currentAgentId.value = 'a1'
      const agent = { agent_id: 'a1' }
      agentList.value = [agent]
      const wsCountBefore = globalThis.WebSocket.instances.length
      api.checkHeartbeatTimeout()
      expect(ws.close).toHaveBeenCalled()
      expect(sockets.value.has('a1')).toBe(false)
      // After triggering a reconnect, connectToAgent re-acquires the connection lock (reconnect in progress)
      expect(connectingAgents.value.has('a1')).toBe(true)
      // connectToAgent is an internal closure function that cannot be spied directly, so verify its side effects:
      // triggering a reconnect creates a new WebSocket connection
      expect(globalThis.WebSocket.instances.length).toBe(wsCountBefore + 1)
    })

    it('checkHeartbeatTimeout keeps connections that have not timed out', () => {
      const { api, sockets, lastPongTime } = makeHarness()
      const ws = { readyState: 1, close: vi.fn() }
      sockets.value.set('a1', ws)
      lastPongTime.value.set('a1', Date.now())
      api.checkHeartbeatTimeout()
      expect(ws.close).not.toHaveBeenCalled()
      expect(sockets.value.has('a1')).toBe(true)
    })
  })
})
