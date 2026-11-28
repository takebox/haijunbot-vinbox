<template>
  <aside
    class="agent-sidebar"
    :class="{ collapsed: !visible, 'agent-sidebar-resizing': resizeState.active }"
    :style="sidebarStyle"
  >
    <div class="agent-sidebar-header">
      <h3>Agent List</h3>
      <div class="sidebar-header-actions">
        <button class="icon-btn" tabindex="-1" :class="{ active: isBatchMode }" @mousedown.prevent @click="$emit('toggleBatchMode')" title="Batch selection mode" v-html="BTN_ICONS.check"></button>
        <button class="icon-btn" tabindex="-1" @mousedown.prevent @click="openManageGroups" title="Manage Groups" v-html="BTN_ICONS.folder"></button>
        <button class="icon-btn" tabindex="-1" @mousedown.prevent @click="$emit('orchestrate')" title="Orchestrate: batch-create Agents from an orchestration file" v-html="BTN_ICONS.puzzle"></button>
        <button class="icon-btn" tabindex="-1" @mousedown.prevent @click="$emit('createAgent')" title="Create New Agent" v-html="BTN_ICONS.plus"></button>
        <button v-if="!embedded" class="icon-btn" tabindex="-1" @mousedown.prevent @click="$emit('close')" title="Close sidebar">✕</button>
      </div>
    </div>
    <div class="agent-list">
      <!-- Welcome banner: not shown on mobile (limited screen space, takes up too much room) -->
      <div v-if="windowWidth > 768" class="hello-user-banner" aria-hidden="true">
        <span class="hello-user-glow">Hello, {{ currentUserName || '' }}</span>
        <span class="hello-user-sub">✦ Hello, {{ currentUserName || '' }} ✦</span>
      </div>
      <template v-for="agentGroup in displayGroups" :key="agentGroup.key">
        <div v-if="agentGroup.isCollapsible && agentGroup.agents.length > 0" class="agent-collapsed-section">
          <button
            class="agent-collapsed-toggle"
            :class="{
              'group-waiting-unread': hasUnreadWaitingAgent(agentGroup.agents),
              'group-waiting-clicked': hasClickedWaitingAgent(agentGroup.agents)
            }"
            @click="toggleGroupCollapse(agentGroup.key)"
          >
            <span class="agent-collapsed-arrow">{{ isGroupCollapsed(agentGroup.key) ? '▶' : '▼' }}</span>
            <span class="agent-collapsed-title">{{ agentGroup.title }}</span>
            <span class="agent-collapsed-count">({{ agentGroup.agents.filter(a => getStatusClass(a) !== 'stopped').length }}/{{ agentGroup.agents.length }})</span>
          </button>
          <div v-if="!isGroupCollapsed(agentGroup.key)">
            <div
              v-for="agent in agentGroup.agents"
              :key="agent.agent_id"
              class="agent-item"
              :class="{ active: currentAgentId === agent.agent_id, selected: isSelected(agent.agent_id), 'waiting-input': isWaitingInput(agent), 'waiting-input-unread': isWaitingInput(agent) && !clickedWaitingAgents.has(agent.agent_id) }"
              @click="handleAgentClick(agent, $event)"
              @contextmenu.prevent="handleAgentContextMenu(agent, $event)"
            >
              <div v-if="isBatchMode" class="agent-checkbox" @click.stop>
                <input type="checkbox" :checked="isSelected(agent.agent_id)" @change="$emit('toggleSelectAgent', agent.agent_id)">
              </div>
              <div class="agent-info">
                <span class="agent-type-icon" :title="agent.agent_type">
                  <svg v-if="agent.agent_type === 'code_agent'" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M5.5 4.5 2.5 8l3 3.5M10.5 4.5l3 3.5-3 3.5"/>
                    <path d="M9.5 3.5l-3 9"/>
                  </svg>
                  <svg v-else viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <rect x="3" y="5" width="10" height="7" rx="2"/>
                    <circle cx="5.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                    <circle cx="10.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                    <path d="M6 3.5 8 5l2-1.5"/>
                    <path d="M5 12v1.5M11 12v1.5"/>
                    <path d="M3 10H1.5M14.5 10H13"/>
                  </svg>
                </span>
                <span class="agent-name">{{ agent.name }}</span>
                <span class="agent-status-dot" :class="getStatusClass(agent)" :title="getStatusText(agent)"></span>
              </div>
              <div class="agent-dir-line">
                <span class="agent-dir" :title="workingDirDisplay(agent)">{{ workingDirDisplay(agent) }}</span>
                <span class="agent-meta-tag"><span class="meta-icon" v-html="SIDEBAR_ICONS.location"></span> {{ nodeDisplayLabel(agent) }}</span>
                <span class="agent-meta-tag" v-if="agent.proxy_node"><span class="meta-icon" v-html="SIDEBAR_ICONS.proxy"></span> {{ getProxyNodeLabel(agent) }}</span>
                <span class="agent-meta-tag" v-if="agent.llm_group"><span class="meta-icon" v-html="SIDEBAR_ICONS.llm"></span> {{ agent.llm_group }}</span>
                <span class="agent-meta-tag" v-if="agent.worktree"><span class="meta-icon" v-html="SIDEBAR_ICONS.worktree"></span></span>
                <span class="agent-meta-tag" v-if="agent.quick_mode"><span class="meta-icon" v-html="SIDEBAR_ICONS.quick"></span></span>
              </div>
              <!-- List item action buttons (rename/copy/permissions/respawn/delete) have moved to the Ctrl+P command palette and are no longer shown here -->
            </div>
          </div>
        </div>
        <template v-else>
          <div
            v-for="agent in agentGroup.agents"
            :key="agent.agent_id"
            class="agent-item"
            :class="{ active: currentAgentId === agent.agent_id, selected: isSelected(agent.agent_id), 'waiting-input': isWaitingInput(agent), 'waiting-input-unread': isWaitingInput(agent) && !clickedWaitingAgents.has(agent.agent_id) }"
            @click="handleAgentClick(agent, $event)"
            @contextmenu.prevent="handleAgentContextMenu(agent, $event)"
          >
            <div v-if="isBatchMode" class="agent-checkbox" @click.stop>
              <input type="checkbox" :checked="isSelected(agent.agent_id)" @change="$emit('toggleSelectAgent', agent.agent_id)">
            </div>
            <div class="agent-info">
              <span class="agent-type-icon" :title="agent.agent_type">
                <svg v-if="agent.agent_type === 'code_agent'" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M5.5 4.5 2.5 8l3 3.5M10.5 4.5l3 3.5-3 3.5"/>
                  <path d="M9.5 3.5l-3 9"/>
                </svg>
                <svg v-else viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="3" y="5" width="10" height="7" rx="2"/>
                  <circle cx="5.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                  <circle cx="10.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                  <path d="M6 3.5 8 5l2-1.5"/>
                  <path d="M5 12v1.5M11 12v1.5"/>
                  <path d="M3 10H1.5M14.5 10H13"/>
                </svg>
              </span>
              <span class="agent-name">{{ agent.name }}</span>
              <span class="agent-status-dot" :class="getStatusClass(agent)" :title="getStatusText(agent)"></span>
            </div>
            <div class="agent-dir-line">
              <span class="agent-dir" :title="workingDirDisplay(agent)">{{ workingDirDisplay(agent) }}</span>
              <span class="agent-meta-tag"><span class="meta-icon" v-html="SIDEBAR_ICONS.location"></span> {{ nodeDisplayLabel(agent) }}</span>
              <span class="agent-meta-tag" v-if="agent.proxy_node"><span class="meta-icon" v-html="SIDEBAR_ICONS.proxy"></span> {{ getProxyNodeLabel(agent) }}</span>
              <span class="agent-meta-tag" v-if="agent.llm_group"><span class="meta-icon" v-html="SIDEBAR_ICONS.llm"></span> {{ agent.llm_group }}</span>
              <span class="agent-meta-tag" v-if="agent.worktree"><span class="meta-icon" v-html="SIDEBAR_ICONS.worktree"></span></span>
              <span class="agent-meta-tag" v-if="agent.quick_mode"><span class="meta-icon" v-html="SIDEBAR_ICONS.quick"></span></span>
            </div>
             <!-- List item action buttons (rename/copy/permissions/respawn/delete) have moved to the Ctrl+P command palette and are no longer shown here -->
          </div>
        </template>
      </template>
      <!-- Batch action button bar -->
      <div v-if="isBatchMode && agentList.length > 0" class="batch-actions-bar">
        <div class="batch-actions-info">
          {{ selectedCount }} selected
        </div>
        <div class="batch-actions-buttons">
          <button class="icon-btn-small" @click="$emit('toggleSelectAll')" :title="isAllSelected ? 'Deselect all' : 'Select all'" v-html="isAllSelected ? BTN_ICONS.unchecked : BTN_ICONS.check"></button>
          <button class="icon-btn-small" @click="$emit('batchCopy')" title="Batch copy" v-html="BTN_ICONS.copy"></button>
          <button class="icon-btn-small" @click="openGroupModal" title="Add to group" v-html="BTN_ICONS.folder"></button>
          <button class="icon-btn-small stop-btn" @click="$emit('batchDelete')" title="Batch delete" v-html="BTN_ICONS.trash"></button>
          <button class="icon-btn-small" @click="$emit('toggleBatchMode')" title="Exit batch mode">
            ✕
          </button>
        </div>
      </div>
      <div v-if="agentList.length === 0" class="agent-empty">
        No Agents yet, click + to create
      </div>
    </div>
    <div
      v-if="visible && windowWidth > 768 && !embedded"
      class="agent-sidebar-resize-handle"
      @mousedown="$emit('startResize', $event)"
    ></div>
  </aside>


  <!-- Add-to-group modal -->
  <Teleport to="body">
    <div v-if="showGroupModal" class="group-modal-overlay" @click.self="closeGroupModal">
      <div class="group-modal">
        <div class="group-modal-header">
          <span>Add to Group</span>
          <button class="icon-btn-small" @click="closeGroupModal" title="Close">✕</button>
        </div>
        <div v-if="agentGroups.length === 0" class="agent-group-empty">No groups yet, please create one first</div>
        <div
          v-for="group in agentGroups"
          :key="group.id"
          class="agent-group-item"
          @click="selectGroup(group.id)"
        >
          <span class="agent-group-item-name"><span class="meta-icon" v-html="BTN_ICONS.folder"></span> {{ group.name }}</span>
          <span class="agent-group-item-count">({{ group.agentIds?.length || 0 }})</span>
        </div>
        <div class="agent-group-create">
          <input
            v-model="newGroupName"
            class="agent-group-create-input"
            placeholder="New group name"
            @keyup.enter="handleCreateGroup"
          />
          <button class="icon-btn-small" @click="handleCreateGroup" title="Create group">➕</button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Manage groups modal: rename / delete (decoupled from "Add to group") -->
  <Teleport to="body">
    <div v-if="showManageGroupsModal" class="group-modal-overlay" @click.self="closeManageGroups">
      <div class="group-modal">
        <div class="group-modal-header">
          <span>Manage Groups</span>
          <button class="icon-btn-small" @click="closeManageGroups" title="Close">✕</button>
        </div>
        <div v-if="agentGroups.length === 0" class="agent-group-empty">No groups yet</div>
        <div
          v-for="group in agentGroups"
          :key="group.id"
          class="agent-group-item"
        >
          <input
            v-if="editingGroupId === group.id"
            ref="groupRenameInputRef"
            v-model="editingGroupName"
            class="agent-group-rename-input"
            @click.stop
            @keyup.enter="confirmRenameGroup"
            @keyup.esc="cancelRenameGroup"
            @blur="confirmRenameGroup"
          />
          <template v-else>
            <span class="agent-group-item-name"><span class="meta-icon" v-html="BTN_ICONS.folder"></span> {{ group.name }}</span>
            <span class="agent-group-item-count">({{ group.agentIds?.length || 0 }})</span>
          </template>
          <span class="agent-group-item-actions" @click.stop>
            <button class="icon-btn-small" title="Rename group" @click="startRenameGroup(group)" v-html="BTN_ICONS.edit"></button>
            <button class="icon-btn-small" title="Delete group" @click="deleteGroup(group)" v-html="BTN_ICONS.trash"></button>
          </span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, defineProps, defineEmits } from 'vue'

