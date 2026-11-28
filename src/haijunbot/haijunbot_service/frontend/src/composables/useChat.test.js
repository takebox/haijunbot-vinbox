// useChat unit tests
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed } from 'vue'
import { useChat } from './useChat.js'

// Build a useChat dependency-injection harness
function makeHarness({ socketOpen = true } = {}) {
  const socket = ref(socketOpen ? { readyState: WebSocket.OPEN, send: vi.fn() } : { readyState: WebSocket.CLOSED, send: vi.fn() })
  const auth = ref({ token: 'test-token', userInfo: { user_id: 'u1', display_name: 'Test User' } })
  const username = ref('tester')
  const windowWidth = ref(1200)
  const activeWindow = ref(null)
  const showChatPanel = ref(false)
  const focusWindow = vi.fn()
  const showToast = vi.fn()
  const showConfirm = vi.fn((msg, cb) => cb && cb())
  const playChatNotificationSound = vi.fn()
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const workspaceHostsChat = computed(() => false)
  const setWorkspaceMainView = vi.fn()
  const showWorkspaceHostView = vi.fn()
  const clamp = (v, min, max) => Math.min(Math.max(v, min), max)
  const PANEL_DRAG_ACTIVATION_DISTANCE = 4
  const ACTIVE_Z_INDEX = 1100
  const BASE_Z_INDEX = 1000

  const api = useChat({
    socket,
    auth,
    username,
    windowWidth,
    activeWindow,
    showChatPanel,
    focusWindow,
    showToast,
    showConfirm,
    playChatNotificationSound,
    getGatewayAddress,
    workspaceHostsChat,
    setWorkspaceMainView,
    showWorkspaceHostView,
    clamp,
    PANEL_DRAG_ACTIVATION_DISTANCE,
    ACTIVE_Z_INDEX,
    BASE_Z_INDEX,
  })
  return { api, socket, auth, username, windowWidth, activeWindow, showChatPanel, focusWindow, showToast, showConfirm, playChatNotificationSound, getGatewayAddress, workspaceHostsChat, setWorkspaceMainView, showWorkspaceHostView }
}

// Clear localStorage (read during useChat initialization)
beforeEach(() => {
  localStorage.clear()
})

