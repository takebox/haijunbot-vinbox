<template>
  <!-- Settings modal -->
  <div class="modal-overlay" v-if="visible">
    <div class="modal settings-modal">
      <div class="modal-header">
        <h2>Settings</h2>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="form-group">
        <div class="toggle-wrapper">
          <label class="toggle-switch">
            <input type="checkbox" v-model="localAutoLoginEnabled" @change="handleAutoLoginChange" class="toggle-input" />
            <span class="toggle-slider"></span>
          </label>
          <div class="toggle-info">
            <span class="toggle-label-text">Skip Login (Remember Token)</span>
            <span class="form-help">When enabled, the token is saved locally in the browser after successful login, and auto-connect will be attempted on next launch.</span>
          </div>
        </div>
      </div>

      <div class="form-group">
        <div class="toggle-wrapper">
          <label class="toggle-switch">
            <input type="checkbox" v-model="localNotifyOnExit" @change="handleNotifyOnExitChange" class="toggle-input" />
            <span class="toggle-slider"></span>
          </label>
          <div class="toggle-info">
            <span class="toggle-label-text">Notify on Agent Exit</span>
            <span class="form-help">When enabled, a system notification will appear when an Agent finishes running (does not affect sound alerts).</span>
          </div>
        </div>
      </div>

      <div class="form-group">
        <div class="toggle-wrapper">
          <label class="toggle-switch">
            <input type="checkbox" v-model="localNotifyOnInput" @change="handleNotifyOnInputChange" class="toggle-input" />
            <span class="toggle-slider"></span>
          </label>
          <div class="toggle-info">
            <span class="toggle-label-text">Notify on Input Required</span>
            <span class="form-help">When enabled, a system notification will appear when an Agent is waiting for input (does not affect sound alerts).</span>
          </div>
        </div>
      </div>

      <!-- My Account -->
      <div class="form-group">
        <label>Current User</label>
        <div style="font-size:14px">{{ currentUserInfo?.username || '-' }}<span v-if="currentUserInfo?.display_name" style="color:var(--text-secondary,#8ba3b8);margin-left:8px">({{ currentUserInfo.display_name }})</span></div>
      </div>
      <div class="form-group">
        <label>Change Password</label>
        <div class="form-row"><label>Old Password</label><input v-model="changePasswordForm.old_password" type="password" placeholder="Enter old password" /></div>
        <div class="form-row"><label>New Password</label><input v-model="changePasswordForm.new_password" type="password" placeholder="Enter new password" /></div>
        <div class="form-row"><label>Confirm Password</label><input v-model="changePasswordForm.confirm_password" type="password" placeholder="Re-enter new password" /></div>
        <button class="ghost-btn" @click="changePassword" :disabled="loading">Change Password</button>
      </div>

      <!-- Message History Management -->
      <div class="form-group">
        <div class="history-info">
          <div class="history-stat">
            <span class="history-stat-label">Total messages:</span>
            <span class="history-stat-value">{{ historyStorage.getTotalCount() }}</span>
          </div>
          <div class="history-stat">
            <span class="history-stat-label">Storage used:</span>
            <span class="history-stat-value">{{ historyStorage.getStorageInfo().totalSizeFormatted }}</span>
          </div>
        </div>
      </div>
      <div class="form-group">
        <button class="danger-btn" @click="confirmClearHistory" :disabled="historyStorage.getTotalCount() === 0">
          Clear History
        </button>
      </div>


      <!-- Hide Working Directory -->
      <div class="form-group">
        <div class="toggle-wrapper">
          <label class="toggle-switch">
            <input type="checkbox" v-model="localHideWorkingDir" @change="handleHideWorkingDirChange" class="toggle-input" />
            <span class="toggle-slider"></span>
          </label>
          <div class="toggle-info">
            <span class="toggle-label-text">Hide Working Directory</span>
            <span class="form-help">When enabled, Agent working directories will be shown as placeholders, useful for screen recording or screenshots (only effective in local browser).</span>
          </div>
        </div>
      </div>

      <!-- Auto-install/Update Browser Extension -->
      <div class="form-group">
        <div class="toggle-wrapper">
          <label class="toggle-switch">
            <input type="checkbox" v-model="localAutoInstallBrowserExt" @change="handleAutoInstallBrowserExtChange" class="toggle-input" />
            <span class="toggle-slider"></span>
          </label>
          <div class="toggle-info">
            <span class="toggle-label-text">Auto-install/Update Browser Extension</span>
            <span class="form-help">Off by default. When enabled, the local daemon will automatically download and overwrite the local extension directory when the extension version changes on the gateway; the browser will not be restarted, you need to click "Refresh" in chrome://extensions for the new version to take effect.</span>
          </div>
        </div>
      </div>
      <!-- Terminal Name -->
      <div class="form-group">
        <label>Terminal Name</label>
        <div class="form-help" style="margin-bottom:10px">Used to distinguish different terminals on the gateway side (e.g. "Home Desktop", "Work Laptop"). Leave empty to use the default name; changes are automatically synced to the browser extension and local daemon, allowing Agents to locate this machine by name.</div>
        <input
          class="node-name-input"
          :value="localTerminalName"
          placeholder="e.g. Work Laptop"
          @input="onTerminalNameInput($event.target.value)"
          @keydown.enter="$event.target.blur()"
        />
      </div>

      <!-- Local Daemon Port -->
      <div class="form-group">
        <label>Local Daemon Port</label>
        <div class="form-help" style="margin-bottom:10px">The listening port of the local haijunbot-daemon (default 17800). If the default port is occupied or the daemon uses a different port, enter the new port number here. The browser will use this to connect to the local daemon (address is always 127.0.0.1). Leave empty or enter the default port to restore the default.</div>
        <input
          class="node-name-input"
          :value="localDaemonPort"
          placeholder="17800"
          inputmode="numeric"
          @input="onDaemonPortInput($event.target.value)"
          @change="onDaemonPortCommit"
          @keydown.enter="$event.target.blur()"
          @blur="onDaemonPortCommit"
        />
      </div>

      <!-- Node Display Name Mapping -->
      <div class="form-group">
        <label>Node Display Names</label>
        <div class="form-help" style="margin-bottom:10px">Custom display names for nodes (only effective in local browser, leave empty to show original node ID).</div>
        <div v-if="nodeList.length === 0" class="form-help">No available nodes.</div>
        <div v-for="node in nodeList" :key="node.value" class="node-name-row">
          <span class="node-name-origin" :title="node.value">{{ node.value }}</span>
          <input
            class="node-name-input"
            :value="localNodeDisplayNames[node.value] || ''"
            :placeholder="'Custom display name'"
            @input="onNodeNameInput(node.value, $event.target.value)"
            @keydown.enter="$event.target.blur()"
          />
        </div>
      </div>

      <!-- Connection Management -->
      <div class="form-group">
        <label>Connection Management</label>
        <div class="connection-management-section">
          <button class="danger-btn" @click="disconnectAll" :disabled="!socket">
            Disconnect
          </button>
          <span class="form-help">Disconnect all WebSocket connections and refresh the page</span>
        </div>
      </div>

      <div class="modal-actions">
        <button class="ghost-btn" @click="close">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  historyStorage: {
    type: Object,
    required: true
  },
  socket: {
    type: Object,
    default: null
  },
  autoLoginEnabled: {
    type: Boolean,
    default: false
  },
  notifyOnExit: {
    type: Boolean,
    default: false
  },
  notifyOnInput: {
    type: Boolean,
    default: false
  },
  auth: { type: Object, default: () => ({}) },
  fetchWithAuth: { type: Function, default: null },
  gatewayUrl: { type: String, default: '127.0.0.1:8000' },
  getHttpProtocol: { type: Function, default: () => 'http' },
  showToast: { type: Function, default: () => {} },
  nodeOptions: { type: Array, default: () => [] },
  nodeDisplayNames: { type: Object, default: () => ({}) },
  hideWorkingDir: { type: Boolean, default: false },
  autoInstallBrowserExt: { type: Boolean, default: false },
  terminalName: { type: String, default: '' },
  daemonPort: { type: String, default: '' }
})