// Functional icons: hand-drawn 16x16 stroke line SVG, using currentColor to inherit the theme color (consistent with the agent type icon style)
const SIDEBAR_ICONS = {
  location: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 1.5a4.5 4.5 0 0 0-4.5 4.5c0 3.3 4.5 8.5 4.5 8.5s4.5-5.2 4.5-8.5A4.5 4.5 0 0 0 8 1.5z"/><circle cx="8" cy="6" r="1.5"/></svg>',
  proxy: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 13V7a2 2 0 0 1 2-2h6"/><path d="M10 2.5 13 5l-3 2.5"/></svg>',
  llm: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="4" width="8" height="8" rx="1.5"/><path d="M4 6.5H2.5M4 9.5H2.5M13.5 6.5H12M13.5 9.5H12M6.5 4V2.5M9.5 4V2.5M6.5 13.5V12M9.5 13.5V12"/><circle cx="8" cy="8" r="1.5"/></svg>',
  worktree: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5.5 13.5V6a3 3 0 0 1 3-3h3"/><path d="M9.5 1.5 12.5 3l-3 1.5"/><circle cx="5.5" cy="13.5" r="1"/></svg>',
  quick: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8.5 1.5 4 9h3l-1 5.5L11.5 7H8z"/></svg>'
}
// Generic small icons (for buttons, 14px)
const BTN_ICONS = {
  check: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="2.5" width="11" height="11" rx="2"/><path d="m5 8 2 2 4-4"/></svg>',
  unchecked: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="2.5" width="11" height="11" rx="2"/></svg>',
  folder: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 4.5v7a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H8.2L6.7 4.5H2.5a1 1 0 0 0-1 1z"/></svg>',
  puzzle: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6.5 3a1.5 1.5 0 0 1 3 0v1h2a1 1 0 0 1 1 1v2h1a1.5 1.5 0 0 1 0 3h-1v2a1 1 0 0 1-1 1H9.5v1a1.5 1.5 0 0 1-3 0v-1H4.5a1 1 0 0 1-1-1V9.5h-1a1.5 1.5 0 0 1 0-3h1V4.5a1 1 0 0 1 1-1h2z"/></svg>',
  plus: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3v10M3 8h10"/></svg>',
  close: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>',
  copy: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5.5 4.5h-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1"/><rect x="5.5" y="2.5" width="5" height="3" rx="0.5"/></svg>',
  trash: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4.5h10M6.5 4.5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1.5"/><path d="M4.5 4.5l.7 8.3a1 1 0 0 0 1 .9h3.6a1 1 0 0 0 1-.9l.7-8.3"/><path d="M6.5 7.5v4M9.5 7.5v4"/></svg>',
  edit: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 13l.8-2.6 7.2-7.2a1.4 1.4 0 0 1 2 2l-7.2 7.2z"/><path d="M3 13h3.5"/></svg>'
}

