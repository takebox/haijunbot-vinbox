<template>
  <div class="modal-overlay" v-if="visible">
    <div class="modal admin-modal">
      <div class="modal-header">
        <h2>System Admin</h2>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="admin-tabs">
        <button class="admin-tab" :class="{ active: activeTab === 'users' }" @click="switchTab('users')">User Management</button>
        <button class="admin-tab" :class="{ active: activeTab === 'groups' }" @click="switchTab('groups')">Permission Groups</button>
        <button class="admin-tab" :class="{ active: activeTab === 'system' }" @click="switchTab('system')">System Config</button>
        <button class="admin-tab" :class="{ active: activeTab === 'config' }" @click="switchTab('config')">Config File</button>
        <button
          v-for="ext in pluginAdminTabs"
          :key="'plugin-tab-' + ext.id"
          class="admin-tab"
          :class="{ active: activeTab === ('plugin-tab:' + ext.id) }"
          @click="switchTab('plugin-tab:' + ext.id)"
        >{{ ext.title }}</button>
      </div>
      <!-- User Management -->
      <div v-if="activeTab === 'users'" class="tab-content">
        <div class="form-group" v-if="showCreateUser">
          <label>Create a new user</label>
          <div class="form-row"><label>Username</label><input v-model="newUserForm.username" placeholder="Enter a username" /></div>
          <div class="form-row"><label>Password</label><input v-model="newUserForm.password" type="password" placeholder="Enter a password" /></div>
          <div class="form-row"><label>Display name</label><input v-model="newUserForm.display_name" placeholder="Enter a display name (optional)" /></div>
          <div class="form-row"><label>Administrator</label><label class="toggle-switch"><input type="checkbox" v-model="newUserForm.is_admin" class="toggle-input" /><span class="toggle-slider"></span></label></div>
          <div class="btn-group"><button class="ghost-btn" @click="createUser" :disabled="loading">Create</button><button class="ghost-btn" @click="showCreateUser = false">Cancel</button></div>
        </div>
        <div class="form-group" v-else><button class="ghost-btn" @click="showCreateUser = true">+ Create user</button></div>
        <div class="form-group">
          <div v-if="loading" style="text-align:center;padding:16px;color:var(--text-secondary,#888)">Loading...</div>
          <div v-else class="table-scroll">
            <table class="admin-table">
              <thead><tr><th>Username</th><th>Display name</th><th>Administrator</th><th>Actions</th></tr></thead>
              <tbody>
                <tr v-for="user in users" :key="user.user_id">
                  <td>{{ user.username }}</td><td>{{ user.display_name || '-' }}</td><td>{{ user.is_admin ? 'Yes' : 'No' }}</td>
                  <td><div class="btn-group"><button class="btn-sm" @click="openEditUser(user)">Edit</button><button class="btn-sm" @click="openGroupAssign(user)">Assign groups</button><button class="btn-sm" @click="openResetPassword(user)">Reset password</button><button class="btn-sm danger" @click="deleteUser(user)" :disabled="user.user_id === currentUserId">Delete</button></div></td>
                </tr>
                <tr v-if="users.length === 0"><td colspan="4" style="text-align:center;color:var(--text-secondary,#888)">No users yet</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <!-- User group assignment -->
        <div class="expand-section" v-if="showGroupAssign && selectedUser">
          <div style="margin-bottom:8px;font-weight:600;font-size:13px">Assign groups - {{ selectedUser.username }}</div>
          <div v-if="loadingGroups" style="color:var(--text-secondary,#888);font-size:13px">Loading...</div>
          <div v-else>
            <div class="group-checkbox" v-for="group in allGroups" :key="group.group_id">
              <input type="checkbox" :value="group.group_id" v-model="userGroupIds" />
              <span>{{ group.display_name || group.name }}</span>
              <span v-if="group.description" style="color:var(--text-secondary,#888);font-size:12px;margin-left:4px">({{ group.description }})</span>
            </div>
            <div class="btn-group" style="margin-top:8px">
              <button class="ghost-btn" @click="saveUserGroups" :disabled="loading">Save</button>
              <button class="ghost-btn" @click="showGroupAssign = false">Cancel</button>
            </div>
          </div>
        </div>
        <!-- Reset password -->
        <div class="expand-section" v-if="showResetPassword && selectedUser">
          <div style="margin-bottom:8px;font-weight:600;font-size:13px">Reset password - {{ selectedUser.username }}</div>
          <div class="form-row"><label>New password</label><input v-model="resetPasswordForm.new_password" type="password" placeholder="Enter a new password" /></div>
          <div class="btn-group">
            <button class="ghost-btn" @click="resetPassword" :disabled="loading">Confirm reset</button>
            <button class="ghost-btn" @click="showResetPassword = false">Cancel</button>
          </div>
        </div>
        <!-- Edit user -->
        <div class="expand-section" v-if="showEditUser && selectedEditUser">
          <div style="margin-bottom:8px;font-weight:600;font-size:13px">Edit user - {{ selectedEditUser.username }}</div>
          <div class="form-row"><label>Display name</label><input v-model="editUserForm.display_name" placeholder="Enter a display name (optional)" /></div>
          <div class="form-row"><label>Administrator</label><label class="toggle-switch"><input type="checkbox" v-model="editUserForm.is_admin" class="toggle-input" /><span class="toggle-slider"></span></label></div>
          <div class="form-row"><label>Status</label><select v-model="editUserForm.status"><option value="active">Active</option><option value="disabled">Disabled</option><option value="locked">Locked</option></select></div>
          <div class="btn-group">
            <button class="ghost-btn" @click="updateUser" :disabled="loading">Save</button>
            <button class="ghost-btn" @click="showEditUser = false">Cancel</button>
          </div>
        </div>
      </div>
      <!-- Permission group management -->
      <div v-if="activeTab === 'groups'" class="tab-content">
        <div class="form-group" v-if="showCreateGroup">
          <label>Create a new permission group</label>
          <div class="form-row"><label>Group name</label><input v-model="newGroupForm.name" placeholder="Enter a group name" /></div>
          <div class="form-row"><label>Description</label><input v-model="newGroupForm.description" placeholder="Enter a description (optional)" /></div>
          <div class="btn-group"><button class="ghost-btn" @click="createGroup" :disabled="loading">Create</button><button class="ghost-btn" @click="showCreateGroup = false">Cancel</button></div>
        </div>
        <div class="form-group" v-else><button class="ghost-btn" @click="showCreateGroup = true">+ Create permission group</button></div>
        <div class="form-group">
          <div v-if="loading" style="text-align:center;padding:16px;color:var(--text-secondary,#888)">Loading...</div>
          <div v-else class="table-scroll">
            <table class="admin-table">
              <thead><tr><th>Group name</th><th>Display name</th><th>Description</th><th>Actions</th></tr></thead>
              <tbody>
                <tr v-for="group in groups" :key="group.group_id">
                  <td>{{ group.name }}</td><td>{{ group.display_name || '-' }}</td><td>{{ group.description || '-' }}</td>
                  <td><div class="btn-group"><button class="btn-sm" @click="openEditGroup(group)">Edit</button><button class="btn-sm danger" @click="deleteGroup(group)">Delete</button></div></td>
                </tr>
                <tr v-if="groups.length === 0"><td colspan="4" style="text-align:center;color:var(--text-secondary,#888)">No permission groups yet</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <!-- Edit group -->
        <div class="expand-section" v-if="showEditGroup && selectedGroup">
          <div style="margin-bottom:8px;font-weight:600;font-size:13px">Edit group - {{ selectedGroup.name }}</div>
          <div class="form-row"><label>Display name</label><input v-model="editGroupForm.display_name" placeholder="Enter a display name" /></div>
          <div class="form-row"><label>Description</label><input v-model="editGroupForm.description" placeholder="Enter a description" /></div>
          <!-- Permission matrix -->
          <div class="permission-matrix">
            <div style="margin-bottom:8px;font-weight:600;font-size:13px">Permission settings</div>
            <div v-if="loadingGroupPerms" style="color:var(--text-secondary,#888);font-size:13px">Loading permissions...</div>
            <div v-else class="table-scroll">
              <table class="perm-table">
                <thead><tr><th>Resource</th><th>Action</th><th>Permission</th></tr></thead>
                <tbody>
                  <template v-for="(actions, resource) in permissionSchema" :key="resource">
                    <tr v-for="(action, idx) in actions" :key="resource + ':' + action">
                      <td v-if="idx === 0" :rowspan="actions.length" class="perm-resource-cell">{{ resourceLabels[resource] || resource }}</td>
                      <td class="perm-action-cell">{{ action }}</td>
                      <td class="perm-value-cell">
                        <select class="perm-select" v-model="editPermissions[resource + ':' + action]">
                          <option value="">None</option>
                          <option value="allow">✓ Allow</option>
                          <option value="deny">✗ Deny</option>
                        </select>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </div>
          <!-- Accessible nodes -->
          <div class="permission-matrix" style="margin-top:12px">
            <div style="margin-bottom:8px;font-weight:600;font-size:13px">Accessible nodes</div>
            <div style="font-size:12px;color:var(--text-secondary,#888);margin-bottom:8px">Empty list = no node permissions, ["*"] = all nodes, a specific node ID = restricted nodes</div>
            <div class="form-row" style="align-items:flex-start">
              <label style="min-width:60px">Node list</label>
              <div style="flex:1;display:flex;flex-direction:column;gap:6px;align-items:flex-start">
                <label class="checkbox-label" style="margin-bottom:0">
                  <input type="checkbox" :checked="editAccessibleNodes.includes('*')" @change="toggleAllNodesAccess" />
                  <span>All nodes ("*")</span>
                </label>
                <template v-if="!editAccessibleNodes.includes('*')">
                  <label v-for="node in availableNodeOptions" :key="node.node_id" class="checkbox-label" style="margin-bottom:0">
                    <input type="checkbox" :checked="editAccessibleNodes.includes(node.node_id)" @change="toggleNodeAccess(node.node_id)" />
                    <span>{{ formatNodeOptionLabel(node) }}</span>
                  </label>
                  <label class="checkbox-label" style="margin-bottom:0">
                    <input type="checkbox" :checked="editAccessibleNodes.includes('master')" @change="toggleNodeAccess('master')" />
                    <span>This node (master)</span>
                  </label>
                  <div v-if="availableNodeOptions.length === 0" style="font-size:12px;color:var(--text-secondary,#888)">No child nodes yet</div>
                </template>
              </div>
            </div>
          </div>
          <div class="btn-group"><button class="ghost-btn" @click="updateGroup" :disabled="loading">Save</button><button class="ghost-btn" @click="showEditGroup = false">Cancel</button></div>
        </div>
      </div>
      <!-- System Config -->
      <div v-if="activeTab === 'system'" class="tab-content">
        <!-- Restart node service -->
        <div class="form-group" v-if="availableNodeOptions.length > 0">
          <label>Restart node service</label>
          <div class="restart-service-section">
            <div class="restart-service-row">
              <select v-model="localRestartNodeId" class="node-select">
                <option value="">This node (master)</option>
                <option v-for="node in availableNodeOptions" :key="node.node_id" :value="node.node_id">
                  {{ formatNodeOptionLabel(node) }}
                </option>
              </select>
              <span class="form-help">Select the node whose service to restart; defaults to the local node</span>
            </div>
            <div class="restart-service-row" v-if="!localRestartNodeId || localRestartNodeId === 'master'">
              <label class="checkbox-label">
                <input type="checkbox" v-model="localRestartFrontendService" />
                <span>Also restart the frontend service</span>
              </label>
              <span class="form-help">Restarting the frontend takes a while; usually only the backend needs restarting</span>
            </div>
            <div class="restart-service-row">
              <button class="ghost-btn" @click="confirmRestartGateway" :disabled="isRestartingGateway">
                {{ isRestartingGateway ? 'Please wait...' : (localRestartNodeId ? `Restart node ${localRestartNodeId} service` : "Restart this node's service") }}
              </button>
              <button class="ghost-btn" @click="confirmRestartAllNodes" :disabled="isRestartingGateway">
                Restart all nodes with one click
              </button>
            </div>
          </div>
        </div>
        <!-- Code update -->
        <div class="form-group">
          <label>Code update</label>
          <span class="form-help">Switch all nodes' HaijunBot code to the main branch and pull the latest code</span>
          <button class="ghost-btn" @click="updateCodeToMain" :disabled="isUpdatingCode">
            {{ isUpdatingCode ? 'Updating...' : 'Update code to the main branch' }}
          </button>
        </div>
        <!-- Node connection private key -->
        <div class="form-group">
          <label>Node connection private key</label>
          <div class="node-secret-section">
            <div class="secret-display">
              <code class="secret-code" v-if="nodeSecret" :title="nodeSecret">{{ maskedNodeSecret }}</code>
              <span class="secret-placeholder" v-else>Click "Get private key" to load</span>
              <button class="copy-btn" @click="copyNodeSecret" :disabled="!nodeSecret" title="Copy private key">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
              </button>
            </div>
            <div class="secret-actions">
              <button class="ghost-btn" @click="fetchNodeSecret" :disabled="isLoadingSecret">
                {{ isLoadingSecret ? 'Loading...' : 'Get private key' }}
              </button>
              <button class="ghost-btn" @click="toggleSecretMask" :disabled="!nodeSecret" title="Show/Hide">
                {{ showSecret ? 'Hide' : 'Show' }}
              </button>
            </div>
            <span class="form-help">This private key authenticates child nodes when connecting to the main gateway; keep it safe</span>
          </div>
        </div>
      </div>
      <!-- Config File -->
      <div v-if="activeTab === 'config'" class="tab-content">
        <!-- Config file editing -->
        <div class="form-group">
          <label>Config file editing</label>
          <div class="form-help" style="margin-bottom:10px">Dynamically generate a form from the JSON Schema to edit the config file (~/.haijunbot/config.yaml), with plain-text preview (requires the admin:config permission).</div>
          <button class="ghost-btn" @click="openConfigEditor">Edit config file</button>
        </div>
        <!-- Config backup and restore -->
        <div class="form-group">
          <label>Config backup and restore</label>
          <div class="form-help" style="margin-bottom:10px">Export a node's config as a JSON backup, or restore from a backup file (requires the admin:config permission; the existing config is backed up automatically before import).</div>
          <div class="config-backup-row">
            <select v-model="backupNodeId" class="node-select">
              <option value="" disabled>Select node</option>
              <option v-for="node in availableNodeOptions" :key="node.node_id" :value="node.node_id">{{ node.node_id }}</option>
            </select>
            <div class="config-backup-actions">
              <button class="ghost-btn" @click="exportConfig" :disabled="!backupNodeId || exporting">
                {{ exporting ? 'Exporting…' : 'Export config' }}
              </button>
              <button class="ghost-btn" @click="triggerImportFile" :disabled="!backupNodeId || importing">
                {{ importing ? 'Importing…' : 'Import config' }}
              </button>
            </div>
            <input ref="importFileEl" type="file" accept=".json,application/json" style="display:none" @change="onImportFileChange" />
          </div>
        </div>
        <!-- Config sync -->
        <div class="form-group" v-if="availableNodeOptions.length > 0">
          <label>Config sync</label>
          <div class="config-sync-section">
            <div class="config-sync-row">
              <span class="config-sync-label">Source node:</span>
              <select v-model="localSyncConfigSourceNode" class="node-select">
                <option value="">This node (master)</option>
                <option v-for="node in availableNodeOptions" :key="node.node_id" :value="node.node_id">
                  {{ formatNodeOptionLabel(node) }}
                </option>
              </select>
            </div>
            <div class="config-sync-button">
              <button class="ghost-btn" @click="syncConfig" :disabled="isSyncingConfig">
                {{ isSyncingConfig ? 'Syncing...' : 'Sync config to other nodes' }}
              </button>
            </div>
          </div>
        </div>
      </div>
      <!-- Dynamic content for plugin-extended admin_tabs (option 2: frontend.admin_tabs in the plugin config.yaml) -->
      <div v-if="isPluginAdminTab(activeTab) && activePluginAdminTabComp" class="tab-content">
        <component
          :is="activePluginAdminTabComp"
          :userInfo="props.auth?.userInfo || null"
          :nodes="props.availableNodeOptions"
          :gatewayUrl="props.gatewayUrl"
          :fetchWithAuth="props.fetchWithAuth"
          :getHttpProtocol="props.getHttpProtocol"
          :showToast="props.showToast"
        />
      </div>
      <!-- Config file editor modal -->
      <ConfigEditorModal
        :visible="showConfigEditor"
        :fetchWithAuth="props.fetchWithAuth"
        :gatewayUrl="props.gatewayUrl"
        :getHttpProtocol="props.getHttpProtocol"
        :showToast="props.showToast"
        :nodeId="backupNodeId || 'master'"
        @update:visible="showConfigEditor = $event"
      />
      <div class="modal-actions">
        <button class="ghost-btn" @click="close">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, defineAsyncComponent } from 'vue'