const emit = defineEmits([
  'update:visible',
  'confirmClearHistory',
  'disconnectAll',
  'update:autoLoginEnabled',
  'saveAutoLoginSetting',
  'update:notifyOnExit',
  'update:notifyOnInput',
  'saveNotifySettings',
  'saveNodeDisplayNames',
  'update:hideWorkingDir',
  'saveHideWorkingDirSetting',
  'update:autoInstallBrowserExt',
  'saveAutoInstallBrowserExtSetting',
  'update:terminalName',
  'saveTerminalNameSetting',
  'update:daemonPort',
  'saveDaemonPortSetting'
])

// Local state
const localAutoLoginEnabled = ref(props.autoLoginEnabled)
const localNotifyOnExit = ref(props.notifyOnExit)
const localNotifyOnInput = ref(props.notifyOnInput)
const localHideWorkingDir = ref(props.hideWorkingDir)
const localAutoInstallBrowserExt = ref(props.autoInstallBrowserExt)
const localTerminalName = ref(props.terminalName)
const localDaemonPort = ref(props.daemonPort)
const changePasswordForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const loading = ref(false)
// Local copy of node display names (updated in real-time during editing and synced upward)
const localNodeDisplayNames = ref({ ...(props.nodeDisplayNames || {}) })

// Node list (deduplicated, value is original node_id)
const nodeList = computed(() => {
  const seen = new Set()
  const list = []
  for (const opt of props.nodeOptions || []) {
    const value = String(opt?.node_id || opt?.value || '').trim()
    if (!value || seen.has(value)) continue
    seen.add(value)
    list.push({ value })
  }
  return list
})

