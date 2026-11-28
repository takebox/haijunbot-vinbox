<template>
  <div class="session-panel" :class="{ 'active': active, 'session-panel-embedded': embedded, 'session-panel-dragging': interaction?.active }" :style="panelStyle" @click="handlePanelClick" @contextmenu="handlePanelContextMenu">
    <!-- Blank placeholder -->
    <div v-if="!agent" class="session-panel-empty">
      <div class="empty-icon">▦</div>
      <div class="empty-text">Click an Agent on the left to open here</div>
      <button class="empty-close-btn" tabindex="-1" @mousedown.prevent @click.stop="$emit('close-panel')" title="Close panel">✕</button>
    </div>

    <!-- Session with an Agent -->
    <template v-else>
      <!-- Session header -->
      <div class="session-panel-header" @mousedown="!embedded && $emit('startMove', $event)">
        <span class="session-agent-name">{{ agent.name || agent.agent_id }}</span>
        <span class="session-agent-status" :class="getStatusClass(agent)">{{ getStatusLabel(agent) }}</span>
        <!-- Action icons moved to the "Current Agent" group in the Ctrl+P command palette -->
        <div class="session-header-actions">
          <button class="session-close-panel-btn" tabindex="-1" @mousedown.prevent @click.stop="$emit('close-panel')" title="Close panel">✕</button>
        </div>
      </div>

      <!-- Message list -->
      <div class="messages" :ref="el => setOutputListRef(el)">
        <article v-for="(item, index) in messages" :key="item._stableId || index" class="message" :class="`message-${item.output_type?.toLowerCase()}`">
          <div class="message-content">
            <button class="icon-btn copy-message-btn" @click="copyToClipboard(item.text, index)" title="Copy to clipboard" v-if="item.text">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </button>
            <button class="icon-btn export-message-btn" @click="exportMessageAsImage(item, index, $event)" title="Export as image" v-if="item.text">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <path d="M21 15l-5-5L5 21"></path>
              </svg>
            </button>
            <div class="message-body markdown-content" v-html="item.html" @click="onMessageBodyClick"></div>
            <!-- Streaming typewriter cursor (pet thumbnail) -->
            <span v-if="item.isStreaming && item.output_type === 'STREAM'" class="stream-caret" aria-hidden="true">
              <span class="stream-caret-pet">
                <span class="stream-caret-ear l"></span>
                <span class="stream-caret-ear r"></span>
                <span class="stream-caret-eye l"></span>
                <span class="stream-caret-eye r"></span>
              </span>
            </span>
            <div class="message-meta" v-if="item.agent_name || item.timestamp || item.non_interactive || item.agent_list">
              <span class="message-agent" v-if="item.agent_name">{{ item.agent_name }}</span>
              <span class="message-separator" v-if="item.agent_name && item.agent_list"> · </span>
              <span class="message-agent-list" v-if="item.agent_list" title="Agent chain within the current process">{{ item.agent_list }}</span>
              <span class="message-separator" v-if="(item.agent_name || item.agent_list) && item.timestamp"> · </span>
              <span class="message-time" v-if="item.timestamp">{{ formatMessageTime(item.timestamp) }}</span>
              <span class="message-separator" v-if="(item.agent_name || item.agent_list || item.timestamp) && (item.non_interactive !== undefined)"> · </span>
              <span class="message-silent" v-if="item.non_interactive === true" title="Silent mode" v-html="SESSION_ICONS.muted"></span>
              <span class="message-silent" v-if="item.non_interactive === false" title="Interactive mode" v-html="SESSION_ICONS.speaker"></span>
              <button
                v-if="ttsSupported && item.text"
                class="message-speak-btn"
                :class="{ 'speaking': isSpeaking(item) }"
                @click.stop="toggleSpeak(item)"
                :title="isSpeaking(item) ? 'Stop reading' : 'Read this message'"
              ><span v-html="isSpeaking(item) ? '⏹' : SESSION_ICONS.speaker"></span></button>
            </div>
          </div>
          <!-- Terminal embed: when suppressTerminal is true (this panel is already hosted by the editor main area), do not render,
               to avoid two xterm hosts for the same execution competing and repeatedly destroying/recreating each other -->
          <div v-if="!suppressTerminal && item.output_type === 'execution' && item.execution_id && !item.is_finished && !item.terminal_content" class="terminal-wrapper">
            <div :ref="el => setTerminalRef(item.execution_id, el, item.agent_id)" class="terminal-host"></div>
          </div>
          <!-- Terminal content (history): only render when there is no xterm instance (finished, or running but terminal_content already flushed to disk),
               avoiding simultaneous display with the xterm branch above; when terminal_content is missing, fall back to concatenating execution_chunks,
               avoiding the whole block failing to render due to incomplete data flushed after refresh -->
          <div v-if="item.output_type === 'execution' && showTerminalHistory(item)" class="terminal-history" :style="getTerminalStyle(getTerminalHistoryText(item))">
            <div class="terminal-history-header">Terminal Output ({{ item.execution_id }})</div>
            <pre class="terminal-history-content">{{ getTerminalHistoryText(item) }}</pre>
          </div>
        </article>
      </div>

      <!-- Resize handle -->
      <div
        v-for="direction in resizeDirections"
        :key="direction"
        :class="['session-resize-handle', `session-resize-${direction}`]"
        @mousedown="$emit('startResize', $event, direction)"
      ></div>

      <!-- Inline confirmation area -->
      <div v-if="confirmData" class="panel-confirm-bar">
        <div class="panel-confirm-message">{{ confirmData.message }}</div>
        <div class="panel-confirm-actions">
          <button class="panel-confirm-btn panel-confirm-no" :class="{ 'default': confirmData.defaultConfirm === false }" :style="{ order: confirmData.defaultConfirm === false ? 2 : 1 }" @click="$emit('cancel-confirm')">Cancel</button>
          <button class="panel-confirm-btn panel-confirm-yes" :class="{ 'default': confirmData.defaultConfirm !== false }" :style="{ order: confirmData.defaultConfirm !== false ? 2 : 1 }" @click="$emit('confirm')">Confirm</button>
        </div>
      </div>

      <!-- Input area -->
      <div class="input-area" :class="{ 'collapsed': inputCollapsed }">
        <div class="input-toggle-bar" @click="inputCollapsed = !inputCollapsed" :title="inputCollapsed ? 'Expand input box' : 'Collapse input box'">
          <!-- Agent running progress indicator (does not collapse with the input box) -->
          <div class="agent-thinking-indicator" v-if="agent?.status === 'running' && (agentStatus?.execution_status ?? 'running') === 'running'">
            <div class="thinking-spinner"></div>
            <span class="thinking-text">Agent is running...</span>
          </div>
          <button class="input-toggle-btn">
            {{ inputCollapsed ? '▲' : '▼' }}
          </button>
        </div>
        <div class="input-wrapper" v-show="!inputCollapsed">
          <!-- Multi-line input box -->
          <textarea
            v-if="inputMode === 'multi'"
            ref="multiInputRef"
            :value="inputText"
            :data-agent-id="agent?.agent_id || ''"
            :placeholder="isInputDisabled ? 'Agent is not running' : (inputTip || 'Enter content (Ctrl+Enter / Ctrl+D to send, Right Ctrl for voice input)')"
            :disabled="isInputDisabled"
            @input="$emit('input-change', $event)"
            @keydown="handleInputKeydown($event)"
            @keyup="handleInputKeyup($event)"
            @paste="$emit('paste', $event)"
          ></textarea>

          <!-- Single-line input box -->
          <input
            v-else
            ref="singleInputRef"
            :value="inputText"
            :data-agent-id="agent?.agent_id || ''"
            :type="isPassword ? 'password' : 'text'"
            :placeholder="isInputDisabled ? 'Agent is not running' : (inputTip || 'Enter content (Enter to send)')"
            :disabled="isInputDisabled"
            @input="$emit('input-change', $event)"
            @keydown="handleInputKeydown($event)"
            @keyup="handleInputKeyup($event)"
            @paste="$emit('paste', $event)"
          />
          <!-- Buffer indicator -->
          <div class="buffer-indicator" v-if="hasBufferedInput && (agentStatus?.execution_status ?? 'running') !== 'waiting_multi'" @click="$emit('show-buffer', agent?.agent_id)">
            <span class="buffer-icon" v-html="SESSION_ICONS.buffer"></span>
            <span class="buffer-text">Buffer has content</span>
          </div>

          <!-- Action buttons -->
          <div class="input-actions">
            <button
              v-if="hasBufferedInput && (agentStatus?.execution_status ?? 'running') !== 'waiting_multi'"
              class="action-btn clear-buffer-btn"
              @click="$emit('clear-buffer')"
              :disabled="isInputDisabled"
              title="Clear buffer"
            >
              Clear
            </button>
            <button
              class="complete-btn"
              @click="$emit('complete')"
              :disabled="isWaitingMultiDisabled"
              title="Done (send empty message)"
            >
              Done
            </button>
            <button
              class="action-btn completion-btn"
              @click="$emit('open-completions')"
              :disabled="isWaitingMultiDisabled"
              title="Insert completion (@)"
            >
              @
            </button>
            <button
              v-if="asrSupported && !isMobileDevice"
              class="action-btn asr-btn"
              :class="{ 'recording': isRecording }"
              @click="toggleRecord"
              @contextmenu.prevent
              :disabled="isInputDisabled"
              :title="isRecording ? 'Stop voice input' : 'Voice input'"
            >
              <span v-html="isRecording ? '⏹' : SESSION_ICONS.mic"></span>
            </button>
            <button
              class="send-btn"
              @click="$emit('send')"
              :disabled="isInputDisabled || (!inputText.trim() && (!hasBufferedInput || (agentStatus?.execution_status ?? 'running') === 'waiting_multi'))"
            >
              {{ hasBufferedInput && (agentStatus?.execution_status ?? 'running') !== 'waiting_multi' ? 'Send buffer' : 'Send' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { exportElementAsImage } from '../utils/exportImage.js'
// Self-drawn 16x16 stroke linear SVG icons (currentColor inherits theme color), consistent with the global style
const SESSION_ICONS = {
  muted: '<svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 6.5v3h2.5L9 13V3L5 6.5z"/><path d="M11 6.5 13.5 9M13.5 6.5 11 9"/></svg>',
  speaker: '<svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 6.5v3h2.5L9 13V3L5 6.5z"/><path d="M11 6.5a3 3 0 0 1 0 3"/></svg>',
  buffer: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 1.5h8v13l-1.5-1-1.5 1-1.5-1-1.5 1-1.5-1z"/><path d="M6 5.5h4M6 8h4"/></svg>',
  mic: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5.5" y="2" width="5" height="8" rx="2.5"/><path d="M3.5 8a4.5 4.5 0 0 0 9 0M8 12.5V14"/></svg>',
}

const props = defineProps({

  agent: { type: Object, default: null },
  messages: { type: Array, default: () => [] },
  inputText: { type: String, default: '' },
  inputMode: { type: String, default: 'multi' },
  inputTip: { type: String, default: '' },
  isPassword: { type: Boolean, default: false },
  isInputDisabled: { type: Boolean, default: true },
  isWaitingMultiDisabled: { type: Boolean, default: true },
  hasBufferedInput: { type: Boolean, default: false },
  agentStatus: { type: Object, default: null },
  active: { type: Boolean, default: false },
  confirmData: { type: Object, default: null },
  embedded: { type: Boolean, default: false },
  interaction: { type: Object, default: null },
  resizeDirections: { type: Array, default: () => [] },
  panelStyle: { type: Object, default: null },
  // Set to true when this panel is already hosted by the editor main area: do not render the inline xterm host,
  // avoiding competing for the host element with the same execution terminal in the editor
  suppressTerminal: { type: Boolean, default: false },
})

const emit = defineEmits([
  'activate', 'close-agent', 'close-panel',
  'send', 'complete', 'open-completions',
  'input-change', 'keydown', 'paste',
  'show-buffer', 'clear-buffer',
  'set-output-list', 'set-terminal-ref',
  'show-toast',
  'confirm', 'cancel-confirm',
  'startMove', 'startResize',
  'context-menu',
  'open-diff-file',
])

// Message content click delegation: after clicking a diff file path embedded in the conversation (data-diff-file-path),
// bubble up to App which opens the file in the editor panel. Only handle elements with this marker.
function onMessageBodyClick(event) {
  const target = event?.target?.closest?.('[data-diff-file-path]')
  if (!target) return
  const filePath = target.getAttribute('data-diff-file-path')
  if (!filePath) return
  event.preventDefault()
  event.stopPropagation()
  emit('open-diff-file', filePath)
}

function handlePanelClick() {
  // Do not trigger activate in floating mode (not in the grid, activation is meaningless)
  if (!props.embedded) {
    return
  }
  // Do not repeatedly trigger activate on the currently active Panel
  if (props.active) {
    return
  }
  // Do not trigger activate if the user is selecting text
  const selection = window.getSelection()
  if (selection && selection.toString().trim()) {
    return
  }
  emit('activate')
}

// Right-click inside the panel: keep the browser default menu when text is selected (for copying), otherwise let the parent component show the Agent action menu
function handlePanelContextMenu(event) {
  // Empty panels with no Agent do not provide an action menu
  if (!props.agent) return
  const selection = window.getSelection()
  if (selection && selection.toString().trim()) {
    return
  }
  event.preventDefault()
  emit('context-menu', event)
}

const outputListRef = ref(null)
const inputCollapsed = ref(false)
const multiInputRef = ref(null)
const singleInputRef = ref(null)

// Determine whether the current focus can be taken over by this panel's input box:
// allowed only when there is no focus (body), focus is already in this panel's input box, or focus is on another non-input control on the page,
// avoiding stealing focus from the input box the user is using (e.g. the command palette search box) during status polling.
function canStealFocus() {
  // When a modal is open, the user is operating inside it; do not steal focus
  if (hasVisibleModalOverlay()) return false
  // Do not steal focus when the user is selecting text:
  // selecting text does not change document.activeElement (usually still body),
  // and focusing the input box now would clear the selection, leaving the user no time to copy.
  if (hasActiveTextSelection()) return false
  const active = document.activeElement
  if (!active || active === document.body) return true
  const currentEl = props.inputMode === 'multi' ? multiInputRef.value : singleInputRef.value
  if (currentEl && active === currentEl) return true
  const tagName = String(active.tagName || '').toLowerCase()
  // Do not steal focus when the user is operating in another input control (input/textarea/contenteditable)
  if (tagName === 'input' || tagName === 'textarea' || active.isContentEditable) return false
  // When focus is inside another panel area (session panel/terminal/editor/chat room), the user has actively placed focus there,
  // and status polling should not steal focus back to the input box (otherwise arrow-key navigation would be interrupted immediately)
  const otherPanel = active.closest && active.closest('.session-panel, .terminal-panel, .workspace-panel, .chat-panel')
  const selfPanel = currentEl && currentEl.closest ? currentEl.closest('.session-panel') : null
  if (otherPanel && otherPanel !== selfPanel) return false
  return true
}

// Detect whether there is a visible modal overlay on the page (Element Plus popups/dialogs, etc.).
// When a popup is open, the user is operating inside it and should not have focus stolen by auto-focus.
function hasVisibleModalOverlay() {
  const overlays = document.querySelectorAll('.el-overlay, .modal-overlay, .dialog-overlay, .diff-modal-overlay')
  for (const el of overlays) {
    const style = window.getComputedStyle(el)
    if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
      return true
    }
  }
  return false
}

// Detect whether there is a non-empty text selection on the page.
// When the user selects text, document.activeElement is usually still body, which activeElement alone cannot detect;
// Focusing the input box now would clear the selection, leaving the user no time to copy.
function hasActiveTextSelection() {
  const selection = window.getSelection && window.getSelection()
  if (!selection || selection.isCollapsed) return false
  return Boolean(selection.toString().trim())
}

// Focus the input box
// When force=true, used to explicitly switch focus (e.g. switching Panel), skipping the "user is in another input box" protection
function focusInput(force = false) {
  // Respect the collapsed state when the user has collapsed the input box: do not auto-expand or steal focus.
  // Collapsing is the user's explicit intent, and status polling (fetchAgentStatus calls this function periodically) should not expand it.
  if (inputCollapsed.value) return
  if (!force && !canStealFocus()) return
  // Wait for the DOM update before focusing
  setTimeout(() => {
    if (!force && !canStealFocus()) return
    const el = props.inputMode === 'multi' ? multiInputRef.value : singleInputRef.value
    if (el) {
      el.focus()
    }
  }, 50)
}

defineExpose({ focusInput, speakMessage, speakText, stopSpeak })

function setOutputListRef(el) {
  outputListRef.value = el
  emit('set-output-list', el)
}

function setTerminalRef(executionId, el, agentId) {
  emit('set-terminal-ref', executionId, el, agentId)
}

async function copyToClipboard(text, index) {
  if (!text) {
    console.warn('[COPY] No text to copy')
    return
  }

  try {
    await navigator.clipboard.writeText(text)

    emit('show-toast', 'Copied to clipboard', 'success')
  } catch (err) {
    console.error('[COPY] Failed to copy text:', err)
    // Fallback
    try {
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.opacity = '0'
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)

      emit('show-toast', 'Copied to clipboard', 'success')
    } catch (fallbackErr) {
      console.error('[COPY] Fallback also failed:', fallbackErr)
      emit('show-toast', 'Copy failed, please copy manually', 'error')
    }
  }
}

