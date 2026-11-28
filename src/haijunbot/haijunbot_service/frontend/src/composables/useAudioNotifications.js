// Audio notification / auto reading / system notification composable.
//
// Extracted from App.vue's <script setup> (former lines 20747-20895) while preserving identical behavior:
// - beeps: playNotificationSound / playChatNotificationSound (Web Audio API, self-contained)
// - auto reading: uses the browser built-in SpeechSynthesis, reusing SessionPanel's speakMessage/speakText
// - system notifications: Notification API (popup only, no beep)
//
// Dependency injection:
// - sessionPanelRefs: plain Map (panelId -> SessionPanel component instance)
// - allOutputs: ref(Map) (agent_id -> outputs array)
// - panelInputTips: ref(Map) (agentId -> input hint string)
// - panels: ref(array) ([{ id, agentId }])
// - isAutoReadEnabled: function (agentId -> boolean)
export function useAudioNotifications({
  sessionPanelRefs,
  allOutputs,
  panelInputTips,
  panels,
  isAutoReadEnabled,
}) {
  // Play a single beep
  function playSingleBeep(audioContext, startTime) {
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    oscillator.frequency.value = 800
    oscillator.type = 'sine'
    gainNode.gain.setValueAtTime(0.3, startTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + 0.2)
    oscillator.start(startTime)
    oscillator.stop(startTime + 0.2)
  }

  // Play the chat-room new message sound (two tones, distinct from the regular beep)
  function playChatNotificationSound() {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)()
      const now = audioContext.currentTime
      // Play two notes at different frequencies to create a pleasant two-tone chime
      playChatSingleTone(audioContext, now, 880, 'triangle', 0.25)
      playChatSingleTone(audioContext, now + 0.18, 1320, 'triangle', 0.3)
    } catch {
      // Silently ignore when the browser has no Web Audio support
    }
  }

  // Play a single chat tone
  function playChatSingleTone(audioContext, startTime, frequency, type, duration) {
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    oscillator.frequency.value = frequency
    oscillator.type = type
    gainNode.gain.setValueAtTime(0.25, startTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + duration)
    oscillator.start(startTime)
    oscillator.stop(startTime + duration)
  }

  // Play the notification sound (three beeps), returning a Promise that resolves after the last tone ends
  function playNotificationSound() {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)()
      const now = audioContext.currentTime
      // Play three beeps in a row, 0.25s apart
      playSingleBeep(audioContext, now)
      playSingleBeep(audioContext, now + 0.25)
      playSingleBeep(audioContext, now + 0.5)
      // The last tone starts at now + 0.5 and lasts 0.2s; leave a little margin
      return new Promise(resolve => setTimeout(resolve, 750))
    } catch {
      // Silently ignore when the browser has no Web Audio support and return an already-resolved Promise
      return Promise.resolve()
    }
  }

  // Play the notification sound when an input request arrives (not gated by the auto-read toggle; always plays)
  function notifyInputRequest() {
    playNotificationSound()
  }

  // ---- Auto reading (browser built-in SpeechSynthesis) ----
  const autoReadSupported = typeof window !== 'undefined' && 'speechSynthesis' in window

  // Stop auto reading (reuses SessionPanel's stop logic to keep icon states in sync)
  function stopAutoRead() {
    if (!autoReadSupported) return
    for (const sp of sessionPanelRefs.values()) {
      sp?.stopSpeak?.()
    }
  }

  // Extract plain text from rendered HTML so Markdown markers are not read aloud
  function extractAutoReadText(item) {
    if (!item) return ''
    if (item.html) {
      const tmp = document.createElement('div')
      tmp.innerHTML = item.html
      return (tmp.textContent || '').replace(/\s+/g, ' ').trim()
    }
    return String(item.text || '').trim()
  }

  // Get the auto-read target: multiline input uses the last message with text; single-line/confirm uses the input hint
  function getAutoReadTarget(agentId, executionStatus) {
    if (executionStatus === 'waiting_multi') {
      const messages = allOutputs.value.get(agentId) || []
      for (let i = messages.length - 1; i >= 0; i--) {
        if (extractAutoReadText(messages[i])) return { message: messages[i] }
      }
    }
    const tip = panelInputTips.value.get(agentId) || ''
    return { text: tip || 'Waiting for input' }
  }

  // When entering the waiting-for-input state, trigger the read-aloud logic for the matching message (the beep is played separately by notifyInputRequest)
  async function handleAutoRead(agentId, executionStatus) {
    if (!isAutoReadEnabled(agentId)) return
    const target = getAutoReadTarget(agentId, executionStatus)
    const panel = panels.value.find(p => p.agentId === agentId)
    const sp = panel ? sessionPanelRefs.get(panel.id) : null
    if (target.message && sp?.speakMessage) {
      // Reuse the message list read-aloud logic; icon states sync automatically
      sp.speakMessage(target.message)
    } else if (sp?.speakText) {
      sp.speakText(target.text)
    }
  }

  // Notification permission state
  let notificationPermissionRequested = false

  // Send a system notification (popup only, no beep)
  function sendSystemNotification(message) {
    // Check whether the browser supports the Notification API
    if (!('Notification' in window)) {
      return
    }
    // If permission is already granted, send the notification directly
    if (Notification.permission === 'granted') {
      new Notification('HaijunBot', {
        body: message,
        icon: '/icons/haijunbot-pet.svg'
      })
    }
    // If not denied and permission has not been requested yet, request it
    else if (Notification.permission !== 'denied' && !notificationPermissionRequested) {
      notificationPermissionRequested = true
      Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
          new Notification('HaijunBot', {
            body: message,
            icon: '/icons/haijunbot-pet.svg'
          })
        }
      })
    }
  }

  return {
    autoReadSupported,
    notifyInputRequest,
    playChatNotificationSound,
    stopAutoRead,
    handleAutoRead,
    sendSystemNotification,
  }
}