import ConfigEditorModal from './ConfigEditorModal.vue'
import { loadExtensionComponent } from '../pluginExtensions.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  auth: { type: Object, default: () => ({}) },
  fetchWithAuth: { type: Function, required: true },
  gatewayUrl: { type: String, default: '127.0.0.1:8000' },
  showToast: { type: Function, default: () => {} },
  getHttpProtocol: { type: Function, default: () => 'http' },
  availableNodeOptions: { type: Array, default: () => [] },
  isRestartingGateway: { type: Boolean, default: false },
  isSyncingConfig: { type: Boolean, default: false },
  isUpdatingCode: { type: Boolean, default: false },
  getToken: { type: Function, default: null },
  pluginAdminTabs: { type: Array, default: () => [] },
  pluginExtensions: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:visible', 'confirmRestartGateway', 'confirmRestartAllNodes', 'syncConfig', 'updateCodeToMain', 'confirmUpdateCodeToMain'])

// Status
const activeTab = ref('users')
const users = ref([])
const groups = ref([])
const loading = ref(false)
const loadingGroups = ref(false)
const showCreateUser = ref(false)
const showCreateGroup = ref(false)
const showResetPassword = ref(false)
const showEditGroup = ref(false)
const showGroupAssign = ref(false)
const selectedUser = ref(null)
const selectedGroup = ref(null)
const newUserForm = ref({ username: '', password: '', display_name: '', is_admin: false })
const newGroupForm = ref({ name: '', description: '' })
const resetPasswordForm = ref({ new_password: '' })
const showEditUser = ref(false)
const selectedEditUser = ref(null)
const editUserForm = ref({ display_name: '', is_admin: false, status: 'active' })
const editGroupForm = ref({ group_id: '', display_name: '', description: '' })
const userGroupIds = ref([])
const allGroups = ref([])
const editPermissions = ref({})
const editAccessibleNodes = ref([])
const loadingGroupPerms = ref(false)
const localRestartNodeId = ref('')
const localRestartFrontendService = ref(false)
const localSyncConfigSourceNode = ref('')
const nodeSecret = ref('')
const isLoadingSecret = ref(false)
const showSecret = ref(false)
// Config file related state
const showConfigEditor = ref(false)
const backupNodeId = ref('')
const exporting = ref(false)
const importing = ref(false)
const importFileEl = ref(null)