// Computed properties
const currentUserInfo = computed(() => props.auth?.userInfo || null)
const currentUserId = computed(() => props.auth?.userInfo?.user_id || '')

// Helper functions
function getGatewayAddress() {
  const raw = (props.gatewayUrl || '127.0.0.1:8000').trim()
  // Full URL (e.g. wss://hjb-ai.cn) needs URL parsing to avoid split(':') misjudgment
  if (raw.includes('://')) {
    try {
      const url = new URL(raw)
      const isTls = url.protocol === 'https:' || url.protocol === 'wss:'
      return {
        host: url.hostname || '127.0.0.1',
        port: url.port || (isTls ? '443' : '80'),
      }
    } catch (e) {
      return { host: '127.0.0.1', port: '8000' }
    }
  }
  const parts = raw.split(':')
  return { host: parts[0] || '127.0.0.1', port: parts[1] || '8000' }
}

function buildApiUrl(path) {
  const { host, port } = getGatewayAddress()
  const proto = props.getHttpProtocol ? props.getHttpProtocol() : 'http'
  return `${proto}://${host}:${port}${path}`
}

// Watch props changes
watch(() => props.autoLoginEnabled, (newVal) => {
  localAutoLoginEnabled.value = newVal
})

watch(() => props.notifyOnExit, (newVal) => {
  localNotifyOnExit.value = newVal
})

watch(() => props.notifyOnInput, (newVal) => {
  localNotifyOnInput.value = newVal
})

watch(() => props.nodeDisplayNames, (newVal) => {
  localNodeDisplayNames.value = { ...(newVal || {}) }
}, { deep: true })

watch(() => props.hideWorkingDir, (newVal) => {
  localHideWorkingDir.value = newVal
})
watch(() => props.autoInstallBrowserExt, (newVal) => {
  localAutoInstallBrowserExt.value = newVal
})