// Group collapse state management - stored in an object to avoid Set reactivity issues
const collapsedGroupsMap = ref({})

// Track waiting-for-input Agents that have been clicked - restore state from localStorage
const CLICKED_WAITING_STORAGE_KEY = 'haijunbot_clicked_waiting_agents'

// Load clicked state from localStorage
function loadClickedWaitingAgents() {
  try {
    const stored = localStorage.getItem(CLICKED_WAITING_STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      return new Set(Array.isArray(parsed) ? parsed : [])
    }
  } catch (e) {
    console.warn('[AGENT_SIDEBAR] Failed to load clicked waiting agents:', e)
  }
  return new Set()
}

// Save clicked state to localStorage
function saveClickedWaitingAgents(set) {
  try {
    localStorage.setItem(CLICKED_WAITING_STORAGE_KEY, JSON.stringify([...set]))
  } catch (e) {
    console.warn('[AGENT_SIDEBAR] Failed to save clicked waiting agents:', e)
  }
}

const clickedWaitingAgents = ref(loadClickedWaitingAgents())

function isGroupCollapsed(groupKey) {
  return !!collapsedGroupsMap.value[groupKey]
}

function toggleGroupCollapse(groupKey) {
  if (collapsedGroupsMap.value[groupKey]) {
    collapsedGroupsMap.value[groupKey] = false
  } else {
    collapsedGroupsMap.value[groupKey] = true
  }
}