// Permission schema: resource → action list (loaded dynamically from the backend /api/permissions/schema to avoid hardcoding)
const permissionSchema = ref({})
const resourceLabels = {
  '*': 'All',
  'agent': 'Agent',
  'terminal': 'Terminal',
  'timer': 'Timer',
  'admin': 'Admin',
  'file': 'File',
  'node': 'Node',
}

// Computed properties
const currentUserId = computed(() => props.auth?.userInfo?.user_id || '')
// Helper functions
function getGatewayAddress() {
  const raw = (props.gatewayUrl || '127.0.0.1:8000').trim()
  // Full URL (e.g. wss://hjb-ai.cn) must be parsed with URL to avoid a wrong split(':') result
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

function close() {
  emit('update:visible', false)
}

function switchTab(tab) {
  activeTab.value = tab
  showCreateUser.value = false
  showCreateGroup.value = false
  showResetPassword.value = false
  showEditGroup.value = false
  showGroupAssign.value = false
}

// ---- Plugin-extended admin_tabs (option 2: frontend.admin_tabs in the plugin config.yaml) ----
// Determine whether a tab is a plugin-extended tab (tab name = `plugin-tab:${id}`)
function isPluginAdminTab(tab) {
  return typeof tab === 'string' && tab.startsWith('plugin-tab:')
}
// The async component for the currently active plugin tab (used for <component :is> rendering)
const activePluginAdminTabComp = computed(() => {
  const tab = activeTab.value
  if (!isPluginAdminTab(tab)) return null
  const id = tab.slice('plugin-tab:'.length)
  const ext = props.pluginAdminTabs.find(e => e.id === id)
  if (!ext) return null
  return defineAsyncComponent(() => loadExtensionComponent(ext, {
    fetchWithAuth: props.fetchWithAuth,
    getHttpProtocol: props.getHttpProtocol,
  }))
})

// Called externally (from the command palette): switch to the matching tab and trigger the matching action
function openSystemAction(kind) {
  if (kind === 'config-file' || kind === 'sync-config') {
    switchTab('config')
    if (kind === 'config-file') openConfigEditor()
    else if (kind === 'sync-config') syncConfig()
    return
  }
  switchTab('system')
  if (kind === 'restart') {
    confirmRestartGateway()
  } else if (kind === 'restart-all') {
    confirmRestartAllNodes()
  } else if (kind === 'node-secret') {
    fetchNodeSecret()
  } else if (kind === 'update-code') {
    updateCodeToMain()
  }
}

defineExpose({ openSystemAction })

// Load data when opened
watch(() => props.visible, (val) => {
  if (val) {
    loadUsers()
    loadGroups()
    loadPermissionSchema()
  } else {
    showCreateUser.value = false
    showCreateGroup.value = false
    showResetPassword.value = false
    showEditGroup.value = false
    showGroupAssign.value = false
  }
})

// ===== API calls =====
async function loadUsers() {
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl('/api/users'))
    const result = await resp.json()
    if (result.success) users.value = result.data.users || []
    else props.showToast(result.error?.message || 'Failed to load users', 'error')
  } catch (e) { props.showToast('Failed to load users: ' + e.message, 'error') }
  finally { loading.value = false }
}

