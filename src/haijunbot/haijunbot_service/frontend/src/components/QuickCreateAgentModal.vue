<template>
  <div class="modal-overlay" v-if="visible" @click.self="$emit('close')">
    <div class="modal quick-create-agent-modal">
      <h2>⚡ Create an Agent in One Sentence</h2>
      <p class="quick-create-hint">Describe a task; all other parameters use defaults. The Agent starts executing the task immediately after creation.</p>

      <div class="form-group">
        <label>Task description</label>
        <textarea
          ref="taskInput"
          v-model="taskText"
          class="form-control"
          rows="4"
          placeholder="e.g. Analyze the current project directory structure and suggest optimizations"
          @keydown="handleKeydown"
          @keyup="handleKeyup"
        ></textarea>
        <div class="form-help">Press Ctrl / Cmd + Enter or Ctrl + D to submit quickly; a quick double-tap of the right Ctrl also submits.</div>
      </div>

      <div v-if="error" class="error-message">{{ error }}</div>

      <div class="modal-actions">
        <button class="link-btn" @click="$emit('open-full')" :disabled="loading">Open full creation panel</button>
        <button class="btn secondary" @click="$emit('close')" :disabled="loading">Cancel</button>
        <button class="btn primary" @click="submit" :disabled="loading || !taskText.trim()">
          {{ loading ? 'Creating…' : 'Create and run' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const emit = defineEmits(['close', 'submit', 'open-full'])

const taskText = ref('')
const taskInput = ref(null)

// Reset the input and focus on each open
watch(() => props.visible, async (val) => {
  if (val) {
    taskText.value = ''
    await nextTick()
    taskInput.value?.focus()
  }
})

function submit() {
  if (props.loading) return
  const task = taskText.value.trim()
  if (!task) return
  emit('submit', {
    task,
    agentType: 'agent',
    workingDir: '~'
  })
}

// Submission shortcuts match the multi-line input: Ctrl/Cmd+Enter, Ctrl+D, and a quick double-tap of the right Ctrl
const DOUBLE_TAP_MS = 300 // double-tap detection window
const QUICK_TAP_MS = 250  // single "quick press" detection
let ctrlDownTime = 0
let lastQuickTapTime = 0

function handleKeydown(event) {
  // Quick right-Ctrl double-tap → submit (this modal has no voice input, so hold-to-talk is not handled)
  if (event.code === 'ControlRight') {
    event.preventDefault()
    const now = Date.now()
    if (lastQuickTapTime && now - lastQuickTapTime < DOUBLE_TAP_MS) {
      lastQuickTapTime = 0
      submit()
      return
    }
    ctrlDownTime = now
    return
  }
  // Ctrl/Cmd + Enter or Ctrl + D → submit
  const key = typeof event.key === 'string' ? event.key.toLowerCase() : ''
  if ((event.ctrlKey || event.metaKey) && (key === 'enter' || key === 'd')) {
    event.preventDefault()
    submit()
  }
}

function handleKeyup(event) {
  if (event.code !== 'ControlRight') return
  event.preventDefault()
  // A very short press counts as a "quick tap"; record it for the next double-tap check
  if (ctrlDownTime && Date.now() - ctrlDownTime < QUICK_TAP_MS) {
    lastQuickTapTime = Date.now()
  } else {
    lastQuickTapTime = 0
  }
  ctrlDownTime = 0
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
  padding: 20px;
}

.modal-overlay .modal {
  background: rgba(9, 16, 28, 0.86);
  border: 1px solid var(--color-border-subtle);
  border-radius: 14px;
  padding: 28px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(32, 200, 255, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.modal-overlay .modal.quick-create-agent-modal {
  width: min(92vw, 520px);
  max-width: 520px;
  max-height: calc(var(--app-height, 100vh) - 40px);
  overflow-y: auto;
}

.quick-create-agent-modal h2 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: var(--color-text-primary);
}

.quick-create-hint {
  margin: 0 0 18px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.quick-create-agent-modal .form-group {
  margin-bottom: 16px;
}

.quick-create-agent-modal .form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.quick-create-agent-modal .form-control {
  width: 100%;
  box-sizing: border-box;
}

.quick-create-agent-modal .form-help {
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary, var(--color-text-secondary));
}

.link-btn {
  margin-right: auto;
  background: none;
  border: none;
  padding: 0;
  font-size: 13px;
  color: var(--color-accent, #4fc3f7);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.link-btn:hover:not(:disabled) {
  color: var(--color-accent-hover, #7ddcff);
}

.link-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 80, 80, 0.12);
  border: 1px solid rgba(255, 80, 80, 0.35);
  color: var(--color-error);
  font-size: 13px;
  white-space: pre-wrap;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