describe('useChat', () => {
  it('exposes the expected interface', () => {
    const { api } = makeHarness()
    // State (ref/computed)
    expect(typeof api.chatPanelRect).toBe('object')
    expect(typeof api.chatPanelCollapsed).toBe('object')
    expect(typeof api.chatPanelInteraction).toBe('object')
    expect(typeof api.chatPanelStyle).toBe('object')
    expect(typeof api.chatRooms).toBe('object')
    expect(typeof api.chatMessages).toBe('object')
    expect(typeof api.chatClients).toBe('object')
    expect(typeof api.chatRoomMembers).toBe('object')
    expect(typeof api.myClientId).toBe('object')
    expect(typeof api.activeChatRoomId).toBe('object')
    expect(typeof api.activePrivateClientId).toBe('object')
    expect(typeof api.chatUnreadCount).toBe('object')
    expect(typeof api.chatName).toBe('object')
    expect(typeof api.myUserId).toBe('object')
    expect(typeof api.chatSidebarWidth).toBe('object')
    expect(typeof api.chatUnreadMap).toBe('object')
    expect(typeof api.chatJoinedRooms).toBe('object')
    // Functions
    for (const fn of ['startChatSidebarResize', 'startChatPanelMove', 'startChatPanelResize', 'toggleChatPanel', 'toggleChatPanelCollapse', 'sendChatMessageToServer', 'createChatRoom', 'joinChatRoom', 'leaveChatRoom', 'deleteChatRoom', 'renameChatRoom', 'clearChatMessages', 'sendChatMessage', 'selectPrivateClient', 'handleChatMessage', 'getOrCreateClientId', 'restoreChatRoomsFromServer']) {
      expect(typeof api[fn]).toBe('function')
    }
  })

  it('initial state', () => {
    const { api } = makeHarness()
    expect(api.chatPanelCollapsed.value).toBe(false)
    expect(api.chatRooms.value).toEqual([])
    expect(api.chatMessages.value).toEqual({})
    expect(api.chatClients.value).toEqual([])
    expect(api.chatRoomMembers.value).toEqual([])
    expect(api.myClientId.value).toBe('')
    expect(api.activeChatRoomId.value).toBe('')
    expect(api.activePrivateClientId.value).toBe('')
    expect(api.chatUnreadCount.value).toBe(0)
    expect(api.chatJoinedRooms.value).toEqual([])
  })

  describe('sendChatMessageToServer', () => {
    it('sends a JSON message when the socket is open', () => {
      const { api, socket } = makeHarness()
      api.sendChatMessageToServer('chat_get_rooms', {})
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({ type: 'chat_get_rooms', payload: {} }))
    })

    it('does not send when the socket is closed', () => {
      const { api, socket } = makeHarness({ socketOpen: false })
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      api.sendChatMessageToServer('chat_get_rooms', {})
      expect(socket.value.send).not.toHaveBeenCalled()
      warnSpy.mockRestore()
    })
  })

  describe('handleChatMessage', () => {
    it('chat_message broadcast: appends the message and bumps the unread count', () => {
      const { api, showChatPanel, activeWindow, playChatNotificationSound } = makeHarness()
      showChatPanel.value = false
      activeWindow.value = 'terminal'
      api.handleChatMessage('chat_message', {
        client_id: 'client_b',
        sender_name: 'bob',
        content: 'hello',
        room_id: 'room1',
        timestamp: 123,
      })
      expect(api.chatMessages.value['room1']).toHaveLength(1)
      expect(api.chatMessages.value['room1'][0].content).toBe('hello')
      expect(api.chatMessages.value['room1'][0].client_name).toBe('bob')
      expect(api.chatUnreadCount.value).toBe(1)
      expect(api.chatUnreadMap.value['room1']).toBe(1)
      expect(playChatNotificationSound).toHaveBeenCalled()
    })

    it('chat_message sent by self is filtered out', () => {
      const { api } = makeHarness()
      api.myClientId.value = 'client_me'
      api.handleChatMessage('chat_message', { client_id: 'client_me', content: 'self', room_id: 'room1' })
      expect(api.chatMessages.value['room1']).toBeUndefined()
    })

    it('chat_private_message: appends the private message', () => {
      const { api } = makeHarness()
      api.handleChatMessage('chat_private_message', {
        message: { sender_id: 'client_b', sender_name: 'bob', content: 'hi', timestamp: 456 },
      })
      const key = 'private_client_b'
      expect(api.chatMessages.value[key]).toHaveLength(1)
      expect(api.chatMessages.value[key][0].content).toBe('hi')
      expect(api.chatMessages.value[key][0].private).toBe(true)
    })

    it('chat_register_response success: updates myClientId and adds the online user', () => {
      const { api } = makeHarness()
      api.handleChatMessage('chat_register_response', {
        success: true,
        client_id: 'client_me',
        user_id: 'u1',
        name: 'tester',
        display_name: 'Test User',
      })
      expect(api.myClientId.value).toBe('client_me')
      expect(api.chatClients.value).toHaveLength(1)
      expect(api.chatClients.value[0].client_id).toBe('client_me')
    })

    it('chat_get_rooms_response: updates the room list', () => {
      const { api } = makeHarness()
      api.handleChatMessage('chat_get_rooms_response', { rooms: [{ room_id: 'r1', name: 'Room 1' }] })
      expect(api.chatRooms.value).toHaveLength(1)
      expect(api.chatRooms.value[0].room_id).toBe('r1')
    })

    it('chat_leave_room_response success: removes the room and clears its messages', () => {
      const { api } = makeHarness()
      api.chatJoinedRooms.value = ['r1']
      api.chatMessages.value = { r1: [{ content: 'x' }] }
      api.activeChatRoomId.value = 'r1'
      api.handleChatMessage('chat_leave_room_response', { success: true, room_id: 'r1' })
      expect(api.chatJoinedRooms.value).toEqual([])
      expect(api.chatMessages.value['r1']).toBeUndefined()
      expect(api.activeChatRoomId.value).toBe('')
    })
  })

  describe('sendChatMessage', () => {
    it('private-chat mode: sends a private message and appends it locally', () => {
      const { api, socket } = makeHarness()
      api.myClientId.value = 'client_me'
      api.activePrivateClientId.value = 'client_b'
      api.sendChatMessage('hello', null)
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_send_private',
        payload: { sender_id: 'client_me', receiver_id: 'client_b', content: 'hello' },
      }))
      const key = 'private_client_b'
      expect(api.chatMessages.value[key]).toHaveLength(1)
      expect(api.chatMessages.value[key][0].content).toBe('hello')
    })

    it('room mode: sends a group message and appends it locally', () => {
      const { api, socket } = makeHarness()
      api.myClientId.value = 'client_me'
      api.activeChatRoomId.value = 'room1'
      api.sendChatMessage('hello room', null)
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_send_message',
        payload: { room_id: 'room1', client_id: 'client_me', content: 'hello room' },
      }))
      expect(api.chatMessages.value['room1']).toHaveLength(1)
      expect(api.chatMessages.value['room1'][0].content).toBe('hello room')
    })

    it('prompts when there is no target', () => {
      const { api, showToast } = makeHarness()
      api.sendChatMessage('hello', null)
      expect(showToast).toHaveBeenCalledWith('Join a chat room or pick a private chat target first', 'warning')
    })

    it('does not send when the content is empty and there is no image', () => {
      const { api, socket } = makeHarness()
      api.activeChatRoomId.value = 'room1'
      api.sendChatMessage('   ', null)
      expect(socket.value.send).not.toHaveBeenCalled()
    })
  })

  describe('chat room operations', () => {
    it('createChatRoom sends a creation request', () => {
      const { api, socket } = makeHarness()
      api.myClientId.value = 'client_me'
      api.createChatRoom('New Room')
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_create_room',
        payload: { name: 'New Room', client_id: 'client_me' },
      }))
    })

    it('joinChatRoom sets the active room and clears unread', () => {
      const { api, socket } = makeHarness()
      api.myClientId.value = 'client_me'
      api.chatUnreadMap.value = { room1: 3 }
      api.joinChatRoom('room1')
      expect(api.activeChatRoomId.value).toBe('room1')
      expect(api.chatUnreadMap.value['room1']).toBeUndefined()
      // Sends join for rooms not yet joined
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_join_room',
        payload: { room_id: 'room1', client_id: 'client_me' },
      }))
    })

    it('joinChatRoom only fetches members for already-joined rooms', () => {
      const { api, socket } = makeHarness()
      api.myClientId.value = 'client_me'
      api.chatJoinedRooms.value = ['room1']
      api.joinChatRoom('room1')
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_get_room_members',
        payload: { room_id: 'room1' },
      }))
    })

    it('leaveChatRoom sends a leave request', () => {
      const { api, socket } = makeHarness()
      api.myClientId.value = 'client_me'
      api.leaveChatRoom('room1')
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_leave_room',
        payload: { room_id: 'room1', client_id: 'client_me' },
      }))
    })

    it('deleteChatRoom shows a confirmation then sends a delete request', () => {
      const { api, socket, showConfirm } = makeHarness()
      api.myClientId.value = 'client_me'
      api.deleteChatRoom('room1')
      expect(showConfirm).toHaveBeenCalled()
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_delete_room',
        payload: { room_id: 'room1', client_id: 'client_me' },
      }))
    })

    it('renameChatRoom sends a rename request', () => {
      const { api, socket } = makeHarness()
      api.myClientId.value = 'client_me'
      api.renameChatRoom('room1', 'New Name')
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_rename_room',
        payload: { room_id: 'room1', client_id: 'client_me', new_name: 'New Name' },
      }))
    })

    it('clearChatMessages all: clears every message', () => {
      const { api, showConfirm } = makeHarness()
      api.chatMessages.value = { room1: [{ content: 'x' }] }
      api.clearChatMessages('all')
      expect(showConfirm).toHaveBeenCalled()
      expect(api.chatMessages.value).toEqual({})
    })

    it('selectPrivateClient switches the private target and fetches history', () => {
      const { api, socket } = makeHarness()
      api.myUserId.value = 'u1'
      api.selectPrivateClient('client_b')
      expect(api.activePrivateClientId.value).toBe('client_b')
      expect(socket.value.send).toHaveBeenCalledWith(JSON.stringify({
        type: 'chat_get_private_history',
        payload: { client_id: 'u1', other_id: 'client_b' },
      }))
    })

    it('selectPrivateClient toggles off when clicked again', () => {
      const { api } = makeHarness()
      api.activePrivateClientId.value = 'client_b'
      api.selectPrivateClient('client_b')
      expect(api.activePrivateClientId.value).toBe('')
    })
  })

  describe('toggleChatPanel', () => {
    it('registers the client and fetches rooms/users on first open', () => {
      const { api, socket, focusWindow, showWorkspaceHostView } = makeHarness()
      api.toggleChatPanel()
      expect(showWorkspaceHostView).toHaveBeenCalledWith('chat')
      expect(focusWindow).toHaveBeenCalledWith('chat')
      expect(api.myClientId.value).toBeTruthy()
      const sends = socket.value.send.mock.calls.map(c => JSON.parse(c[0]))
      expect(sends.some(s => s.type === 'chat_register')).toBe(true)
      expect(sends.some(s => s.type === 'chat_get_rooms')).toBe(true)
      expect(sends.some(s => s.type === 'chat_get_clients')).toBe(true)
    })

    it('collapses when the workspace hosts the chat (switching back to the file view)', () => {
      const { api, workspaceHostsChat, setWorkspaceMainView } = makeHarness()
      // Override workspaceHostsChat to true
      const orig = workspaceHostsChat.value
      Object.defineProperty(workspaceHostsChat, 'value', { get: () => true, configurable: true })
      api.toggleChatPanel()
      expect(setWorkspaceMainView).toHaveBeenCalledWith('file')
      Object.defineProperty(workspaceHostsChat, 'value', { get: () => orig, configurable: true })
    })
  })

  describe('toggleChatPanelCollapse', () => {
    it('toggles the collapsed state', () => {
      const { api } = makeHarness()
      expect(api.chatPanelCollapsed.value).toBe(false)
      api.toggleChatPanelCollapse()
      expect(api.chatPanelCollapsed.value).toBe(true)
      api.toggleChatPanelCollapse()
      expect(api.chatPanelCollapsed.value).toBe(false)
    })
  })

  describe('getOrCreateClientId', () => {
    it('generates and persists a clientId on first call', () => {
      const { api } = makeHarness()
      const id = api.getOrCreateClientId()
      expect(id).toMatch(/^client_/)
      expect(localStorage.getItem('haijunbot_chat_client_id')).toBe(id)
    })

    it('reuses an existing id', () => {
      const { api } = makeHarness()
      localStorage.setItem('haijunbot_chat_client_id', 'client_existing')
      expect(api.getOrCreateClientId()).toBe('client_existing')
    })
  })

  describe('chatPanelStyle', () => {
    it('full-screen on mobile', () => {
      const { api, windowWidth } = makeHarness()
      windowWidth.value = 700
      expect(api.chatPanelStyle.value.width).toBe('100vw')
    })

    it('uses the panel rect on desktop', () => {
      const { api } = makeHarness()
      api.chatPanelRect.value = { top: 88, left: 100, width: 800, height: 500 }
      expect(api.chatPanelStyle.value.width).toBe('800px')
      expect(api.chatPanelStyle.value.height).toBe('500px')
    })
  })
})