// Export a single message as an image (with an info bar containing the Agent name and time)
async function exportMessageAsImage(item, index, event) {
  if (!item || !item.text) return
  // Locate .message-body within the message node containing the button, to avoid exporting another message
  const contentEl = event?.currentTarget?.closest('.message-content')?.querySelector('.message-body')
  if (!contentEl) return
  const result = await exportElementAsImage(contentEl, {
    title: props.agent?.name || props.agent?.agent_id || 'Agent',
    subtitle: item.agent_name || '',
    time: formatMessageTime(item.timestamp) || new Date().toLocaleString(),
    filename: `haijunbot-${props.agent?.name || props.agent?.agent_id || 'agent'}-${Date.now()}`,
  })
  if (!result.ok) {
    emit('show-toast', result.error || 'Export failed', 'error')
    return
  }
  const tip = result.mode === 'clipboard'
    ? 'Image copied to clipboard'
    : result.mode === 'clipboard+download'
      ? 'Image copied and downloaded'
      : 'Image downloaded'
  emit('show-toast', tip, 'success')
}

function formatMessageTime(timestamp) {
  return timestamp || ''
}

// ---- Voice reading (browser built-in SpeechSynthesis) ----
const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
const speakingKey = ref(null)

function messageKey(item, index) {
  return item._stableId != null ? String(item._stableId) : `idx-${index}`
}