// Node display name: prefer the custom display name provided by the parent, falling back to the original node label
function nodeDisplayLabel(agent) {
  if (typeof props.getNodeDisplayLabel === 'function') {
    return props.getNodeDisplayLabel(agent)
  }
  return props.getNodeLabel(agent)
}

// Working directory display: prefer the parent-provided display function (which may hide it), falling back to the original directory
function workingDirDisplay(agent) {
  if (typeof props.getWorkingDirDisplay === 'function') {
    return props.getWorkingDirDisplay(agent.working_dir)
  }
  return agent.working_dir
}

// Handle Agent click event and record the clicked state
function handleAgentClick(agent, event) {
  // If in the waiting-for-input state, record the click
  if (props.isWaitingInput(agent)) {
    clickedWaitingAgents.value.add(agent.agent_id)
    // Persist to localStorage
    saveClickedWaitingAgents(clickedWaitingAgents.value)
    // Trigger a reactive update
    clickedWaitingAgents.value = new Set(clickedWaitingAgents.value)
  }
  // Emit the click event to the parent
  emit('agentClick', agent, event)
}

// Right-click on an Agent item: hand off to the parent to show that Agent's action menu
function handleAgentContextMenu(agent, event) {
  emit('agentContextMenu', agent, event)
}

// Determine whether the group contains a waiting-for-input Agent that has not been clicked (blinking)
function hasUnreadWaitingAgent(agents) {
  return agents.some(agent =>
    props.isWaitingInput(agent) && !clickedWaitingAgents.value.has(agent.agent_id)
  )
}

