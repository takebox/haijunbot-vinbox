<template>
  <aside class="plugin-sidebar">
    <div class="plugin-sidebar-header">
      <h3 class="plugin-sidebar-title">Plugin Management</h3>
      <button
        class="plugin-sidebar-refresh"
        tabindex="-1"
        title="Refresh plugin list"
        :disabled="loadingPlugins"
        @click="loadPlugins"
      >⟳</button>
    </div>

    <div class="plugin-sidebar-content">
      <!-- node selection -->
      <div class="plugin-node-select">
        <select v-model="pluginNodeId" class="plugin-node-select-input" @change="loadPlugins">
          <option value="master">This node (master)</option>
          <option v-for="node in availableNodeOptions" :key="node.node_id" :value="node.node_id">
            {{ formatNodeOptionLabel(node) }}
          </option>
        </select>
      </div>

      <!-- install plugin -->
      <div class="plugin-install">
        <div class="plugin-install-title">Install Plugin</div>
        <input
          v-model="installSource"
          class="plugin-install-input"
          placeholder="Source: local path or http(s):// URL"
          @keyup.enter="installPlugin"
        />
        <div class="plugin-install-row">
          <label class="plugin-force-label">
            <input type="checkbox" v-model="installForce" />
            <span>Force overwrite</span>
          </label>
          <button class="plugin-btn plugin-btn-primary" :disabled="installingPlugin || !installSource" @click="installPlugin">
            {{ installingPlugin ? 'Installing...' : 'Install' }}
          </button>
        </div>
      </div>

      <!-- plugin list -->
      <div class="plugin-list">
        <div v-if="loadingPlugins" class="plugin-empty">Loading...</div>
        <div v-else-if="plugins.length === 0" class="plugin-empty">No plugins installed on this node</div>
        <div v-else class="plugin-list-inner">
          <div
            v-for="plugin in plugins"
            :key="plugin.name"
            class="plugin-item"
            @contextmenu.prevent="openCapMenu(plugin, $event)"
          >
            <div class="plugin-item-head">
              <span class="plugin-item-name" :title="plugin.name">{{ plugin.name }}</span>
              <span class="plugin-item-head-right">
                <button
                  v-if="plugin.capabilities && plugin.capabilities.length"
                  class="plugin-btn plugin-btn-sm plugin-cap-btn"
                  @click.stop="openCapModal(plugin)"
                >Capabilities</button>
                <span class="plugin-item-version">
                  {{ plugin.version || '-' }}
                  <span v-if="plugin.builtin" class="plugin-item-badge">Built-in</span>
                </span>
              </span>
            </div>
            <div v-if="plugin.description" class="plugin-item-desc">{{ plugin.description }}</div>
            <div v-if="formatDependencies(plugin.dependencies) !== '-'" class="plugin-item-meta">
              <span class="plugin-item-meta-label">Dependencies</span> {{ formatDependencies(plugin.dependencies) }}
            </div>
            <div class="plugin-item-meta">
              <span class="plugin-item-meta-label">Frontend extension</span> {{ plugin.frontend ? 'Yes' : 'No' }}
            </div>
            <div v-if="!plugin.builtin" class="plugin-item-actions">
              <button class="plugin-btn plugin-btn-sm" :disabled="pluginBusy[plugin.name]" @click="upgradePlugin(plugin)">Upgrade</button>
              <button class="plugin-btn plugin-btn-sm plugin-btn-danger" :disabled="pluginBusy[plugin.name]" @click="uninstallPlugin(plugin)">Uninstall</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- context menu -->
    <div
      v-if="capMenuVisible"
      class="plugin-cap-menu"
      :style="capMenuStyle"
      @click.stop
    >
      <button
        class="plugin-cap-menu-item"
        @click="openCapModal(capMenuPlugin)"
      >Capability Details</button>
    </div>

    <!-- capability details modal -->
    <div v-if="capModalPlugin" class="cap-modal-overlay" @click.self="closeCapModal">
      <div class="cap-modal">
        <div class="cap-modal-header">
          <span class="cap-modal-title">{{ capModalPlugin.name }} · Capability Details</span>
          <button class="cap-modal-close" @click="closeCapModal">✕</button>
        </div>
        <div class="cap-modal-body">
          <div
            v-for="(cap, idx) in capModalPlugin.capabilities"
            :key="idx"
            class="cap-modal-item"
          >
            <span class="cap-modal-name">{{ cap.name }}</span>
            <span v-if="cap.description" class="cap-modal-desc">: {{ cap.description }}</span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>