function isSpeaking(item) {
  if (!ttsSupported || speakingKey.value === null) return false
  return speakingKey.value === messageKey(item, props.messages.indexOf(item))
}

// Extract plain text from the rendered HTML to avoid reading out Markdown markers (##, **, ```, etc.)
function extractSpeakText(item) {
  if (item.html) {
    const tmp = document.createElement('div')
    tmp.innerHTML = item.html
    return (tmp.textContent || '').replace(/\s+/g, ' ').trim()
  }
  return (item.text || '').trim()
}

function stopSpeak() {
  if (!ttsSupported) return
  window.speechSynthesis.cancel()
  speakingKey.value = null
}

function toggleSpeak(item) {
  if (!ttsSupported) return
  // Clicking the same message again: stop
  if (isSpeaking(item)) {
    stopSpeak()
    return
  }
  const text = extractSpeakText(item)
  if (!text) return
  const key = messageKey(item, props.messages.indexOf(item))
  // First stop what is currently playing
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 2.0
  utterance.onend = () => {
    if (speakingKey.value === key) speakingKey.value = null
  }
  utterance.onerror = () => {
    if (speakingKey.value === key) speakingKey.value = null
  }
  speakingKey.value = key
  window.speechSynthesis.speak(utterance)
}

// For external use (e.g. auto-read) to directly read a specified message, reusing the same icon state
function speakMessage(item) {
  if (!ttsSupported || !item) return
  const text = extractSpeakText(item)
  if (!text) return
  const key = messageKey(item, props.messages.indexOf(item))
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 2.0
  utterance.onend = () => {
    if (speakingKey.value === key) speakingKey.value = null
  }
  utterance.onerror = () => {
    if (speakingKey.value === key) speakingKey.value = null
  }
  speakingKey.value = key
  window.speechSynthesis.speak(utterance)
}