// Determine whether the group contains a waiting-for-input Agent that has been clicked (background color)
function hasClickedWaitingAgent(agents) {
  return agents.some(agent =>
    props.isWaitingInput(agent) && clickedWaitingAgents.value.has(agent.agent_id)
  )
}

const props = defineProps({
  visible: Boolean,
  resizeState: Object,
  sidebarStyle: Object,
  isBatchMode: Boolean,
  displayGroups: Array,
  currentAgentId: String,
  selectedCount: Number,
  agentList: Array,
  windowWidth: Number,
  isAllSelected: Boolean,
  agentStatuses: Map,  // Agent status map (agent_id -> {execution_status})
  getStatusClass: Function,
  getStatusText: Function,
  getNodeLabel: Function,
  getNodeDisplayLabel: Function,
  getProxyNodeLabel: Function,
  getWorkingDirDisplay: Function,
  isSelected: Function,
  isWaitingInput: Function,
  agentGroups: { type: Array, default: () => [] },
  nodes: { type: Array, default: () => [] },
  currentUserId: { type: String, default: '' },
  currentUserName: { type: String, default: '' },
  isConnected: { type: Boolean, default: true },
  // True when embedded in the editor sidebar: hides its own close button and width resize handle, managed uniformly by the host
  embedded: { type: Boolean, default: false }
})

// Group modal state
const showGroupModal = ref(false)
const newGroupName = ref('')
// Manage groups modal state (rename / delete)
const showManageGroupsModal = ref(false)
// Group rename state
const editingGroupId = ref(null)
const editingGroupName = ref('')
const groupRenameInputRef = ref(null)

function openGroupModal() {
  newGroupName.value = ''
  showGroupModal.value = true
}

function closeGroupModal() {
  showGroupModal.value = false
  cancelRenameGroup()
}

// Open/close the "Manage Groups" modal
function openManageGroups() {
  cancelRenameGroup()
  showManageGroupsModal.value = true
}

function closeManageGroups() {
  showManageGroupsModal.value = false
  cancelRenameGroup()
}

function selectGroup(groupId) {
  emit('addToGroup', groupId)
  closeGroupModal()
}

function handleCreateGroup() {
  const name = newGroupName.value.trim()
  if (!name) return
  emit('createGroupWithAgents', name)
  newGroupName.value = ''
  closeGroupModal()
}

// Start renaming a group
function startRenameGroup(group) {
  if (!group) return
  editingGroupId.value = group.id
  editingGroupName.value = group.name || ''
  nextTick(() => {
    const el = groupRenameInputRef.value
    if (el) {
      el.focus()
      el.select()
    }
  })
}

function cancelRenameGroup() {
  editingGroupId.value = null
  editingGroupName.value = ''
}

// Confirm rename: emit only if the name is non-empty and differs from the original
function confirmRenameGroup() {
  const groupId = editingGroupId.value
  if (!groupId) return
  const group = props.agentGroups.find(g => g.id === groupId)
  const name = editingGroupName.value.trim()
  if (group && name && name !== group.name) {
    emit('renameGroup', { groupId, name })
  }
  cancelRenameGroup()
}

// Delete group (the parent shows a unified confirmation dialog)
function deleteGroup(group) {
  if (!group) return
  emit('deleteGroup', group.id)
}