<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  fetchWithAuth: { type: Function, required: true },
  gatewayUrl: { type: String, default: '127.0.0.1:8000' },
  showToast: { type: Function, default: () => {} },
  getHttpProtocol: { type: Function, default: () => 'http' },
  availableNodeOptions: { type: Array, default: () => [] },
})

// state
const pluginNodeId = ref('master')
const plugins = ref([])
const loadingPlugins = ref(false)

const installingPlugin = ref(false)
const installSource = ref('')
const installForce = ref(false)
const pluginBusy = ref({})

// capability details: context menu + modal
const capMenuVisible = ref(false)
const capMenuStyle = ref({})
const capMenuPlugin = ref(null)
const capModalPlugin = ref(null)

function openCapMenu(plugin, event) {
  if (!plugin.capabilities || !plugin.capabilities.length) return
  capMenuPlugin.value = plugin
  const menuWidth = 140
  const menuHeight = 36
  let left = event.clientX
  let top = event.clientY
  // keep within the bottom-right edge of the viewport
  if (left + menuWidth > window.innerWidth - 8) left = window.innerWidth - menuWidth - 8
  if (left < 8) left = 8
  if (top + menuHeight > window.innerHeight - 8) top = window.innerHeight - menuHeight - 8
  if (top < 8) top = 8
  capMenuStyle.value = { left: left + 'px', top: top + 'px' }
  capMenuVisible.value = true
}

function closeCapMenu() {
  capMenuVisible.value = false
  capMenuPlugin.value = null
}

function openCapModal(plugin) {
  closeCapMenu()
  if (!plugin || !plugin.capabilities || !plugin.capabilities.length) return
  capModalPlugin.value = plugin
}

function closeCapModal() {
  capModalPlugin.value = null
}

function getGatewayAddress() {

  const raw = (props.gatewayUrl || '127.0.0.1:8000').trim()
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

function formatNodeOptionLabel(node) {
  const nodeId = String(node?.node_id || '').trim()
  const status = String(node?.status || node?.runtime_status || '').trim()
  const label = String(node?.label || node?.agent_label || '').trim()
  const isStopped = !status || status === 'stopped' || status === 'stop' || status === 'terminated'
  if (!isStopped && label) return `${nodeId} (${status}) - ${label}`
  return status ? `${nodeId} (${status})` : nodeId
}

function formatDependencies(deps) {
  if (!deps) return '-'
  if (Array.isArray(deps)) return deps.length ? deps.join(', ') : '-'
  if (typeof deps === 'object') {
    const parts = []
    if (deps.plugins) {
      const p = deps.plugins
      if (Array.isArray(p)) parts.push(p.map(x => x.name || x).join(', '))
      else if (typeof p === 'object') parts.push(Object.keys(p).join(', '))
      else parts.push(String(p))
    }
    if (deps.python) {
      const py = deps.python
      if (Array.isArray(py)) parts.push(py.join(', '))
      else if (typeof py === 'object') parts.push(Object.keys(py).join(', '))
      else parts.push(String(py))
    }
    if (deps.commands) {
      const c = deps.commands
      parts.push(Array.isArray(c) ? c.join(', ') : String(c))
    }
    return parts.length ? parts.join('; ') : '-'
  }
  return String(deps)
}

async function loadPlugins() {
  loadingPlugins.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/node/${encodeURIComponent(pluginNodeId.value)}/plugins`))
    const result = await resp.json()
    if (result.success) plugins.value = result.data?.plugins || []
    else props.showToast(result.error?.message || 'Failed to load plugins', 'error')
  } catch (e) { props.showToast('Failed to load plugins: ' + e.message, 'error') }
  finally { loadingPlugins.value = false }
}

async function installPlugin() {
  if (!installSource.value) { props.showToast('Please provide a plugin source', 'warning'); return }
  installingPlugin.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/node/${encodeURIComponent(pluginNodeId.value)}/plugins/install`), {
      method: 'POST',
      body: JSON.stringify({
        source: installSource.value,
        force: installForce.value,
      }),
    })
    const result = await resp.json()
    if (result.success) {
      props.showToast('Plugin installed successfully', 'success')
      installSource.value = ''
      installForce.value = false
      loadPlugins()
    } else props.showToast(result.error?.message || 'Failed to install plugin', 'error')
  } catch (e) { props.showToast('Failed to install plugin: ' + e.message, 'error') }
  finally { installingPlugin.value = false }
}