async function loadGroups() {
  try {
    const resp = await props.fetchWithAuth(buildApiUrl('/api/permissions/groups'))
    const result = await resp.json()
    if (result.success) groups.value = result.data.groups || []
    else props.showToast(result.error?.message || 'Failed to load permission groups', 'error')
  } catch (e) { props.showToast('Failed to load permission groups: ' + e.message, 'error') }
}

// Load the available permission manifest (resource → actions) dynamically from the backend for the permission matrix, avoiding frontend hardcoding
async function loadPermissionSchema() {
  try {
    const resp = await props.fetchWithAuth(buildApiUrl('/api/permissions/schema'))
    const result = await resp.json()
    if (result.success) permissionSchema.value = result.data.schema || {}
    else props.showToast(result.error?.message || 'Failed to load the permission manifest', 'error')
  } catch (e) { props.showToast('Failed to load the permission manifest: ' + e.message, 'error') }
}

async function createUser() {
  if (!newUserForm.value.username || !newUserForm.value.password) {
    props.showToast('Username and password cannot be empty', 'error'); return
  }
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl('/api/users'), {
      method: 'POST', body: JSON.stringify(newUserForm.value)
    })
    const result = await resp.json()
    if (result.success) {
      props.showToast('User created successfully', 'success')
      newUserForm.value = { username: '', password: '', display_name: '', is_admin: false }
      showCreateUser.value = false
      loadUsers()
    } else props.showToast(result.error?.message || 'Creation failed', 'error')
  } catch (e) { props.showToast('Creation failed: ' + e.message, 'error') }
  finally { loading.value = false }
}