// Collapse all groups on init - set only on first initialization to avoid later data updates overwriting user actions
watch(() => props.displayGroups, (newGroups) => {
  if (!newGroups || newGroups.length === 0) return
  // Initialize collapse state only when collapsedGroupsMap is empty
  if (Object.keys(collapsedGroupsMap.value).length === 0) {
    newGroups.forEach(group => {
      if (group.isCollapsible) {
        collapsedGroupsMap.value[group.key] = true
      }
    })
  }
}, { immediate: true })

const emit = defineEmits([
  'close',
  'toggleBatchMode',
  'createAgent',
  'orchestrate',
  'agentClick',
  'agentContextMenu',
  'toggleSelectAgent',
  'renameAgent',
  'copyAgent',
  'deleteAgent',
  'toggleSelectAll',
  'batchCopy',
  'batchDelete',
  'addToGroup',
  'createGroupWithAgents',
  'renameGroup',
  'deleteGroup',
  'startResize',
  'editAccess',
  'regenerateAgent',
])

// Watch agentStatuses; clear the clicked marker when an agent transitions from waiting-for-input to non-waiting
// Use a ref to track the previous state
const previousStatusMap = ref(new Map())

watch(() => props.agentStatuses, (newStatuses) => {
  if (!newStatuses) return

  // Iterate over all agents and check for status changes
  props.agentList?.forEach(agent => {
    const agentId = agent.agent_id
    const currentStatus = newStatuses.get(agentId)
    const previousStatus = previousStatusMap.value.get(agentId)

    // If the current status exists
    if (currentStatus) {
      const executionStatus = currentStatus.execution_status
      const isWaiting = executionStatus === 'waiting_multi' || executionStatus === 'waiting_single' || executionStatus === 'waiting_confirm'

      // If it was previously waiting for input and no longer is, clear the clicked marker
      if (previousStatus) {
        const prevExecutionStatus = previousStatus.execution_status
        const wasWaiting = prevExecutionStatus === 'waiting_multi' || prevExecutionStatus === 'waiting_single' || prevExecutionStatus === 'waiting_confirm'

        if (wasWaiting && !isWaiting) {
          if (clickedWaitingAgents.value.has(agentId)) {
            clickedWaitingAgents.value.delete(agentId)
            // Persist to localStorage
            saveClickedWaitingAgents(clickedWaitingAgents.value)
            // Trigger a reactive update
            clickedWaitingAgents.value = new Set(clickedWaitingAgents.value)
          }
        }
      }

      // Update the previous state
      previousStatusMap.value.set(agentId, { ...currentStatus })
    }
  })
}, { deep: true })

// Watch currentAgentId and automatically expand the corresponding node group
watch(() => props.currentAgentId, (newAgentId) => {
  if (!newAgentId || !props.agentList) return

  const agent = props.agentList.find(a => a.agent_id === newAgentId)
  if (!agent) return

  // Get the node label
  const nodeLabel = props.getNodeLabel(agent)
  const groupKey = `node-${nodeLabel}`

  // If the group is collapsed, expand it
  if (collapsedGroupsMap.value[groupKey]) {
    collapsedGroupsMap.value[groupKey] = false
  }
})

defineExpose({
  openManageGroups,
})
</script>
<style scoped>
.icon-btn {
  background: var(--color-bg-tertiary);
  border: none;
  border-radius: var(--tile-radius);
  font-size: 18px;
  cursor: pointer;
  padding: 0;
  color: var(--color-text-secondary);
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-btn:hover:not(:disabled) {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
  transform: translateY(-1px);
}

.icon-btn:active:not(:disabled) {
  transform: translateY(0);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.icon-btn.active {
  background: var(--color-accent-subtle);
  color: var(--color-accent);
  border-color: var(--color-border-active);
}

.agent-sidebar {
  position: relative;
  width: 320px;
  min-width: 0;
  background: var(--color-bg-secondary);
  border-right: 0.5px solid var(--color-border-subtle);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.agent-sidebar.collapsed {
  width: 0;
  border-right: none;
  overflow: hidden;
}

.agent-sidebar-resizing {
  user-select: none;
}

.agent-sidebar-resize-handle {
  position: absolute;
  top: 0;
  right: -4px;
  width: 8px;
  height: 100%;
  cursor: ew-resize;
  z-index: 5;
}

.agent-sidebar-resize-handle::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 2px;
  transform: translateX(-50%);
  background: transparent;
  transition: background 0.15s ease;
}

.agent-sidebar-resize-handle:hover::after,
.agent-sidebar-resizing .agent-sidebar-resize-handle::after {
  background: var(--color-accent-glow);
}

.agent-sidebar-header {
  padding: 12px;
  border-bottom: 0.5px solid var(--color-border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--color-bg-tertiary);
}

.sidebar-header-actions {
  display: flex;
  gap: 8px;
}

.agent-sidebar-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.agent-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}


.hello-user-banner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 14px 8px;
  margin-bottom: 8px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(120, 80, 255, 0.18), rgba(0, 200, 255, 0.18));
  border: 1px solid rgba(150, 120, 255, 0.35);
}