async function upgradePlugin(plugin) {
  if (!confirm(`Upgrade plugin ${plugin.name}?`)) return
  pluginBusy.value = { ...pluginBusy.value, [plugin.name]: true }
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/node/${encodeURIComponent(pluginNodeId.value)}/plugins/${encodeURIComponent(plugin.name)}/upgrade`), {
      method: 'POST',
      body: JSON.stringify({}),
    })
    const result = await resp.json()
    if (result.success) { props.showToast(`Plugin ${plugin.name} upgraded`, 'success'); loadPlugins() }
    else props.showToast(result.error?.message || 'Failed to upgrade plugin', 'error')
  } catch (e) { props.showToast('Failed to upgrade plugin: ' + e.message, 'error') }
  finally { pluginBusy.value = { ...pluginBusy.value, [plugin.name]: false } }
}

async function uninstallPlugin(plugin) {
  if (!confirm(`Uninstall plugin ${plugin.name}? This cannot be undone.`)) return
  pluginBusy.value = { ...pluginBusy.value, [plugin.name]: true }
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/node/${encodeURIComponent(pluginNodeId.value)}/plugins/${encodeURIComponent(plugin.name)}/uninstall`), {
      method: 'POST',
      body: JSON.stringify({}),
    })
    const result = await resp.json()
    if (result.success) { props.showToast(`Plugin ${plugin.name} uninstalled`, 'success'); loadPlugins() }
    else props.showToast(result.error?.message || 'Failed to uninstall plugin', 'error')
  } catch (e) { props.showToast('Failed to uninstall plugin: ' + e.message, 'error') }
  finally { pluginBusy.value = { ...pluginBusy.value, [plugin.name]: false } }
}