// For external use to directly read arbitrary text (used when there is no corresponding message), without occupying the message icon state
function speakText(text) {
  if (!ttsSupported) return
  const content = String(text || '').replace(/\s+/g, ' ').trim()
  if (!content) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(content)
  utterance.lang = 'zh-CN'
  utterance.rate = 2.0
  window.speechSynthesis.speak(utterance)
}


onBeforeUnmount(() => {
  if (ttsSupported) {
    window.speechSynthesis.cancel()
  }
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleAsrResize)
  }
  stopRecord()
})

// ---- Voice input (Web Speech API, available only in Chromium-based browsers + secure context) ----
// The microphone is restricted by secure context: https, localhost, 127.0.0.1 work; http + other IPs are rejected by the browser.
// isSecureContext is determined directly by the browser and is more reliable than manually parsing the address.
const SpeechRecognitionImpl =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null
const asrSupported =
  !!SpeechRecognitionImpl &&
  typeof window !== 'undefined' &&
  window.isSecureContext
const isRecording = ref(false)
let recognizer = null
// Preserve any existing content in the input box as a prefix before recognition
let recordPrefix = ''
// Mark whether this session was stopped by the user (to distinguish from a browser auto-end)
let userStopped = false
// Auto-restart timer (continuous does not work on mobile; restart with a delay after onend)
let restartTimer = null