async function deleteUser(user) {
  if (user.user_id === currentUserId.value) { props.showToast('You cannot delete yourself', 'error'); return }
  if (!confirm(`Delete user ${user.username}?`)) return
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/users/${user.user_id}`), { method: 'DELETE' })
    const result = await resp.json()
    if (result.success) { props.showToast('User deleted', 'success'); loadUsers() }
    else props.showToast(result.error?.message || 'Delete failed', 'error')
  } catch (e) { props.showToast('Delete failed: ' + e.message, 'error') }
  finally { loading.value = false }
}

function openEditUser(user) {
  selectedEditUser.value = user
  editUserForm.value = { display_name: user.display_name || '', is_admin: !!user.is_admin, status: user.status || 'active' }
  showEditUser.value = true
  showResetPassword.value = false
  showGroupAssign.value = false
}

async function updateUser() {
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/users/${selectedEditUser.value.user_id}`), {
      method: 'PUT', body: JSON.stringify(editUserForm.value)
    })
    const result = await resp.json()
    if (result.success) { props.showToast('User updated', 'success'); showEditUser.value = false; await loadUsers() }
    else props.showToast(result.error?.message || 'Update failed', 'error')
  } catch (e) { props.showToast('Update failed: ' + e.message, 'error') }
  finally { loading.value = false }
}

function openResetPassword(user) {
  selectedUser.value = user
  resetPasswordForm.value = { new_password: '' }
  showResetPassword.value = true
  showGroupAssign.value = false
  showEditUser.value = false
}

async function resetPassword() {
  if (!resetPasswordForm.value.new_password) { props.showToast('The new password cannot be empty', 'error'); return }
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/users/${selectedUser.value.user_id}/reset-password`), {
      method: 'POST', body: JSON.stringify(resetPasswordForm.value)
    })
    const result = await resp.json()
    if (result.success) { props.showToast('Password reset', 'success'); showResetPassword.value = false }
    else props.showToast(result.error?.message || 'Reset failed', 'error')
  } catch (e) { props.showToast('Reset failed: ' + e.message, 'error') }
  finally { loading.value = false }
}

async function openGroupAssign(user) {
  selectedUser.value = user
  showGroupAssign.value = true
  showResetPassword.value = false
  showEditUser.value = false
  loadingGroups.value = true
  try {
    const [groupsResp, userGroupsResp] = await Promise.all([
      props.fetchWithAuth(buildApiUrl('/api/permissions/groups')),
      props.fetchWithAuth(buildApiUrl(`/api/permissions/user/${user.user_id}/groups`))
    ])
    const groupsResult = await groupsResp.json()
    const userGroupsResult = await userGroupsResp.json()
    if (groupsResult.success) allGroups.value = groupsResult.data.groups || []
    if (userGroupsResult.success) userGroupIds.value = (userGroupsResult.data.groups || []).map(g => g.group_id)
  } catch (e) { props.showToast('Failed to load group information', 'error') }
  finally { loadingGroups.value = false }
}

async function saveUserGroups() {
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/permissions/user/${selectedUser.value.user_id}/groups`), {
      method: 'PUT', body: JSON.stringify({ group_ids: userGroupIds.value })
    })
    const result = await resp.json()
    if (result.success) { props.showToast('Group assignment saved', 'success'); showGroupAssign.value = false }
    else props.showToast(result.error?.message || 'Save failed', 'error')
  } catch (e) { props.showToast('Save failed: ' + e.message, 'error') }
  finally { loading.value = false }
}

async function createGroup() {
  if (!newGroupForm.value.name) { props.showToast('Group name cannot be empty', 'error'); return }
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl('/api/permissions/groups'), {
      method: 'POST', body: JSON.stringify(newGroupForm.value)
    })
    const result = await resp.json()
    if (result.success) {
      props.showToast('Permission group created successfully', 'success')
      newGroupForm.value = { name: '', description: '' }
      showCreateGroup.value = false; loadGroups()
    } else props.showToast(result.error?.message || 'Creation failed', 'error')
  } catch (e) { props.showToast('Creation failed: ' + e.message, 'error') }
  finally { loading.value = false }
}

async function openEditGroup(group) {
  selectedGroup.value = group
  editGroupForm.value = { group_id: group.group_id, display_name: group.display_name || '', description: group.description || '' }
  showEditGroup.value = true
  // Load group permissions
  loadingGroupPerms.value = true
  editPermissions.value = {}
  editAccessibleNodes.value = []
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/permissions/groups/${group.group_id}/permissions`))
    const result = await resp.json()
    if (result.success) {
      // Convert the permissions object into a flat key→value map
      const perms = result.data.permissions || {}
      const accessibleNodes = perms.accessible_nodes || []
      const flat = {}
      for (const [key, val] of Object.entries(perms)) {
        if (key !== 'accessible_nodes') flat[key] = val
      }
      editPermissions.value = flat
      editAccessibleNodes.value = Array.isArray(accessibleNodes) ? [...accessibleNodes] : []
    }
  } catch (e) { props.showToast('Failed to load permissions', 'error') }
  finally { loadingGroupPerms.value = false }
}

async function updateGroup() {
  loading.value = true
  try {
    const { group_id, ...updateData } = editGroupForm.value
    // Update the group's basic information
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/permissions/groups/${group_id}`), {
      method: 'PUT', body: JSON.stringify(updateData)
    })
    const result = await resp.json()
    if (!result.success) { props.showToast(result.error?.message || 'Update failed', 'error'); return }
    // Save permissions (filtering out empty values)
    const perms = {}
    for (const [key, val] of Object.entries(editPermissions.value)) {
      if (val) perms[key] = val
    }
    perms.accessible_nodes = editAccessibleNodes.value
    const permResp = await props.fetchWithAuth(buildApiUrl(`/api/permissions/groups/${group_id}/permissions`), {
      method: 'PUT', body: JSON.stringify({ permissions: perms })
    })
    const permResult = await permResp.json()
    if (permResult.success) { props.showToast('Permission group updated', 'success'); showEditGroup.value = false; loadGroups() }
    else props.showToast(permResult.error?.message || 'Permission update failed', 'error')
  } catch (e) { props.showToast('Update failed: ' + e.message, 'error') }
  finally { loading.value = false }
}