.hello-user-glow {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.5px;
  background: linear-gradient(90deg, #7b5cff, #00d4ff, #ff5cc8, #7b5cff);
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: hello-user-flow 4s linear infinite;
  filter: drop-shadow(0 0 5px rgba(123, 92, 255, 0.45));
}

.hello-user-sub {
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--color-text-secondary, #9aa4b2);
}

@keyframes hello-user-flow {
  0% { background-position: 0% 50%; }
  100% { background-position: 300% 50%; }
}

.agent-collapsed-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-collapsed-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: var(--color-bg-tertiary);
  border: none;
  border-radius: var(--tile-radius-xs);
  color: var(--color-text-secondary);
  cursor: pointer;
  text-align: left;
}

.agent-collapsed-toggle:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

/* Group contains a clicked waiting-for-input Agent - background color */
.agent-collapsed-toggle.group-waiting-clicked {
  background: rgba(210, 153, 34, 0.35);
}

/* Group contains an unclicked waiting-for-input Agent - breathing-light blink */
.agent-collapsed-toggle.group-waiting-unread {
  animation: group-breathing 2s ease-in-out infinite;
}

@keyframes group-breathing {
  0%, 100% {
    background: rgba(210, 153, 34, 0.35);
  }
  50% {
    background: rgba(210, 153, 34, 0.65);
  }
}

.agent-collapsed-arrow {
  width: 16px;
  color: var(--color-accent);
}

.agent-collapsed-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
}

.agent-collapsed-count {
  font-size: 12px;
  color: var(--color-text-muted);
}

.agent-item {
  padding: 6px;
  background: var(--color-bg-tertiary);
  border: none;
  border-radius: var(--tile-radius-xs);
  cursor: pointer;
  position: relative;
}

.agent-item:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-border-active);
}

.agent-item.active {
  background: rgba(32, 200, 255, 0.25);
  border-color: var(--color-border-active);
}

.agent-item.selected {
  background: var(--color-accent-subtle);
  border-color: var(--color-border-active);
}

.agent-item.waiting-input {
  background: rgba(210, 153, 34, 0.35);
}

/* Active + waiting-for-input combined state - uses a purple background */
.agent-item.active.waiting-input {
  background: rgba(32, 200, 255, 0.35);
}

/* Unclicked waiting-for-input state - breathing-light effect */
.agent-item.waiting-input-unread {
  animation: breathing 2s ease-in-out infinite;
}

@keyframes breathing {
  0%, 100% {
    background: rgba(210, 153, 34, 0.35);
  }
  50% {
    background: rgba(210, 153, 34, 0.65);
  }
}

.agent-checkbox {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.agent-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--color-accent);
}

.batch-actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--color-bg-secondary);
  border-top: 1px solid var(--color-border-subtle);
  gap: 12px;
}

.batch-actions-info {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.batch-actions-buttons {
  display: flex;
  gap: 8px;
}

.group-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
}

.group-modal {
  width: 320px;
  max-width: 90vw;
  max-height: 70vh;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.group-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.agent-group-empty {
  font-size: 12px;
  color: var(--color-text-muted);
  padding: 4px 0;
}

.agent-group-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px;
  border-radius: var(--tile-radius-xs);
  cursor: pointer;
  transition: background 0.15s ease;
}

.agent-group-item:hover {
  background: var(--color-bg-hover);
}

.agent-group-item-name {
  font-size: 12px;
  color: var(--color-text-primary);
}

.agent-group-item-count {
  font-size: 11px;
  color: var(--color-text-muted);
}