// Mobile detection: consistent with PetLobby, using the viewport width.
// Mobile browsers do not support true continuous; recognition ends automatically and needs special handling.
const isMobileDevice = ref(typeof window !== 'undefined' && window.innerWidth <= 768)
function handleAsrResize() {
  isMobileDevice.value = window.innerWidth <= 768
}
if (typeof window !== 'undefined') {
  window.addEventListener('resize', handleAsrResize)
}

function clearRestartTimer() {
  if (restartTimer) {
    clearTimeout(restartTimer)
    restartTimer = null
  }
}

function stopRecord() {
  userStopped = true
  clearRestartTimer()
  if (recognizer) {
    try {
      recognizer.stop()
    } catch (e) {
      // Ignore the exception from repeated stops
    }
  }
  isRecording.value = false
}

// 🎤 button: click to start recording, click again to stop.
// No long-press: on mobile, long-press triggers native text selection/context menu, interrupting recording.
function toggleRecord() {
  if (!asrSupported) return
  if (isRecording.value) {
    stopRecord()
    return
  }
  startRecord()
}

function startRecord() {
  if (!asrSupported || isRecording.value) return
  recordPrefix = props.inputText || ''
  userStopped = false
  clearRestartTimer()
  recognizer = new SpeechRecognitionImpl()
  recognizer.lang = 'zh-CN'
  // Desktop supports true continuous; on mobile this property is ineffective and recognition ends automatically,
  // simulated continuous recognition via delayed restart in onend.
  recognizer.continuous = !isMobileDevice.value
  recognizer.interimResults = true

  recognizer.onresult = (event) => {
    let finalText = ''
    let interimText = ''
    for (let i = 0; i < event.results.length; i++) {
      const result = event.results[i]
      if (result.isFinal) {
        finalText += result[0].transcript
      } else {
        interimText += result[0].transcript
      }
    }
    const merged = recordPrefix + finalText + interimText
    emit('input-change', { target: { value: merged, selectionStart: merged.length } })
  }

  recognizer.onerror = (event) => {
    const err = event.error
    if (err === 'not-allowed' || err === 'service-not-allowed') {
      // Unauthorized/service unavailable: cannot continue, stop directly
      emit('show-toast', 'Microphone not authorized; please allow microphone access in your browser', 'error')
      userStopped = true
      clearRestartTimer()
      isRecording.value = false
      return
    }
    if (err === 'aborted' || err === 'no-speech') {
      // aborted: recognition was interrupted (a normal occurrence during auto-restart)
      // no-speech: silence timeout, very common on mobile
      // Neither is treated as a fatal error; hand off to the restart logic in onend
      return
    }
    // Other errors (network / audio-capture / language-not-supported, etc.)
    emit('show-toast', `Speech recognition failed: ${err}`, 'error')
    userStopped = true
    clearRestartTimer()
    isRecording.value = false
  }

  recognizer.onend = () => {
    // The user stopped actively, or it ended due to an error; end directly
    if (userStopped || !isRecording.value) {
      isRecording.value = false
      return
    }
    // continuous does not work on mobile; recognition ends automatically; restart with a delay to simulate continuous recognition.
    // Immediate restart easily throws InvalidStateError on mobile, so add a small delay.
    clearRestartTimer()
    restartTimer = setTimeout(() => {
      restartTimer = null
      if (userStopped || !isRecording.value) return
      try {
        recognizer.start()
      } catch (e) {
        // Restart failed (e.g. the recognizer is no longer valid): fall back to the stopped state
        isRecording.value = false
      }
    }, 250)
  }

  try {
    recognizer.start()
    isRecording.value = true
  } catch (e) {
    emit('show-toast', 'Unable to start speech recognition', 'error')
    isRecording.value = false
  }
}

// Hold Right Ctrl to talk: keydown starts, keyup stops (Left Ctrl has no effect)
// Quick double-tap of Right Ctrl: send
// The input box already has keydown listeners (send, etc.); keep the existing event forwarding here
const DOUBLE_TAP_MS = 300 // Double-tap detection window
const QUICK_TAP_MS = 250  // Single "quick press" detection (distinct from hold-to-talk)
let ctrlDownTime = 0
let lastQuickTapTime = 0