onMounted(() => {
  loadPlugins()
  document.addEventListener('click', closeCapMenu)
  document.addEventListener('keydown', onCapKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', closeCapMenu)
  document.removeEventListener('keydown', onCapKeydown)
})

function onCapKeydown(event) {
  if (event.key === 'Escape') {
    closeCapMenu()
    closeCapModal()
  }
}

defineExpose({ loadPlugins })
</script>

<style scoped>
.plugin-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--bg-secondary, #0b1424);
  color: var(--text-primary, #d6e4f0);
  font-size: 13px;
}
.plugin-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color, #1a2a3a);
  flex-shrink: 0;
}
.plugin-sidebar-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #d6e4f0);
}
.plugin-sidebar-refresh {
  background: none;
  border: none;
  color: var(--text-secondary, #8ba3b8);
  font-size: 15px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.2s;
}
.plugin-sidebar-refresh:hover:not(:disabled) {
  color: var(--accent, #20c8ff);
  background: rgba(32, 200, 255, 0.1);
}
.plugin-sidebar-refresh:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.plugin-sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  min-height: 0;
}
.plugin-node-select {
  margin-bottom: 12px;
}
.plugin-node-select-input {
  width: 100%;
  padding: 7px 10px;
  background: var(--bg-primary, #080c16);
  border: 1px solid var(--border-color, #1a2a3a);
  border-radius: 6px;
  color: var(--text-primary, #d6e4f0);
  font-size: 13px;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s;
}
.plugin-node-select-input:focus {
  border-color: var(--accent, #20c8ff);
}
.plugin-install {
  margin-bottom: 14px;
  padding: 10px;
  background: var(--bg-primary, #080c16);
  border: 1px solid var(--border-color, #1a2a3a);
  border-radius: 6px;
}
.plugin-install-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #8ba3b8);
  margin-bottom: 8px;
}
.plugin-install-input {
  width: 100%;
  padding: 6px 10px;
  background: var(--bg-secondary, #0b1424);
  border: 1px solid var(--border-color, #1a2a3a);
  border-radius: 6px;
  color: var(--text-primary, #d6e4f0);
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.plugin-install-input:focus {
  border-color: var(--accent, #20c8ff);
}
.plugin-install-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
}
.plugin-force-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #8ba3b8);
  cursor: pointer;
  flex-shrink: 0;
}
.plugin-force-label input[type="checkbox"] {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: var(--accent, #20c8ff);
}
.plugin-list {
  min-height: 0;
}
.plugin-empty {
  text-align: center;
  padding: 20px 0;
  color: var(--text-secondary, #888);
  font-size: 12px;
}
.plugin-list-inner {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plugin-item {
  padding: 10px;
  background: var(--bg-primary, #080c16);
  border: 1px solid var(--border-color, #1a2a3a);
  border-radius: 6px;
  transition: border-color 0.2s;
}
.plugin-item:hover {
  border-color: var(--accent, #20c8ff);
}
.plugin-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.plugin-item-name {
  font-weight: 600;
  color: var(--accent, #20c8ff);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plugin-item-head-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
/* capability entry button: hidden by default on desktop (right-click menu opens details);
   on mobile the button is shown instead and opens the capability-detail modal */
.plugin-cap-btn {
  display: none;
}
.plugin-item-version {
  font-size: 12px;
  color: var(--text-secondary, #8ba3b8);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.plugin-item-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(32, 200, 255, 0.12);
  color: var(--accent, #20c8ff);
  border: 1px solid rgba(32, 200, 255, 0.3);
  flex-shrink: 0;
}
/* context menu: capability details entry */
.plugin-cap-menu {
  position: fixed;
  z-index: 10000;
  min-width: 120px;
  background: var(--bg-secondary, #0b1424);
  border: 1px solid var(--border-color, #1a2a3a);
  border-radius: 6px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
  padding: 4px;
}
.plugin-cap-menu-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  border: none;
  background: none;
  color: var(--text-primary, #d6e4f0);
  font-size: 13px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}
.plugin-cap-menu-item:hover {
  background: rgba(32, 200, 255, 0.1);
}
/* capability details modal */
.cap-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3100 !important;
}
.cap-modal {
  background: var(--bg-secondary, #0b1424);
  color: var(--text-primary, #d6e4f0);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  width: 520px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.cap-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color, #1a2a3a);
}
.cap-modal-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent, #20c8ff);
}
.cap-modal-close {
  border: none;
  background: none;
  color: var(--text-secondary, #8ba3b8);
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.cap-modal-close:hover {
  background: rgba(255, 60, 72, 0.1);
  color: var(--color-error, #ff3c48);
}
.cap-modal-body {
  padding: 10px 18px 18px;
  overflow-y: auto;
}
.cap-modal-item {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}
.cap-modal-item:first-child {
  margin-top: 0;
}
.cap-modal-name {
  color: var(--text-primary, #d6e4f0);
  font-weight: 500;
}
.cap-modal-desc {
  color: var(--text-tertiary, #5a6b7d);
}
.plugin-item-desc {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary, #8ba3b8);
  line-height: 1.4;
  word-break: break-word;
}
.plugin-item-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-secondary, #8ba3b8);
  word-break: break-word;
}
.plugin-item-meta-label {
  color: var(--text-tertiary, #5a6b7d);
}
.plugin-item-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.plugin-btn {
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--border-color, #1a2a3a);
  background: none;
  color: var(--text-primary, #d6e4f0);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.plugin-btn:hover:not(:disabled) {
  background: rgba(32, 200, 255, 0.1);
  border-color: var(--accent, #20c8ff);
}
.plugin-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.plugin-btn-primary {
  border-color: var(--accent, #20c8ff);
  color: var(--accent, #20c8ff);
  flex-shrink: 0;
}
.plugin-btn-danger {
  color: var(--color-error, #ff3c48);
  border-color: rgba(255, 60, 72, 0.3);
}
.plugin-btn-danger:hover:not(:disabled) {
  background: rgba(255, 60, 72, 0.1);
}
/* mobile: no hover, the "Capabilities" button opens the inline panel on click and
   the fixed floating context menu is hidden */
@media (max-width: 768px) {
  .plugin-cap-btn {
    display: inline-block;
  }
}
</style>