/* Group action buttons: hidden by default, shown on hover */
.agent-group-item-actions {
  display: none;
  gap: 2px;
  align-items: center;
  margin-left: auto;
}

.agent-group-item:hover .agent-group-item-actions {
  display: flex;
}

.agent-group-rename-input {
  flex: 1;
  font-size: 12px;
  padding: 2px 6px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-active);
  border-radius: var(--tile-radius-xs);
  color: var(--color-text-primary);
  outline: none;
}

.agent-group-create {
  display: flex;
  gap: 4px;
  align-items: center;
  margin-top: 4px;
}

.agent-group-create-input {
  flex: 1;
  font-size: 12px;
  padding: 4px 6px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius-xs);
  color: var(--color-text-primary);
  outline: none;
}

.agent-group-create-input:focus {
  border-color: var(--color-border-active);
}

.agent-item .agent-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--color-bg-hover);
  margin-left: 8px;
}

.agent-item .agent-status.running {
  background: var(--color-accent-subtle);
  color: var(--color-accent);
}

.agent-item .agent-status.stopped {
  background: rgba(54, 255, 124, 0.15);
  color: var(--color-success);
}

.agent-item .agent-status.waiting_multi {
  background: rgba(255, 133, 32, 0.15);
  color: var(--color-warning);
}

.agent-item .agent-status.waiting_single {
  background: rgba(255, 60, 72, 0.15);
  color: var(--color-error);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 2px;
}

.agent-type {
  font-size: 16px;
}

.agent-status {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.agent-status.running {
  background: rgba(54, 255, 124, 0.15);
  color: var(--color-success);
}

.agent-status.stopped {
  background: rgba(255, 60, 72, 0.15);
  color: var(--color-error);
}

.agent-status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-left: 4px;
  flex-shrink: 0;
}

.agent-status-dot.running {
  background: var(--color-success);
  box-shadow: var(--tile-shadow);
}

.agent-status-dot.stopped {
  background: var(--color-error);
  box-shadow: var(--tile-shadow);
}

.agent-status-dot.waiting_multi {
  background: var(--color-warning);
  box-shadow: var(--tile-shadow);
}

.agent-status-dot.waiting_single {
  background: var(--color-warning);
  box-shadow: var(--tile-shadow);
}

.agent-status-dot.waiting_confirm {
  background: var(--color-warning);
  box-shadow: var(--tile-shadow);
}

.agent-llm-group {
  font-size: 10px;
  color: #666;
  background: rgba(138, 163, 184, 0.1);
  padding: 1px 4px;
  border-radius: 3px;
}

.agent-port {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-left: auto;
}

.agent-type-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.agent-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  flex-shrink: 0;
}

.agent-dir-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}

.agent-dir {
  font-size: 10px;
  color: var(--color-text-secondary);
  word-break: break-all;
  line-height: 1.3;
  flex: 1;
  min-width: 0;
}

.agent-actions {
  display: flex;
  gap: 3px;
  margin-top: 4px;
  justify-content: flex-end;
}

.icon-btn-small {
  background: var(--color-bg-tertiary);
  border: none;
  border-radius: var(--tile-radius-xs);
  font-size: 12px;
  cursor: pointer;
  padding: 3px 6px;
  color: var(--color-text-secondary);
  transition: all 0.2s ease;
}

.icon-btn-small:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
  transform: translateY(-1px);
}

.icon-btn-small:active {
  transform: translateY(0);
}

.icon-btn-small:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.agent-actions .icon-btn-small.stop-btn:hover {
  background: rgba(255, 60, 72, 0.15);
  color: var(--color-error);
}

.agent-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  font-size: 14px;
  padding: 20px;
}

.agent-proxy-node-label {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: var(--tile-radius);
  background: rgba(32, 200, 255, 0.1); /* Light blue background */
  color: #20c8ff; /* Blue text */
  border: none;
  margin-left: 4px;
}

.agent-meta-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--color-bg-hover);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.meta-icon {
  display: inline-flex;
  vertical-align: middle;
  margin-right: 2px;
}
.meta-icon svg {
  width: 12px;
  height: 12px;
}

.agent-node-label {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: var(--tile-radius);
  background: var(--color-bg-hover);
  color: var(--color-text-secondary);
  border: none;
  margin-left: 4px;
}


</style>