function handleInputKeydown(event) {
  if (event.code === 'ControlRight') {
    event.preventDefault()
    const now = Date.now()
    // The previous tap was a quick single click and within the double-tap window → treat as double-tap send
    if (lastQuickTapTime && now - lastQuickTapTime < DOUBLE_TAP_MS) {
      lastQuickTapTime = 0
      emit('send')
      return
    }
    ctrlDownTime = now
    if (!isRecording.value) startRecord()
    return
  }
  emit('keydown', event)
}

function handleInputKeyup(event) {
  if (event.code === 'ControlRight') {
    event.preventDefault()
    // A very short press counts as a "quick single click"; record it for the next double-tap detection
    if (ctrlDownTime && Date.now() - ctrlDownTime < QUICK_TAP_MS) {
      lastQuickTapTime = Date.now()
    } else {
      lastQuickTapTime = 0
    }
    ctrlDownTime = 0
    if (isRecording.value) stopRecord()
  }
}

function getStatusClass(agent) {
  if (!agent) return 'stopped'
  return agent.status || 'stopped'
}

function getStatusLabel(agent) {
  if (!agent) return ''
  const statusMap = {
    running: 'Running',
    stopped: 'Stopped',
    waiting_multi: 'Waiting for input',
    waiting_single: 'Waiting for input',
    waiting_confirm: 'Waiting for confirmation',
  }
  return statusMap[agent.status] || agent.status || ''
}

// Terminal history text: prefer terminal_content; fall back to concatenating execution_chunks when missing
// (on page refresh terminal_content may not be flushed yet, only chunks are flushed)
function getTerminalHistoryText(item) {
  if (!item) return ''
  if (item.terminal_content) return item.terminal_content
  const chunks = item.execution_chunks
  if (Array.isArray(chunks) && chunks.length > 0) {
    return chunks.join('')
  }
  return ''
}

// Whether to show the Terminal Output text block: must be strictly complementary to the xterm branch condition above,
// otherwise, when execution_chunks already has content during execution, it would display simultaneously with xterm
function showTerminalHistory(item) {
  if (!item || item.output_type !== 'execution') return false
  const hasXterm = Boolean(item.execution_id) && !item.is_finished && !item.terminal_content
  if (hasXterm) return false
  return Boolean(getTerminalHistoryText(item))
}

function getTerminalStyle(terminalContent) {
  if (!terminalContent) return {}
  const lineCount = terminalContent.split('\n').length
  const fontSize = 12
  const lineHeight = 1.4
  const maxLines = 30
  const headerHeight = 41
  const contentPadding = 32
  const contentHeight = lineCount * fontSize * lineHeight
  const totalHeight = contentHeight + headerHeight + contentPadding
  if (lineCount <= maxLines) {
    return { fontFamily: "'Consolas', 'Microsoft YaHei', monospace", fontSize: `${fontSize}px`, lineHeight: lineHeight, height: `${totalHeight}px` }
  }
  const maxHeight = maxLines * fontSize * lineHeight + headerHeight + contentPadding
  return { fontFamily: "'Consolas', 'Microsoft YaHei', monospace", fontSize: `${fontSize}px`, lineHeight: lineHeight, height: `${maxHeight}px` }
}
</script>

<style scoped>
.session-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  position: fixed;
  background: rgba(9, 16, 28, 0.86);
  border: 1px solid var(--color-border-subtle);
  border-radius: 14px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(32, 200, 255, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.session-panel.active {
  border-color: rgba(32, 200, 255, 0.55);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(32, 200, 255, 0.5),
    0 0 24px rgba(32, 200, 255, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.session-panel-embedded {
  position: relative !important;
  width: 100% !important;
  height: 100% !important;
  top: auto !important;
  left: auto !important;
}

.session-panel-dragging {
  cursor: grabbing !important;
  user-select: none;
}

.session-resize-handle {
  position: absolute;
  z-index: 10;
}

.session-resize-n {
  top: -3px;
  left: 8px;
  right: 8px;
  height: 6px;
  cursor: ns-resize;
}

.session-resize-s {
  bottom: -3px;
  left: 8px;
  right: 8px;
  height: 6px;
  cursor: ns-resize;
}

.session-resize-e {
  right: -3px;
  top: 8px;
  bottom: 8px;
  width: 6px;
  cursor: ew-resize;
}

.session-resize-w {
  left: -3px;
  top: 8px;
  bottom: 8px;
  width: 6px;
  cursor: ew-resize;
}

.session-resize-ne {
  top: -3px;
  right: -3px;
  width: 10px;
  height: 10px;
  cursor: nesw-resize;
}

.session-resize-nw {
  top: -3px;
  left: -3px;
  width: 10px;
  height: 10px;
  cursor: nwse-resize;
}

.session-resize-se {
  bottom: -3px;
  right: -3px;
  width: 10px;
  height: 10px;
  cursor: nwse-resize;
}

.session-resize-sw {
  bottom: -3px;
  left: -3px;
  width: 10px;
  height: 10px;
  cursor: nesw-resize;
}

.session-panel-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-secondary);
  position: relative;
}

.empty-icon {
  font-size: 36px;
  opacity: 0.4;
}

.empty-text {
  font-size: 13px;
  opacity: 0.6;
}

.empty-close-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 4px;
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-close-btn:hover {
  background: rgba(255, 60, 72, 0.2);
  color: var(--color-error);
}

.session-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background:
    linear-gradient(160deg, rgba(32, 200, 255, 0.10) 0%, transparent 46%),
    var(--color-bg-tertiary);
  border-bottom: 1px solid var(--color-border-subtle);
  border-left: 2px solid var(--color-accent);
  flex-shrink: 0;
}

