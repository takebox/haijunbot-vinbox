// Chat room composable.
//
// Extracted from App.vue's <script setup> (originally handleChatMessage 16409-16653 + chat room panel 17598-18147), preserving behavior exactly:
// - Chat room panel: chatPanelRect / chatPanelCollapsed / chatPanelInteraction / chatPanelStyle (floating panel layout)
// - Chat room data: chatRooms / chatMessages / chatClients / chatRoomMembers / myClientId / activeChatRoomId /
//   activePrivateClientId / chatUnreadCount / chatName / myUserId / chatSidebarWidth / chatUnreadMap / chatJoinedRooms
// - Chat features: toggleChatPanel / sendChatMessageToServer / createChatRoom / joinChatRoom / leaveChatRoom /
//   deleteChatRoom / renameChatRoom / clearChatMessages / sendChatMessage / selectPrivateClient / toggleChatPanelCollapse
// - Panel interactions: startChatSidebarResize / startChatPanelMove / startChatPanelResize
// - Message handling: handleChatMessage (WebSocket chat_* message dispatch)
// - Utilities: getOrCreateClientId / restoreChatRoomsFromServer
//
// Dependency injection (passed in by the caller within setup; must be called after they are defined):
// - socket: ref(WebSocket|null) (main gateway connection)
// - auth: ref (user authentication info, including userInfo)
// - username: ref(string) (current username)
// - windowWidth: ref(number) (window width, used for responsive decisions)
// - activeWindow: ref(string|null) (currently focused window)
// - showChatPanel: ref(boolean) (whether the chat room panel is shown)
// - focusWindow: function (focus a window)
// - showToast: function (toast messages)
// - showConfirm: function (confirm dialog)
// - playChatNotificationSound: function (chat message notification sound)
// - getGatewayAddress: function (returns { host, port })
// - workspaceHostsChat: computed(boolean) (whether the workspace hosts chat)
// - setWorkspaceMainView: function (set the workspace main view)
// - showWorkspaceHostView: function (show a given view in the workspace)
// - clamp: function (number clamping)
// - PANEL_DRAG_ACTIVATION_DISTANCE: number (drag activation distance)
// - ACTIVE_Z_INDEX / BASE_Z_INDEX: number (z-index constants)
import { computed, ref, watch } from 'vue'