watch(() => props.terminalName, (newVal) => {
  localTerminalName.value = newVal
})

watch(() => props.daemonPort, (newVal) => {
  localDaemonPort.value = newVal
})

// Local daemon port input: updates local copy and syncs upward (parent component handles persistence to localStorage).
// No real-time persistence during input to avoid repeatedly writing incomplete port numbers; commits on blur/Enter.
function onDaemonPortInput(value) {
  localDaemonPort.value = String(value || '').trim()
  emit('update:daemonPort', localDaemonPort.value)
}
function onDaemonPortCommit() {
  emit('saveDaemonPortSetting', localDaemonPort.value)
}

// Terminal name input: updates local copy and syncs upward (parent component handles persistence and sync to extension/daemon)
function onTerminalNameInput(value) {
  const trimmed = String(value || '').trim()
  localTerminalName.value = trimmed
  emit('update:terminalName', trimmed)
  emit('saveTerminalNameSetting', trimmed)
}

// Hide working directory toggle change
function handleHideWorkingDirChange() {
  emit('update:hideWorkingDir', localHideWorkingDir.value)
  emit('saveHideWorkingDirSetting', localHideWorkingDir.value)
}
// Auto-install/update browser extension toggle change (parent component handles persistence to localStorage and pushes to local daemon)
function handleAutoInstallBrowserExtChange() {
  emit('update:autoInstallBrowserExt', localAutoInstallBrowserExt.value)
  emit('saveAutoInstallBrowserExtSetting', localAutoInstallBrowserExt.value)
}

// Node display name input: updates local copy and syncs upward (parent component handles persistence)
function onNodeNameInput(nodeId, value) {
  const next = { ...localNodeDisplayNames.value }
  const trimmed = String(value || '').trim()
  if (trimmed) next[nodeId] = trimmed
  else delete next[nodeId]
  localNodeDisplayNames.value = next
  emit('saveNodeDisplayNames', next)
}

// Close dialog
function close() {
  emit('update:visible', false)
}

// Handle skip-login setting change
function handleAutoLoginChange() {
  emit('update:autoLoginEnabled', localAutoLoginEnabled.value)
  emit('saveAutoLoginSetting')
}

// Handle Agent exit notification toggle change
function handleNotifyOnExitChange() {
  emit('update:notifyOnExit', localNotifyOnExit.value)
  emit('saveNotifySettings')
}

// Handle input-required notification toggle change
function handleNotifyOnInputChange() {
  emit('update:notifyOnInput', localNotifyOnInput.value)
  emit('saveNotifySettings')
}



// Confirm clear history
function confirmClearHistory() {
  emit('confirmClearHistory')
}



// Disconnect all connections
function disconnectAll() {
  emit('disconnectAll')
}