.session-agent-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.session-agent-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--color-bg-secondary);
  flex-shrink: 0;
}

.session-agent-status.running {
  background: rgba(32, 200, 255, 0.2);
  color: var(--color-accent);
}

.session-agent-status.stopped {
  background: rgba(255, 60, 72, 0.2);
  color: var(--color-error);
}

.session-agent-status.waiting_multi,
.session-agent-status.waiting_single,
.session-agent-status.waiting_confirm {
  background: rgba(255, 133, 32, 0.2);
  color: var(--color-warning);
}

.session-header-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.session-close-agent-btn,
.session-close-panel-btn {
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.session-close-agent-btn:hover {
  background: rgba(255, 60, 72, 0.2);
  color: var(--color-error);
}

.session-close-panel-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.messages {
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--color-bg-tile);
  min-height: 0;
  /* Override the user-select: none inherited from .workspace-panel so message content can be selected and copied with Ctrl+C */
  user-select: text;
  -webkit-user-select: text;
}

.message {
  position: relative;
  background: rgba(18, 30, 50, 0.45);
  border-radius: var(--tile-radius);
  padding: 6px 10px;
  border: 1px solid var(--color-border-subtle);
  border-left: 2px solid var(--color-accent);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.message:hover {
  border-color: var(--color-border);
  box-shadow: 0 6px 20px rgba(0, 120, 190, 0.18);
}

.message-user_input {
  background: rgba(32, 200, 255, 0.35);
  border-left: 3px solid var(--color-accent);
}

.message-STREAM {
  background: rgba(18, 30, 50, 0.45);
  border-left: 3px solid var(--color-border-subtle);
}

.message-content {
  position: relative;
}

.message-body {
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
  font-family: 'Consolas', 'Microsoft YaHei', sans-serif;
}

/* Typewriter cursor at the end of streaming output (pet thumbnail) */
.stream-caret {
  display: inline-block;
  vertical-align: text-bottom;
  margin-left: 2px;
  padding-bottom: 1px;
  animation: stream-caret-blink 1s steps(2, start) infinite;
}

.stream-caret-pet {
  position: relative;
  display: block;
  width: 12px;
  height: 11px;
  border-radius: 50% 50% 46% 46%;
  background: linear-gradient(180deg, #7ee7ff 0%, #20c8ff 100%);
  box-shadow: 0 0 6px rgba(32, 200, 255, 0.65), 0 0 2px rgba(126, 231, 255, 0.9);
}

.stream-caret-pet .stream-caret-ear {
  position: absolute;
  top: -3px;
  width: 5px;
  height: 5px;
  background: #20c8ff;
  border-radius: 2px 2px 0 0;
}

.stream-caret-pet .stream-caret-ear.l {
  left: 0;
  transform: rotate(-18deg);
}

.stream-caret-pet .stream-caret-ear.r {
  right: 0;
  transform: rotate(18deg);
}

.stream-caret-pet .stream-caret-eye {
  position: absolute;
  top: 4px;
  width: 2.5px;
  height: 2.5px;
  background: #08243a;
  border-radius: 50%;
}

.stream-caret-pet .stream-caret-eye.l {
  left: 2px;
}

.stream-caret-pet .stream-caret-eye.r {
  right: 2px;
}

@keyframes stream-caret-blink {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0.25;
  }
}

@media (prefers-reduced-motion: reduce) {
  .stream-caret {
    animation: none;
  }
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.message-agent {
  color: var(--color-accent);
}

.message-agent-list {
  color: var(--color-text-secondary);
  opacity: 0.85;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 40ch;
}

.message-separator {
  opacity: 0.5;
}

.message-silent {
  font-size: 10px;
}

.message-speak-btn {
  background: none;
  border: none;
  padding: 0;
  margin-left: 4px;
  font-size: 10px;
  line-height: 1;
  cursor: pointer;
  color: var(--color-text-secondary);
  opacity: 0.7;
  transition: opacity 0.2s ease;
}

.message-speak-btn:hover {
  opacity: 1;
  color: var(--color-text-primary);
}

.message-speak-btn.speaking {
  opacity: 1;
  color: var(--color-accent, #4a9eff);
}

.copy-message-btn {
  position: absolute;
  top: 0;
  right: 0;
  background: var(--color-bg-hover);
  border: none;
  border-radius: var(--tile-radius-xs);
  padding: 4px 8px;
  color: var(--color-text-secondary);
  opacity: 0;
  transition: opacity 0.2s ease;
  z-index: 10;
}

.copy-message-btn svg {
  width: 14px;
  height: 14px;
}

.message-content:hover .copy-message-btn {
  opacity: 1;
}

.copy-message-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.export-message-btn {
  position: absolute;
  top: 0;
  right: 34px;
  background: var(--color-bg-hover);
  border: none;
  border-radius: var(--tile-radius-xs);
  padding: 4px 8px;
  color: var(--color-text-secondary);
  opacity: 0;
  transition: opacity 0.2s ease;
  z-index: 10;
}

.export-message-btn svg {
  width: 14px;
  height: 14px;
}

.message-content:hover .export-message-btn {
  opacity: 1;
}

.export-message-btn:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.terminal-wrapper {
  margin-top: 6px;
}

.terminal-host {
  width: 100%;
  height: 100%;
  user-select: text;
}

.terminal-history {
  margin-top: 6px;
  background: var(--color-bg-primary);
  border-radius: var(--tile-radius-xs);
  overflow: hidden;
  max-height: 400px;
  display: flex;
  flex-direction: column;
}

.terminal-history-header {
  padding: 4px 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
  background: var(--color-bg-tertiary);
  border-bottom: 1px solid var(--color-border-subtle);
}

.terminal-history-content {
  padding: 8px;
  font-size: 12px;
  line-height: 1.4;
  overflow-x: auto;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  flex: 1;
  min-height: 0;
}

.input-area {
  flex-shrink: 0;
  padding: 0;
  background: var(--color-bg-secondary);
  border-top: 1px solid var(--color-border-subtle);
  width: 100%;
}

.input-toggle-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 8px;
}

.input-toggle-btn {
  background: transparent;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
}

.input-toggle-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 0 8px 8px 8px;
  box-sizing: border-box;
}
.agent-thinking-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.thinking-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-border-subtle);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.thinking-text {
  font-size: 11px;
}