async function deleteGroup(group) {
  if (!confirm(`Delete permission group ${group.name}?`)) return
  loading.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/permissions/groups/${group.group_id}`), { method: 'DELETE' })
    const result = await resp.json()
    if (result.success) { props.showToast('Permission group deleted', 'success'); loadGroups() }
    else props.showToast(result.error?.message || 'Delete failed', 'error')
  } catch (e) { props.showToast('Delete failed: ' + e.message, 'error') }
  finally { loading.value = false }
}

// ===== System config features =====

function formatNodeOptionLabel(node) {
  const nodeId = String(node?.node_id || '').trim()
  const status = String(node?.status || node?.runtime_status || '').trim()
  const label = String(node?.label || node?.agent_label || '').trim()
  const isStopped = !status || status === 'stopped' || status === 'stop' || status === 'terminated'
  if (!isStopped && label) return `${nodeId} (${status}) - ${label}`
  return status ? `${nodeId} (${status})` : nodeId
}

function toggleAllNodesAccess() {
  if (editAccessibleNodes.value.includes('*')) {
    editAccessibleNodes.value = []
  } else {
    editAccessibleNodes.value = ['*']
  }
}

function toggleNodeAccess(nodeId) {
  const idx = editAccessibleNodes.value.indexOf(nodeId)
  if (idx >= 0) {
    editAccessibleNodes.value.splice(idx, 1)
  } else {
    editAccessibleNodes.value.push(nodeId)
  }
}

function confirmRestartGateway() {
  emit('confirmRestartGateway', { nodeId: localRestartNodeId.value, restartFrontend: localRestartFrontendService.value })
}

function confirmRestartAllNodes() {
  emit('confirmRestartAllNodes')
}

function syncConfig() {
  emit('syncConfig', { sourceNodeId: localSyncConfigSourceNode.value })
}

function updateCodeToMain() {
  emit('confirmUpdateCodeToMain')
}

async function fetchNodeSecret() {
  if (isLoadingSecret.value) return
  isLoadingSecret.value = true
  try {
    const token = props.getToken ? props.getToken() : null
    if (!token) { props.showToast('Please sign in first', 'error'); return }
    const response = await props.fetchWithAuth(buildApiUrl('/api/node/secret'))
    const result = await response.json()
    if (response.ok && result.success && result.data?.node_secret) {
      nodeSecret.value = result.data.node_secret
    } else {
      props.showToast(result.error?.message || result.detail?.message || 'Failed to get the private key', 'error')
    }
  } catch (error) {
    props.showToast('Failed to get the private key: ' + error.message, 'error')
  } finally {
    isLoadingSecret.value = false
  }
}

function toggleSecretMask() {
  showSecret.value = !showSecret.value
}

// ===== Config file features =====
function openConfigEditor() {
  showConfigEditor.value = true
}
// Export config: pull the config from the selected node and download it as a JSON file
async function exportConfig() {
  if (!backupNodeId.value) { props.showToast('Please select a node first', 'warning'); return }
  exporting.value = true
  try {
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/nodes/${backupNodeId.value}/config`), { method: 'GET' })
    const result = await resp.json()
    if (!resp.ok || !result.success) {
      throw new Error(result.error?.message || 'Failed to get the config')
    }
    const config = result.data?.config || {}
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `haijunbot-config-${backupNodeId.value}-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    props.showToast(`Exported ${Object.keys(config).length} config item(s)`, 'success')
  } catch (e) {
    props.showToast('Export failed: ' + (e.message || 'Unknown error'), 'error')
  } finally {
    exporting.value = false
  }
}
// Trigger file selection
function triggerImportFile() {
  if (!backupNodeId.value) { props.showToast('Please select a node first', 'warning'); return }
  importFileEl.value?.click()
}
// Read the imported file and apply it to the selected node
async function onImportFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = '' // allow selecting the same file again
  if (!file) return
  try {
    const text = await file.text()
    const parsed = JSON.parse(text) // validate the JSON format
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new Error('The config file must be a JSON object')
    }
    if (!backupNodeId.value) { props.showToast('Please select a node first', 'warning'); return }
    importing.value = true
    const sections = Object.keys(parsed)
    if (sections.length === 0) { props.showToast('There is no importable content in the config file', 'warning'); return }
    const resp = await props.fetchWithAuth(buildApiUrl(`/api/nodes/${backupNodeId.value}/config`), {
      method: 'POST',
      body: JSON.stringify({ config_sections: sections, config_data: parsed }),
    })
    const result = await resp.json()
    if (!resp.ok || !result.success) {
      throw new Error(result.error?.message || 'Failed to import the config')
    }
    props.showToast(`Imported ${sections.length} config item(s) to ${backupNodeId.value}`, 'success')
  } catch (e) {
    props.showToast('Import failed: ' + (e.message || 'Unknown error'), 'error')
  } finally {
    importing.value = false
  }
}

async function copyNodeSecret() {
  if (!nodeSecret.value) { props.showToast('The private key is empty', 'error'); return }
  try {
    await navigator.clipboard.writeText(nodeSecret.value)
    props.showToast('Copied to clipboard', 'success')
  } catch (error) {
    try {
      const textArea = document.createElement('textarea')
      textArea.value = nodeSecret.value
      textArea.style.position = 'fixed'
      textArea.style.opacity = '0'
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      props.showToast('Copied to clipboard', 'success')
    } catch (fallbackErr) {
      props.showToast('Copy failed; please copy manually', 'error')
    }
  }
}

const maskedNodeSecret = computed(() => {
  if (!nodeSecret.value) return ''
  if (showSecret.value) return nodeSecret.value
  const secret = nodeSecret.value
  if (secret.length <= 16) return '*'.repeat(secret.length)
  return `${secret.slice(0, 8)}${'*'.repeat(secret.length - 16)}${secret.slice(-8)}`
})


</script>

<style scoped>
/* Modal - reuses the App.vue style */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;
  z-index: 3000;
}
.admin-modal {
  background: rgba(9, 16, 28, 0.86); color: var(--text-primary, #d6e4f0);
  border: 1px solid rgba(32, 200, 255, 0.15);
  border-radius: 14px; width: 80%; max-width: 1200px; max-height: 90vh;
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(32, 200, 255, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px; border-bottom: 1px solid var(--border-color, #1a2a3a);
  border-left: 2px solid var(--accent, #20c8ff);
  background: linear-gradient(160deg, rgba(32, 200, 255, 0.10) 0%, transparent 46%),
    var(--color-bg-tertiary, rgba(18, 30, 50, 0.65));
}
.modal-header h2 { margin: 0; font-size: 18px; }
.close-btn {
  background: none; border: none; color: var(--text-secondary, #8ba3b8);
  font-size: 20px; cursor: pointer; padding: 4px 8px; border-radius: 4px;
  transition: all 0.2s;
}
.close-btn:hover { color: var(--text-primary, #d6e4f0); background: rgba(32,200,255,0.1); }

/* Tab navigation */
.admin-tabs {
  display: flex; border-bottom: 1px solid var(--border-color, #1a2a3a);
  padding: 0 24px;
}
.admin-tab {
  padding: 10px 20px; cursor: pointer; border: none; background: none;
  color: var(--text-secondary, #8ba3b8); font-size: 14px;
  border-bottom: 2px solid transparent; transition: all 0.2s;
  border-radius: 8px 8px 0 0;
}
.admin-tab:hover {
  color: var(--text-primary, #d6e4f0);
  background: rgba(32, 200, 255, 0.08);
}
.admin-tab.active {
  color: var(--accent, #20c8ff);
  border-bottom-color: var(--accent, #20c8ff);
  background: linear-gradient(180deg, rgba(32, 200, 255, 0.14) 0%, transparent 100%);
  text-shadow: 0 0 10px rgba(32, 200, 255, 0.5);
}

/* Tab content area */
.tab-content {
  flex: 1; overflow-y: auto; padding: 20px 24px;
}

/* Form group */
.form-group {
  margin-bottom: 16px;
}
.form-group > label:first-child {
  display: block; font-size: 13px; font-weight: 600;
  color: var(--text-secondary, #8ba3b8); margin-bottom: 8px;
}
.form-row {
  display: flex; gap: 12px; margin-bottom: 10px; align-items: center;
}
.form-row > label {
  font-size: 13px; color: var(--text-secondary, #8ba3b8); min-width: 60px; flex-shrink: 0;
}
.form-row input {
  flex: 1; padding: 6px 10px; border-radius: 6px;
  border: 1px solid var(--border-color, #1a2a3a);
  background: var(--bg-primary, #080c16); color: var(--text-primary, #d6e4f0);
  font-size: 13px; outline: none; transition: border-color 0.2s;
}
.form-row input:focus { border-color: var(--accent, #20c8ff); }

/* Button group */
.btn-group { display: flex; gap: 8px; margin-top: 8px; }
.ghost-btn {
  padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border-color, #1a2a3a);
  background: none; color: var(--text-primary, #d6e4f0); font-size: 13px;
  cursor: pointer; transition: all 0.2s;
}
.ghost-btn:hover { background: rgba(32,200,255,0.1); border-color: var(--accent, #20c8ff); }
.ghost-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm {
  padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border-color, #1a2a3a);
  background: none; color: var(--text-primary, #d6e4f0); font-size: 12px;
  cursor: pointer; transition: all 0.2s;
}
.btn-sm:hover { background: rgba(32,200,255,0.1); }
.btn-sm.danger { color: var(--color-error, #ff3c48); border-color: rgba(255,60,72,0.3); }
.btn-sm.danger:hover { background: rgba(255,60,72,0.1); }

/* Table scroll container (horizontal scroll on narrow screens to avoid table overflow) */
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

/* table */
.admin-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}
.admin-table th {
  text-align: left; padding: 8px 12px; border-bottom: 1px solid rgba(32, 200, 255, 0.25);
  color: var(--accent, #20c8ff); font-weight: 600;
  letter-spacing: 0.02em;
}
.admin-table td {
  padding: 8px 12px; border-bottom: 1px solid rgba(26, 42, 58, 0.3);
}
.admin-table tr {
  transition: background 0.2s ease;
}
.admin-table tr:hover {
  background: rgba(32, 200, 255, 0.08);
  box-shadow: inset 2px 0 0 var(--accent, #20c8ff);
}

/* Expandable area */
.expand-section {
  background: var(--bg-primary, #080c16); border-radius: 8px; padding: 16px; margin-top: 16px;
  border: 1px solid var(--border-color, #1a2a3a);
}

/* Group checkboxes */
.group-checkbox {
  display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px;
}
.group-checkbox input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }

/* toggle switch */
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
.toggle-switch:hover .toggle-slider:before {
  background-color: var(--color-text-primary);
}

/* Active state - physical bounce feedback */
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

/* Permission matrix */
.permission-matrix {
  margin-top: 16px; padding-top: 12px;
  border-top: 1px solid var(--border-color, #1a2a3a);
}
.perm-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}
.perm-table th {
  text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border-color, #1a2a3a);
  color: var(--text-secondary, #8ba3b8); font-weight: 500; font-size: 12px;
}
.perm-table td {
  padding: 4px 10px; border-bottom: 1px solid rgba(26,42,58,0.2);
}
.perm-resource-cell {
  font-weight: 600; color: var(--accent, #20c8ff); vertical-align: middle;
  border-right: 1px solid var(--border-color, #1a2a3a);
}
.perm-action-cell {
  color: var(--text-secondary, #8ba3b8);
}
.perm-value-cell {
  text-align: center;
}
.perm-select {
  padding: 2px 6px; border-radius: 4px; font-size: 12px;
  border: 1px solid var(--border-color, #1a2a3a);
  background: var(--bg-primary, #080c16); color: var(--text-primary, #d6e4f0);
  cursor: pointer; outline: none;
}
.perm-select:focus { border-color: var(--accent, #20c8ff); }
.perm-select option[value="allow"] { color: var(--color-success, #36ff7c); }
.perm-select option[value="deny"] { color: var(--color-error, #ff3c48); }

/* Modal action area */
.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 24px;
}

/* Help text */
.form-help {
  display: block;
  margin: 0;
  padding: 0;
  font-size: 12px;
  color: var(--text-secondary, #8ba3b8);
  line-height: 1.4;
}

/* Config sync area */
.config-sync-section {
  margin-top: 16px;
  padding: 16px;
  background: transparent;
  border-radius: 6px;
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
  color: var(--text-primary, #d6e4f0);
}
.config-sync-section .node-select {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-secondary, #0b1424);
  border: none;
  border-radius: 6px;
  color: var(--text-primary, #d6e4f0);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.config-sync-section .node-select:hover {
  border-color: var(--border-color, #1a2a3a);
}
.config-sync-section .node-select:focus {
  outline: none;
  border-color: var(--accent, #20c8ff);
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.config-sync-button {
  margin-top: 16px;
}

/* Checkbox label */
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary, #0b1424);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
  color: var(--text-primary, #d6e4f0);
}
.checkbox-label:hover {
  background: var(--bg-secondary, #0b1424);
}
.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--accent, #20c8ff);
}

/* Private key display area */
.node-secret-section {
  margin-top: 12px;
  padding: 16px;
  background: transparent;
  border-radius: 6px;
  border: none;
}
.secret-display {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 12px;
  background: var(--bg-primary, #080c16);
  border-radius: 6px;
  border: none;
}
.secret-code {
  flex: 1;
  font-family: 'Consolas', 'Microsoft YaHei', monospace;
  font-size: 13px;
  color: var(--text-primary, #d6e4f0);
  word-break: break-all;
  min-width: 0;
}
.secret-placeholder {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary, #8ba3b8);
  font-style: italic;
}
.copy-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  background: var(--bg-tertiary, #16263a);
  border: 0.5px solid var(--border-color, #1a2a3a);
  border-radius: 4px;
  color: var(--text-secondary, #8ba3b8);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}
.copy-btn:hover:not(:disabled) {
  background: var(--bg-secondary, #0b1424);
  color: var(--accent, #20c8ff);
  border-color: var(--accent, #20c8ff);
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
  padding: 8px 16px;
  font-size: 13px;
}

/* Restart node service area */
.restart-service-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.restart-service-row {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 8px;
}

/* Node selector (restart area) */
.restart-service-section .node-select {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-secondary, #0b1424);
  border: none;
  border-radius: 6px;
  color: var(--text-primary, #d6e4f0);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.restart-service-section .node-select:hover {
  border-color: var(--border-color, #1a2a3a);
}
.restart-service-section .node-select:focus {
  outline: none;
  border-color: var(--accent, #20c8ff);
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

/* Config backup and restore */
.config-backup-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.config-backup-row .node-select {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-secondary, #0b1424);
  border: none;
  border-radius: 6px;
  color: var(--text-primary, #d6e4f0);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.config-backup-row .node-select:focus {
  outline: none;
  border-color: var(--accent, #20c8ff);
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.config-backup-actions {
  display: flex;
  gap: 8px;
}
.config-backup-actions .ghost-btn {
  flex: 1;
  text-align: center;
}
.config-backup-actions .ghost-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}



/* ==================== Mobile adaptation (< 768px) ==================== */
@media (max-width: 768px) {
  /* The modal fills the screen to make full use of narrow-screen space */
  .admin-modal {
    width: 100%;
    max-width: none;
    height: 100vh;
    max-height: 100vh;
    border-radius: 0;
  }

  .modal-header {
    padding: 12px 16px;
  }

  .modal-header h2 {
    font-size: 16px;
  }

  /* Tab navigation: allow horizontal scrolling to avoid squeezing onto new lines */
  .admin-tabs {
    padding: 0 8px;
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
  }

  .admin-tab {
    padding: 10px 14px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .tab-content {
    padding: 14px 12px;
  }

  /* Form rows: stack vertically, label above and input below */
  .form-row {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
  }

  .form-row > label {
    min-width: 0;
  }

  /* Button group: allow wrapping to avoid button overflow */
  .btn-group {
    flex-wrap: wrap;
  }

  /* Action buttons: enlarge the touch area */
  .btn-sm,
  .ghost-btn {
    min-height: 36px;
  }

  /* Table cells: compress padding */
  .admin-table th,
  .admin-table td {
    padding: 8px 10px;
  }

  /* Restart service area: buttons fill the full row */
  .restart-service-row {
    flex-direction: column;
    align-items: stretch;
  }

  .restart-service-row .ghost-btn {
    width: 100%;
  }

  .secret-actions {
    flex-wrap: wrap;
  }

  .secret-actions .ghost-btn {
    flex: 1;
    text-align: center;
  }

  .config-backup-actions {
    flex-wrap: wrap;
  }
}
</style>