// Change password
async function changePassword() {
  const form = changePasswordForm.value
  if (!form.old_password || !form.new_password) { props.showToast('Old password and new password are required', 'error'); return }
  if (form.new_password !== form.confirm_password) { props.showToast('New passwords do not match', 'error'); return }
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/users/${currentUserId.value}/change-password`), {
      method: 'POST', body: JSON.stringify({ old_password: form.old_password, new_password: form.new_password })
    })
    const result = await resp.json()
    if (result.success) { props.showToast('Password changed successfully', 'success'); changePasswordForm.value = { old_password: '', new_password: '', confirm_password: '' } }
    else props.showToast(result.error?.message || 'Change failed', 'error')
  } catch (e) { props.showToast('Change failed: ' + e.message, 'error') }
  finally { loading.value = false }
}




</script>

<style scoped>

/* Modal overlay layer */
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

/* Modal base styles */
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

/* ========== Form Group styles (migrated from the App.vue global styles) ========== */
.form-group {
  margin-bottom: 16px;
  padding: 16px;
  background: var(--color-bg-secondary);
  border: none;
  border-radius: var(--tile-radius-sm);
  box-shadow: 0 2px 8px var(--color-shadow);
}

.form-group.inline {
  display: flex;
  gap: 12px;
}

.form-group.inline .form-item {
  flex: 1;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  letter-spacing: 0.01em;
}

.form-group input {
  width: 100%;
  padding: 11px 14px;
  background: var(--color-bg-primary);
  border: 0.5px solid var(--color-border);
  border-radius: var(--tile-radius);
  color: var(--color-text-primary);
  font-size: 14px;
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-accent);
  background: var(--color-bg-primary);
}

.form-group select {
  width: 100%;
  padding: 11px 14px;
  background: var(--color-bg-primary);
  border: 0.5px solid var(--color-border);
  border-radius: var(--tile-radius);
  color: var(--color-text-primary);
  font-size: 14px;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%239ca3af' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 36px;
}

.form-group select:focus {
  outline: none;
  border-color: var(--color-accent);
  background-color: var(--color-bg-primary);
}

.form-group select option {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
  padding: 8px;
}

/* ========== Toggle Switch styles (migrated from the App.vue global styles) ========== */
.toggle-wrapper {
  display: flex !important;
  align-items: center !important;
  justify-content: flex-start;
  gap: 16px;
  padding: 16px 20px;
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border: none;
  outline: none;
  border-radius: 0;
  box-shadow: none;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.toggle-wrapper:hover {

  border-color: var(--color-accent);
  outline-color: var(--color-accent-subtle);
}

.toggle-wrapper:active {
  transform: scale(0.98);
}

.toggle-switch {
  position: relative;
  display: block;
  width: 52px;
  height: 30px;
  flex-shrink: 0;
  cursor: pointer;
  margin: 0;
  padding: 0;
  line-height: 0;
}

.toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--color-bg-secondary);

  border: none;
  box-shadow: var(--tile-shadow);
  border-radius: var(--tile-radius-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  /* Outer outline effect */
  outline: none;
  outline-offset: -1px;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 24px;
  width: 24px;
  left: 3px;
  bottom: 3px;
  background-color: var(--color-text-secondary);

  border-radius: 50%;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px var(--color-shadow);
  border: none;
}

.toggle-input:checked + .toggle-slider {
  background: linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-secondary) 100%);
  border-color: var(--color-accent);
  box-shadow: var(--tile-shadow);
  outline-color: var(--color-accent-subtle);
}

.toggle-input:checked + .toggle-slider:before {
  transform: translateX(22px);
  background-color: var(--color-text-primary);
  box-shadow: 0 2px 8px var(--color-shadow);
  border-color: var(--color-accent-subtle);
}

/* Hover state */
.toggle-switch:hover .toggle-slider {

}

.toggle-switch:hover .toggle-slider:before {
  background-color: var(--color-text-primary);
}

/* Active state - physical rebound feedback */
.toggle-switch:active .toggle-slider {
  transform: scale(0.95);
}

.toggle-switch:active .toggle-slider:before {
  transform: translateX(22px) scale(0.95);
}

/* Disabled state */
.toggle-input:disabled + .toggle-slider {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-info {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  gap: 4px;
}

.toggle-label-text {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: -0.01em;
  line-height: 1.4;
  margin: 0;
  padding: 0;
}

.form-help {
  display: block;
  margin: 0;
  padding: 0;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
}

/* ========== SettingsModal-specific styles ========== */
.settings-modal {
  max-width: 640px;
  max-height: 80vh;
  overflow-y: auto;
}

.settings-modal h2 {
  margin: 0 0 24px 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
  letter-spacing: -0.03em;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 10px 14px;
  border-left: 2px solid var(--color-accent);
  border-radius: 10px;
  background: linear-gradient(160deg, rgba(32, 200, 255, 0.10) 0%, transparent 46%),
    var(--color-bg-tertiary);
}

.modal-header h2 {
  margin: 0;
  font-size: 21px;
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
}

.close-btn {
  background: var(--color-bg-tertiary);
  border: 0.5px solid var(--color-border);
  border-radius: var(--tile-radius);
  font-size: 22px;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--color-error-subtle);
  color: var(--color-error);
  transform: rotate(90deg);
}

.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 24px;
}

.danger-btn {
  padding: 10px 20px;
  background: var(--color-error);
  border: 0.5px solid var(--color-border);
  border-radius: var(--tile-radius);
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  width: 100%;
}

.danger-btn:hover:not(:disabled) {
  background: var(--color-error);
  transform: translateY(-1px);
}

.danger-btn:active:not(:disabled) {
  transform: translateY(0);
}

.danger-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.history-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--color-bg-primary);
  border: none;
  border-radius: var(--tile-radius);
}

.history-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.history-stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.history-stat-value {
  font-size: 14px;
  color: var(--color-text-primary);
  font-weight: 600;
  font-family: 'Consolas', 'Microsoft YaHei', monospace;
}

.ghost-btn {
  padding: 10px 20px;
  background: var(--color-bg-tertiary);
  border: 0.5px solid var(--color-border);
  border-radius: var(--tile-radius);
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.ghost-btn:hover {
  background: var(--color-bg-tertiary);
  border-color: var(--color-border-subtle);
  transform: translateY(-1px);
}

.config-sync-section {
  margin-top: 16px;
  padding: 16px;
  background: transparent;
  border-radius: var(--tile-radius);
  border: none;
}

.config-sync-row {
  margin-bottom: 16px;
}

.config-sync-row:last-child {
  margin-bottom: 0;
}

.config-sync-label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.config-sync-section .node-select {
  width: 100%;
  padding: 8px 12px;
  background: var(--color-bg-secondary);
  border: none;
  border-radius: var(--tile-radius);
  color: var(--color-text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.config-sync-section .node-select:hover {
  border-color: var(--color-border-subtle);
}

.config-sync-section .node-select:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: var(--tile-shadow);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-bg-secondary);
  border-radius: var(--tile-radius);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
  color: var(--color-text-primary);
}

.checkbox-label:hover {
  background: var(--color-bg-secondary);
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--color-accent);
}

/* ========== Node display-name mapping styles ========== */
.node-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.node-name-row:last-child {
  margin-bottom: 0;
}

.node-name-origin {
  flex: 0 0 40%;
  font-family: 'Consolas', 'Microsoft YaHei', monospace;
  font-size: 12px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-name-input {
  flex: 1;
  min-width: 0;
}

/* ========== Private key display area styles ========== */
.node-secret-section {
  margin-top: 12px;
  padding: 16px;
  background: transparent;
  border-radius: var(--tile-radius);
  border: none;
}

.secret-display {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 12px;
  background: var(--color-bg-primary);
  border-radius: var(--tile-radius);
  border: none;
}

.secret-code {
  flex: 1;
  font-family: 'Consolas', 'Microsoft YaHei', monospace;
  font-size: 13px;
  color: var(--color-text-primary);
  word-break: break-all;
  min-width: 0;
}

.secret-placeholder {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-secondary);
  font-style: italic;
}

.copy-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  background: var(--color-bg-tertiary);
  border: 0.5px solid var(--color-border);
  border-radius: var(--tile-radius-xs);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.copy-btn:hover:not(:disabled) {
  background: var(--color-bg-secondary);
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.copy-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.secret-actions {
  display: flex;
  gap: 8px;
}

.secret-actions .ghost-btn {
  flex: 1;
  padding: 8px 16px;
  font-size: 13px;
}

/* ========== Restart node service area styles ========== */
.restart-service-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.restart-service-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ========== Config sync button styles ========== */
.config-sync-button {
  margin-top: 16px;
}


</style>