.input-wrapper textarea,
.input-wrapper input[type="text"] {
  width: 100%;
  padding: 8px 10px;
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius-xs);
  color: var(--color-text-primary);
  font-size: 14px;
  font-family: 'Consolas', 'Microsoft YaHei', sans-serif;
  box-sizing: border-box;
}

.input-wrapper textarea {
  resize: vertical;
  min-height: 96px;
}

.input-wrapper input[type="text"] {
  min-height: 36px;
}

.input-wrapper textarea:focus,
.input-wrapper input[type="text"]:focus {
  outline: none;
  border-color: var(--color-accent);
}

.input-wrapper textarea::placeholder,
.input-wrapper input[type="text"]::placeholder {
  color: var(--color-text-secondary);
}

.buffer-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-warning);
  cursor: pointer;
}

.buffer-icon {
  font-size: 12px;
}

.buffer-text {
  font-size: 11px;
}

.input-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.action-btn,
.complete-btn,
.send-btn {
  padding: 8px 16px;
  border: none;
  border-radius: var(--tile-radius-xs);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-btn {
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
}

.action-btn:hover:not(:disabled) {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.asr-btn {
  /* Prevent text selection on long-press of buttons (recording switched to click-toggle, not relying on long-press gestures) */
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}

.asr-btn.recording {
  background: rgba(255, 80, 80, 0.2);
  color: #ff5050;
  animation: asr-pulse 1.2s ease-in-out infinite;
}

@keyframes asr-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.complete-btn {
  background: rgba(54, 255, 124, 0.15);
  color: var(--color-success);
}

.complete-btn:hover:not(:disabled) {
  background: rgba(54, 255, 124, 0.25);
}

.send-btn {
  background: rgba(32, 200, 255, 0.15);
  color: var(--color-accent);
  border: 1px solid var(--color-accent);
  min-width: 64px;
  min-height: 36px;
}

.send-btn:hover:not(:disabled) {
  background: rgba(32, 200, 255, 0.25);
}

.action-btn:disabled,
.complete-btn:disabled,
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Mobile adaptation: enlarge the send button */
@media (max-width: 768px) {
  .send-btn {
    min-width: 144px;
    min-height: 44px;
    padding: 10px 20px;
    font-size: 15px;
  }

  /* Mobile: keep the title bar on one line, shrink/ellipsize the Agent name, and keep the close button on the same line as the content */
  .session-panel-header {
    flex-wrap: nowrap;
  }

  .session-agent-name {
    flex: 1 1 auto;
    min-width: 0;
  }

  .session-agent-status {
    flex-shrink: 0;
  }

  .session-header-actions {
    margin-left: auto;
  }
}

/* Inline confirmation area */
.panel-confirm-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(32, 200, 255, 0.08);
  border: 1px solid rgba(32, 200, 255, 0.3);
  border-radius: var(--tile-radius-xs);
  margin: 0 8px 8px;
}

.panel-confirm-message {
  flex: 1;
  font-size: 12px;
  color: var(--color-text-primary);
  line-height: 1.4;
  word-break: break-all;
}

.panel-confirm-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.panel-confirm-btn {
  padding: 4px 12px;
  border: none;
  border-radius: var(--tile-radius-xs);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.panel-confirm-yes {
  background: rgba(32, 200, 255, 0.15);
  color: var(--color-accent);
  border: 1px solid var(--color-accent);
}

.panel-confirm-yes:hover {
  background: rgba(32, 200, 255, 0.25);
}

.panel-confirm-no {
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
}

.panel-confirm-no:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.panel-confirm-btn.default {
  background: var(--color-accent);
  color: #fff;
  border-color: var(--color-accent);
  box-shadow: 0 0 8px rgba(32, 200, 255, 0.3);
}
</style>