export function useChat({
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
}) {

// Chat room panel
const CHAT_PANEL_MIN_WIDTH = 400
const CHAT_PANEL_MIN_HEIGHT = 300
const CHAT_PANEL_STORAGE_KEY = 'haijunbot_chat_panel_rect'
const chatResizeDirections = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

function getDefaultChatPanelRect() {
  return {
    top: 88,
    left: Math.max(window.innerWidth - 824, 16),
    width: 800,
    height: 500,
  }
}

function loadChatPanelRect() {
  const defaultChatPanelRect = getDefaultChatPanelRect()
  const savedValue = localStorage.getItem(CHAT_PANEL_STORAGE_KEY)
  if (!savedValue) {
    return defaultChatPanelRect
  }

  try {
    const parsedValue = JSON.parse(savedValue)
    if (
      typeof parsedValue.top !== 'number' ||
      typeof parsedValue.left !== 'number' ||
      typeof parsedValue.width !== 'number' ||
      typeof parsedValue.height !== 'number'
    ) {
      return defaultChatPanelRect
    }

    return parsedValue
  } catch {
    return defaultChatPanelRect
  }
}

function saveChatPanelRect() {
  localStorage.setItem(CHAT_PANEL_STORAGE_KEY, JSON.stringify(chatPanelRect.value))
}

const chatPanelRect = ref(loadChatPanelRect())
const chatPanelCollapsed = ref(false)
const chatPanelInteraction = ref({
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

const chatPanelStyle = computed(() => {
  // Fullscreen on mobile
  if (windowWidth.value <= 768) {
    return {
      top: '0',
      left: '0',
      width: '100vw',
      height: 'var(--app-height, 100vh)',
      zIndex: activeWindow.value === 'chat' ? ACTIVE_Z_INDEX : BASE_Z_INDEX,
    }
  }
  // Collapsed state: only a narrow strip is shown
  if (chatPanelCollapsed.value) {
    return {
      top: `${chatPanelRect.value.top}px`,
      left: `${chatPanelRect.value.left}px`,
      width: '40px',
      height: `${chatPanelRect.value.height}px`,
      zIndex: activeWindow.value === 'chat' ? ACTIVE_Z_INDEX : BASE_Z_INDEX,
    }
  }
  return {
    top: `${chatPanelRect.value.top}px`,
    left: `${chatPanelRect.value.left}px`,
    width: `${chatPanelRect.value.width}px`,
    height: `${chatPanelRect.value.height}px`,
    zIndex: activeWindow.value === 'chat' ? ACTIVE_Z_INDEX : BASE_Z_INDEX,
  }
})

// Chat room data state
const CHAT_MESSAGES_STORAGE_KEY = 'haijunbot_chat_messages'

function loadChatMessages() {
  try {
    const saved = localStorage.getItem(CHAT_MESSAGES_STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      // Handle both the old format (array) and the new format (object)
      if (Array.isArray(parsed)) {
        const map = {}
        parsed.forEach(msg => {
          const key = msg.room_id || 'private'
          if (!map[key]) map[key] = []
          map[key].push(msg)
        })
        return map
      }
      return parsed
    }
    return {}
  } catch {
    return {}
  }
}

function saveChatMessages() {
  try {
    const toSave = {}
    for (const [roomId, msgs] of Object.entries(chatMessages.value)) {
      toSave[roomId] = msgs.slice(-200)
    }
    localStorage.setItem(CHAT_MESSAGES_STORAGE_KEY, JSON.stringify(toSave))
  } catch (e) {
    console.warn('[CHAT] Failed to save messages:', e)
  }
}

const chatRooms = ref([])
const chatMessages = ref(loadChatMessages())
const chatClients = ref([])
const chatRoomMembers = ref([])
const myClientId = ref('')
const activeChatRoomId = ref('')
const activePrivateClientId = ref('')
const chatUnreadCount = ref(0)
const chatName = computed(() => auth.value.userInfo?.display_name || username.value)
const myUserId = computed(() => auth.value.userInfo?.user_id || myClientId.value)
const chatSidebarWidth = ref(parseInt(localStorage.getItem('haijunbot_chat_sidebar_width') || '160'))
const chatUnreadMap = ref({})
const CHAT_JOINED_ROOMS_KEY = 'haijunbot_chat_joined_rooms'
const chatJoinedRooms = ref(JSON.parse(localStorage.getItem(CHAT_JOINED_ROOMS_KEY) || '[]'))

function saveChatJoinedRooms() {
  localStorage.setItem(CHAT_JOINED_ROOMS_KEY, JSON.stringify(chatJoinedRooms.value))
}

async function restoreChatRoomsFromServer() {
  // Fetch the user's joined rooms from the API, to restore them after login
  try {
    const resp = await fetch('/api/chat/user-rooms', { headers: { 'Authorization': `Bearer ${auth.value.token}` } })
    const data = await resp.json()
    if (data.success && data.rooms) {
      const serverRoomIds = data.rooms.map(r => r.room_id)
      // Merge server rooms with the local cache
      const merged = [...new Set([...serverRoomIds, ...chatJoinedRooms.value.filter(rid => rid)])]
      chatJoinedRooms.value = merged
      saveChatJoinedRooms()
      // Auto-rejoin all rooms
      if (merged.length > 0) {
        chatAutoRejoining = true
        chatAutoRejoinCount = merged.length
        merged.forEach(rid => {
          sendChatMessageToServer('chat_join_room', { room_id: rid, client_id: myClientId.value })
        })
      }
    }
  } catch (e) {
    // Fall back to the localStorage cache when the API fails
    const savedRooms = chatJoinedRooms.value.filter(rid => rid)
    if (savedRooms.length > 0) {
      chatAutoRejoining = true
      chatAutoRejoinCount = savedRooms.length
      savedRooms.forEach(rid => {
        sendChatMessageToServer('chat_join_room', { room_id: rid, client_id: myClientId.value })
      })
    }
  }
}

let chatAutoRejoining = false
let chatAutoRejoinCount = 0

function startChatSidebarResize(event) {
  const startX = event.clientX
  const startWidth = chatSidebarWidth.value
  const onMove = (e) => {
    const delta = e.clientX - startX
    chatSidebarWidth.value = Math.max(120, Math.min(400, startWidth + delta))
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    localStorage.setItem('haijunbot_chat_sidebar_width', String(chatSidebarWidth.value))
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function getOrCreateClientId() {
  let clientId = localStorage.getItem('haijunbot_chat_client_id')
  if (!clientId) {
    clientId = 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
    localStorage.setItem('haijunbot_chat_client_id', clientId)
  }
  return clientId
}



// Chat room panel interactions
function getChatPanelBounds() {
  const HEADER_HEIGHT = 32 // Title bar height
  const MIN_VISIBLE_WIDTH = 100 // Keep at least 100px of the panel width visible
  return {
    minTop: 0,
    minLeft: 0,
    maxLeft: window.innerWidth - MIN_VISIBLE_WIDTH,
    maxTop: window.innerHeight - HEADER_HEIGHT,
    maxWidth: window.innerWidth,
    maxHeight: window.innerHeight,
  }
}

function ensureChatPanelInViewport() {
  const HEADER_HEIGHT = 32
  const MIN_VISIBLE_WIDTH = 100
  const maxWidth = Math.max(window.innerWidth, CHAT_PANEL_MIN_WIDTH)
  const maxHeight = Math.max(window.innerHeight, CHAT_PANEL_MIN_HEIGHT)

  chatPanelRect.value.width = clamp(chatPanelRect.value.width, CHAT_PANEL_MIN_WIDTH, maxWidth)
  chatPanelRect.value.height = clamp(chatPanelRect.value.height, CHAT_PANEL_MIN_HEIGHT, maxHeight)

  chatPanelRect.value.left = clamp(
    chatPanelRect.value.left,
    0,
    window.innerWidth - MIN_VISIBLE_WIDTH
  )
  chatPanelRect.value.top = clamp(
    chatPanelRect.value.top,
    0,
    window.innerHeight - HEADER_HEIGHT
  )
}

function startChatPanelMove(event) {
  if (windowWidth.value <= 768) return
  if (event.target.closest('.chat-panel-actions')) return

  focusWindow('chat')

  chatPanelInteraction.value = {
    active: false,
    mode: 'move',
    direction: null,
    startX: event.clientX,
    startY: event.clientY,
    startTop: chatPanelRect.value.top,
    startLeft: chatPanelRect.value.left,
    startWidth: chatPanelRect.value.width,
    startHeight: chatPanelRect.value.height,
  }

  document.addEventListener('mousemove', onChatPanelPointerMove)
  document.addEventListener('mouseup', stopChatPanelInteraction)
}

function startChatPanelResize(event, direction) {
  if (windowWidth.value <= 768) return

  chatPanelInteraction.value = {
    active: true,
    mode: 'resize',
    direction,
    startX: event.clientX,
    startY: event.clientY,
    startTop: chatPanelRect.value.top,
    startLeft: chatPanelRect.value.left,
    startWidth: chatPanelRect.value.width,
    startHeight: chatPanelRect.value.height,
  }

  document.addEventListener('mousemove', onChatPanelPointerMove)
  document.addEventListener('mouseup', stopChatPanelInteraction)
  event.preventDefault()
  event.stopPropagation()
}

function onChatPanelPointerMove(event) {
  const deltaX = event.clientX - chatPanelInteraction.value.startX
  const deltaY = event.clientY - chatPanelInteraction.value.startY

  if (chatPanelInteraction.value.mode === 'move' && !chatPanelInteraction.value.active) {
    const dragDistance = Math.hypot(deltaX, deltaY)
    if (dragDistance < PANEL_DRAG_ACTIVATION_DISTANCE) {
      return
    }

    chatPanelInteraction.value = {
      ...chatPanelInteraction.value,
      active: true,
    }
    event.preventDefault()
  }

  if (!chatPanelInteraction.value.active) return

  if (chatPanelInteraction.value.mode === 'move') {
    const bounds = getChatPanelBounds()
    chatPanelRect.value.left = clamp(chatPanelInteraction.value.startLeft + deltaX, bounds.minLeft, bounds.maxLeft)
    chatPanelRect.value.top = clamp(chatPanelInteraction.value.startTop + deltaY, bounds.minTop, bounds.maxTop)
    return
  }

  const direction = chatPanelInteraction.value.direction || ''
  const startLeft = chatPanelInteraction.value.startLeft
  const startTop = chatPanelInteraction.value.startTop
  const startWidth = chatPanelInteraction.value.startWidth
  const startHeight = chatPanelInteraction.value.startHeight

  let nextLeft = startLeft
  let nextTop = startTop
  let nextWidth = startWidth
  let nextHeight = startHeight

  if (direction.includes('e')) {
    nextWidth = clamp(startWidth + deltaX, CHAT_PANEL_MIN_WIDTH, Math.max(window.innerWidth - startLeft, CHAT_PANEL_MIN_WIDTH))
  }

  if (direction.includes('s')) {
    nextHeight = clamp(startHeight + deltaY, CHAT_PANEL_MIN_HEIGHT, Math.max(window.innerHeight - startTop, CHAT_PANEL_MIN_HEIGHT))
  }

  if (direction.includes('w')) {
    const desiredLeft = clamp(startLeft + deltaX, 0, startLeft + startWidth - CHAT_PANEL_MIN_WIDTH)
    nextLeft = desiredLeft
    nextWidth = startWidth - (desiredLeft - startLeft)
  }

  if (direction.includes('n')) {
    const desiredTop = clamp(startTop + deltaY, 0, startTop + startHeight - CHAT_PANEL_MIN_HEIGHT)
    nextTop = desiredTop
    nextHeight = startHeight - (desiredTop - startTop)
  }

  if (nextLeft + nextWidth > window.innerWidth) {
    nextWidth = Math.max(CHAT_PANEL_MIN_WIDTH, window.innerWidth - nextLeft)
  }

  if (nextTop + nextHeight > window.innerHeight) {
    nextHeight = Math.max(CHAT_PANEL_MIN_HEIGHT, window.innerHeight - nextTop)
  }

  chatPanelRect.value.left = clamp(nextLeft, 0, Math.max(window.innerWidth - nextWidth, 0))
  chatPanelRect.value.top = clamp(nextTop, 0, Math.max(window.innerHeight - nextHeight, 0))
  chatPanelRect.value.width = clamp(nextWidth, CHAT_PANEL_MIN_WIDTH, Math.max(window.innerWidth - chatPanelRect.value.left, CHAT_PANEL_MIN_WIDTH))
  chatPanelRect.value.height = clamp(nextHeight, CHAT_PANEL_MIN_HEIGHT, Math.max(window.innerHeight - chatPanelRect.value.top, CHAT_PANEL_MIN_HEIGHT))
}

function stopChatPanelInteraction() {
  chatPanelInteraction.value = {
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

  document.removeEventListener('mousemove', onChatPanelPointerMove)
  document.removeEventListener('mouseup', stopChatPanelInteraction)
  saveChatPanelRect()
}

// Chat room feature methods
function toggleChatPanelCollapse() {
  chatPanelCollapsed.value = !chatPanelCollapsed.value
}

function toggleChatPanel() {
  // When the workspace is showing the chat room, the semantics are "collapse": switch back to the file view
  if (workspaceHostsChat.value) {
    setWorkspaceMainView('file')
    return
  }
  showWorkspaceHostView('chat')
  focusWindow('chat')
  chatUnreadCount.value = 0
  // On first open, register the client and fetch the chat room list
  if (!myClientId.value) {
    myClientId.value = getOrCreateClientId()
    sendChatMessageToServer('chat_register', { client_id: myClientId.value, name: username.value })
  }
  sendChatMessageToServer('chat_get_rooms', {})
  sendChatMessageToServer('chat_get_clients', {})
}

// When username changes, sync the chat room registration name
watch(username, (val) => {
  if (myClientId.value && val) {
    sendChatMessageToServer('chat_register', { client_id: myClientId.value, name: val })
    sendChatMessageToServer('chat_get_clients', {})
    if (activeChatRoomId.value) {
      sendChatMessageToServer('chat_get_room_members', { room_id: activeChatRoomId.value })
    }
  }
})

function sendChatMessageToServer(type, payload) {
  if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
    console.warn('[CHAT] No socket connection')
    return
  }
  socket.value.send(JSON.stringify({ type, payload }))
}

function createChatRoom(roomName) {
  if (!roomName || !roomName.trim()) return
  sendChatMessageToServer('chat_create_room', { name: roomName.trim(), client_id: myClientId.value })
}

function joinChatRoom(roomId) {
  activeChatRoomId.value = roomId
  // Clear the private-chat selection when switching to a group chat
  activePrivateClientId.value = ''
  // Clear the room's unread count
  const { [roomId]: _, ...rest } = chatUnreadMap.value
  chatUnreadMap.value = rest
  // Already-joined rooms are only switched for viewing; only unjoined rooms send a join request
  if (!chatJoinedRooms.value.includes(roomId)) {
    sendChatMessageToServer('chat_join_room', { room_id: roomId, client_id: myClientId.value })
  } else {
    sendChatMessageToServer('chat_get_room_members', { room_id: roomId })
  }
}

function leaveChatRoom(roomId) {
  sendChatMessageToServer('chat_leave_room', { room_id: roomId, client_id: myClientId.value })
}

function deleteChatRoom(roomId) {
  showConfirm('Delete this chat room? This cannot be undone.', () => {
    sendChatMessageToServer('chat_delete_room', { room_id: roomId, client_id: myClientId.value })
  })
}

function renameChatRoom(roomId, newName) {
  sendChatMessageToServer('chat_rename_room', { room_id: roomId, client_id: myClientId.value, new_name: newName })
}

function clearChatMessages(scope) {
  if (scope === 'all') {
    showConfirm('Clear all chat history? This cannot be undone.', () => {
      chatMessages.value = {}
      saveChatMessages()
    })
  } else if (scope === 'current') {
    const key = activePrivateClientId.value
      ? `private_${activePrivateClientId.value}`
      : activeChatRoomId.value
    if (key) {
      showConfirm('Clear the current chat history? This cannot be undone.', () => {
        const { [key]: _, ...rest } = chatMessages.value
        chatMessages.value = rest
        saveChatMessages()
      })
    }
  }
}

// Convert a relative-path image URL into a full URL (uploads are served from the backend gateway)
function resolveImageUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/uploads/')) {
    const { host, port } = getGatewayAddress()
    const protocol = window.location.protocol === 'https:' ? 'https' : 'http'
    return `${protocol}://${host}:${port}${url}`
  }
  return url
}

function sendChatMessage(content, imageUrl) {
  if ((!content || !content.trim()) && !imageUrl) return
  const trimmed = (content || '').trim()
  if (activePrivateClientId.value) {
    // Private chat mode
    const payload = {
      sender_id: myClientId.value,
      receiver_id: activePrivateClientId.value,
      content: trimmed,
    }
    if (imageUrl) payload.image_url = resolveImageUrl(imageUrl)
    sendChatMessageToServer('chat_send_private', payload)
    // Append our own message locally
    const selfMsgKey = `private_${activePrivateClientId.value}`
    if (!chatMessages.value[selfMsgKey]) chatMessages.value[selfMsgKey] = []
    const selfMsg = {
      client_id: myClientId.value,
      client_name: chatName.value || myClientId.value,
      sender_name: username.value || myClientId.value,
      sender_display_name: chatName.value || username.value,
      content: trimmed,
      private: true,
      timestamp: Date.now(),
    }
    if (imageUrl) selfMsg.image_url = resolveImageUrl(imageUrl)
    chatMessages.value[selfMsgKey].push(selfMsg)
    saveChatMessages()
  } else if (activeChatRoomId.value) {
    // Chat room mode
    const payload = {
      room_id: activeChatRoomId.value,
      client_id: myClientId.value,
      content: trimmed,
    }
    if (imageUrl) payload.image_url = resolveImageUrl(imageUrl)
    sendChatMessageToServer('chat_send_message', payload)
    // Append our own message locally
    if (!chatMessages.value[activeChatRoomId.value]) chatMessages.value[activeChatRoomId.value] = []
    const selfMsg = {
      client_id: myClientId.value,
      client_name: chatName.value || myClientId.value,
      sender_name: username.value || myClientId.value,
      sender_display_name: chatName.value || username.value,
      content: trimmed,
      room_id: activeChatRoomId.value,
      timestamp: Date.now(),
    }
    if (imageUrl) selfMsg.image_url = resolveImageUrl(imageUrl)
    chatMessages.value[activeChatRoomId.value].push(selfMsg)
    saveChatMessages()
  } else {
    showToast('Join a chat room or pick a private chat target first', 'warning')
  }
}

function selectPrivateClient(clientId) {
  if (activePrivateClientId.value === clientId) {
    activePrivateClientId.value = ''
  } else {
    activePrivateClientId.value = clientId
    // Do not clear activeChatRoomId, keeping the group-chat joined state
    // Clear the private-chat unread count
    const privKey = `private_${clientId}`
    const { [privKey]: _, ...rest } = chatUnreadMap.value
    chatUnreadMap.value = rest
    // Fetch the private-chat history
    sendChatMessageToServer('chat_get_private_history', {
      client_id: myUserId.value,
      other_id: clientId,
    })
  }
}
function handleChatMessage(type, payload) {
  switch (type) {
    case 'chat_register_response':
      if (payload?.success) {
        myClientId.value = payload.client_id || myClientId.value
        // Add ourselves to the online-user list (using display_name, deduped by user_id)
        if (payload.client_id) {
          const uid = payload.user_id || payload.client_id
          const existing = chatClients.value.find(c => (c.user_id || c.client_id) === uid)
          if (existing) {
            existing.client_id = payload.client_id
            existing.name = payload.name
            existing.display_name = payload.display_name || payload.name
          } else {
            chatClients.value = [...chatClients.value, { client_id: payload.client_id, user_id: uid, name: payload.name, display_name: payload.display_name || payload.name }]
          }
        }
        // Restore the user's joined rooms from the API (takes priority over the localStorage cache)
        restoreChatRoomsFromServer()
      } else {
        // Registration failed, clear the cache
        chatJoinedRooms.value = []
        saveChatJoinedRooms()
      }
      break
    case 'chat_get_rooms_response':
      chatRooms.value = payload?.rooms || []
      break
    case 'chat_create_room_response':
      if (payload?.success && payload.room_id) {
        chatRooms.value.push({
          room_id: payload.room_id,
          name: payload.name || 'Untitled chat room',
          member_count: 1,
          created_by: auth.value.userInfo?.user_id || '',
        })
        if (!chatJoinedRooms.value.includes(payload.room_id)) { chatJoinedRooms.value = [...chatJoinedRooms.value, payload.room_id]; saveChatJoinedRooms() }
        showToast('Chat room created', 'success')
      } else {
        showToast(payload?.error || 'Failed to create the chat room', 'error')
      }
      break
    case 'chat_join_room_response':
      if (payload?.success) {
        if (!chatAutoRejoining) showToast('Joined the chat room', 'success')
        const joinedRoomId = payload?.room_id || activeChatRoomId.value
        if (joinedRoomId && !chatJoinedRooms.value.includes(joinedRoomId)) { chatJoinedRooms.value = [...chatJoinedRooms.value, joinedRoomId]; saveChatJoinedRooms() }
        // Fetch the chat room's member list
        if (joinedRoomId) sendChatMessageToServer('chat_get_room_members', { room_id: joinedRoomId })
      } else {
        if (!chatAutoRejoining) showToast(payload?.error || 'Failed to join the chat room', 'error')
        // Join failed (the room may have been deleted); remove it from the cache
        const failedRoomId = payload?.room_id || activeChatRoomId.value
        if (failedRoomId && chatJoinedRooms.value.includes(failedRoomId)) {
          chatJoinedRooms.value = chatJoinedRooms.value.filter(r => r !== failedRoomId)
          saveChatJoinedRooms()
        }
      }
      // Decrement the auto-rejoin completion counter
      if (chatAutoRejoining) {
        chatAutoRejoinCount--
        if (chatAutoRejoinCount <= 0) chatAutoRejoining = false
      }
      break
    case 'chat_get_clients_response':
      chatClients.value = payload?.clients || []
      break
    case 'chat_client_joined':
      if (payload?.client_id && payload?.client_id !== myClientId.value) {
        const uid = payload.user_id || payload.client_id
        const existing = chatClients.value.find(c => (c.user_id || c.client_id) === uid)
        if (existing) {
          existing.client_id = payload.client_id
          existing.name = payload.name
          existing.display_name = payload.display_name || payload.name
        } else {
          chatClients.value = [...chatClients.value, { client_id: payload.client_id, user_id: uid, name: payload.name, display_name: payload.display_name || payload.name }]
        }
      }
      break
    case 'chat_client_left':
      if (payload?.client_id && !payload?.still_online) {
        const uid = payload.user_id || payload.client_id
        chatClients.value = chatClients.value.filter(c => (c.user_id || c.client_id) !== uid)
      }
      break
    case 'chat_get_room_members_response':
      chatRoomMembers.value = payload?.members || []
      break
    case 'chat_message':
      // Chat room broadcast message (skip messages we sent ourselves; already appended locally)
      if (payload?.client_id === myClientId.value) break
      const roomId = payload?.room_id || 'general'
      if (!chatMessages.value[roomId]) chatMessages.value[roomId] = []
      const roomMsg = {
        client_id: payload?.client_id,
        client_name: payload?.sender_display_name || payload?.sender_name || payload?.client_id,
        sender_name: payload?.sender_name || payload?.client_id,
        sender_display_name: payload?.sender_display_name || payload?.sender_name,
        content: payload?.content,
        room_id: roomId,
        timestamp: payload?.timestamp || Date.now(),
      }
      if (payload?.image_url) roomMsg.image_url = resolveImageUrl(payload.image_url)
      chatMessages.value[roomId].push(roomMsg)
      saveChatMessages()
      // New message notification: notify for messages not sent by ourselves
      if (payload?.client_id !== myClientId.value) {
        playChatNotificationSound()
        if (!showChatPanel.value || activeWindow.value !== 'chat') {
          chatUnreadCount.value++
        }
        // Track unread counts per room
        const roomKey = payload?.room_id || 'general'
        if (activeChatRoomId.value !== roomKey || activePrivateClientId.value) {
          chatUnreadMap.value = { ...chatUnreadMap.value, [roomKey]: (chatUnreadMap.value[roomKey] || 0) + 1 }
        }
      }
      break
    case 'chat_private_message':
      // Private message (skip messages we sent ourselves; already appended locally)
      if (payload?.message?.sender_id === myClientId.value) break
      const privPeerId = payload?.message?.sender_user_id || payload?.sender_user_id || payload?.message?.sender_id
      const privMsgKey = `private_${privPeerId}`
      if (!chatMessages.value[privMsgKey]) chatMessages.value[privMsgKey] = []
      const privMsg = {
        client_id: payload?.message?.sender_id,
        client_name: payload?.message?.sender_display_name || payload?.message?.sender_name || payload?.message?.sender_id,
        sender_name: payload?.message?.sender_name || payload?.message?.sender_id,
        sender_display_name: payload?.message?.sender_display_name || payload?.message?.sender_name,
        content: payload?.message?.content,
        private: true,
        timestamp: payload?.message?.timestamp || Date.now(),
      }
      if (payload?.message?.image_url) privMsg.image_url = resolveImageUrl(payload.message.image_url)
      chatMessages.value[privMsgKey].push(privMsg)
      saveChatMessages()
      // New message notification: notify for messages not sent by ourselves
      if (payload?.message?.sender_id !== myClientId.value) {
        playChatNotificationSound()
        if (!showChatPanel.value || activeWindow.value !== 'chat') {
          chatUnreadCount.value++
        }
        // Track unread counts per private chat
        const privUnreadKey = `private_${privPeerId}`
        if (activePrivateClientId.value !== privPeerId) {
          chatUnreadMap.value = { ...chatUnreadMap.value, [privUnreadKey]: (chatUnreadMap.value[privUnreadKey] || 0) + 1 }
        }
      }
      break
    case 'chat_get_private_history_response':
      if (payload?.messages) {
        const histKey = `private_${payload?.other_id || activePrivateClientId.value}`
        chatMessages.value[histKey] = payload.messages.map(msg => {
          const m = {
            client_id: msg.sender_id,
            client_name: msg.sender_name || msg.sender_id,
            sender_name: msg.sender_name || msg.sender_id,
            content: msg.content,
            private: true,
            timestamp: msg.timestamp || Date.now(),
          }
          if (msg.image_url) m.image_url = resolveImageUrl(msg.image_url)
          return m
        })
        saveChatMessages()
      }
      break
    case 'chat_leave_room_response':
      if (payload?.success) {
        showToast('Left the chat room', 'success')
        const leftRoomId = payload?.room_id || activeChatRoomId.value
        chatJoinedRooms.value = chatJoinedRooms.value.filter(r => r !== leftRoomId)
        saveChatJoinedRooms()
        delete chatMessages.value[leftRoomId]
        if (activeChatRoomId.value === leftRoomId) {
          activeChatRoomId.value = ''
        }
        saveChatMessages()
      } else {
        showToast(payload?.error || 'Failed to leave the chat room', 'error')
      }
      break
    case 'chat_delete_room_response':
      if (payload?.success) {
        showToast('Chat room deleted', 'success')
        const deletedRoomId = payload?.room_id || activeChatRoomId.value
        chatJoinedRooms.value = chatJoinedRooms.value.filter(r => r !== deletedRoomId)
        saveChatJoinedRooms()
        delete chatMessages.value[deletedRoomId]
        chatRooms.value = chatRooms.value.filter(r => r.room_id !== deletedRoomId)
        if (activeChatRoomId.value === deletedRoomId) {
          activeChatRoomId.value = ''
        }
        saveChatMessages()
      } else {
        showToast(payload?.error || 'Failed to delete the chat room', 'error')
      }
      break
    case 'chat_room_created':
      // Notification of a new room created by another user
      if (payload?.room_id) {
        chatRooms.value = [...chatRooms.value, {
          room_id: payload.room_id,
          name: payload.name || 'Untitled chat room',
          member_count: payload.member_count || 1,
          created_by: payload.created_by || '',
        }]
      }
      break
    case 'chat_rename_room_response':
      if (payload?.success) {
        showToast('Chat room renamed', 'success')
      } else {
        showToast(payload?.error || 'Failed to rename the chat room', 'error')
      }
      break
    case 'chat_room_renamed':
      // Broadcast notification: update the local room name
      if (payload?.room_id && payload?.new_name) {
        chatRooms.value = chatRooms.value.map(r =>
          r.room_id === payload.room_id ? { ...r, name: payload.new_name } : r
        )
      }
      break
    case 'chat_room_deleted':
      const removedRoomId = payload?.room_id
      if (removedRoomId) {
        chatJoinedRooms.value = chatJoinedRooms.value.filter(r => r !== removedRoomId)
        saveChatJoinedRooms()
        delete chatMessages.value[removedRoomId]
        chatRooms.value = chatRooms.value.filter(r => r.room_id !== removedRoomId)
        if (activeChatRoomId.value === removedRoomId) {
          activeChatRoomId.value = ''
        }
        saveChatMessages()
        showToast('This chat room was deleted by its creator', 'warning')
      }
      break
    case 'chat_error':
      showToast(payload?.error || 'Chat room operation failed', 'error')
      break
  }
}

  return {
    // Panel layout
    chatPanelRect,
    chatPanelCollapsed,
    chatPanelInteraction,
    chatPanelStyle,
    // Chat room data
    chatRooms,
    chatMessages,
    chatClients,
    chatRoomMembers,
    myClientId,
    activeChatRoomId,
    activePrivateClientId,
    chatUnreadCount,
    chatName,
    myUserId,
    chatSidebarWidth,
    chatUnreadMap,
    chatJoinedRooms,
    // Panel interactions
    startChatSidebarResize,
    startChatPanelMove,
    startChatPanelResize,
    // Chat features
    toggleChatPanel,
    toggleChatPanelCollapse,
    sendChatMessageToServer,
    createChatRoom,
    joinChatRoom,
    leaveChatRoom,
    deleteChatRoom,
    renameChatRoom,
    clearChatMessages,
    sendChatMessage,
    selectPrivateClient,
    // Message handling
    handleChatMessage,
    // Utilities
    getOrCreateClientId,
    restoreChatRoomsFromServer,
  }
}
