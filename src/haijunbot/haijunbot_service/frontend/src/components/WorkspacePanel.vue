<template>
  <aside
    v-show="visible"
    class="workspace-panel"
    :class="{ 'workspace-panel-dragging': interaction.active, 'workspace-panel-active': active, 'workspace-panel-embedded': embedded }"
    :style="panelStyle"
    @mousedown="$emit('focus', 'workspace')"
  >
    <div
      class="workspace-panel-header"
      @mousedown="!embedded && $emit('startMove', $event)"
    >
      <div class="workspace-panel-title-group">
        <h3>Workspace</h3>
      </div>
      <div class="workspace-panel-actions">
        <button class="icon-btn close-btn" tabindex="-1" @mousedown.prevent @click.stop="$emit('close')" title="Close">✕</button>
      </div>
    </div>
    <div class="workspace-main">
      <div class="workspace-activity-bar">
        <button
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === 'agents' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'agents')"
          title="Agent List (Space v a)"
        >
          <img class="workspace-activity-icon" src="/icons/haijunbot-pet.svg" alt="Agent" />
        </button>
        <button
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === 'files' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'files')"
          title="Directory Tree"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M1.5 4.5A1.5 1.5 0 0 1 3 3h2.4l1.6 1.6H13A1.5 1.5 0 0 1 14.5 6v5.5A1.5 1.5 0 0 1 13 13H3a1.5 1.5 0 0 1-1.5-1.5v-7Z"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === 'search' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'search')"
          title="Global Search"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">
            <circle cx="7" cy="7" r="4.5"/>
            <path d="M10.5 10.5 14 14"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === 'git' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'git')"
          title="Git (Space v g)"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="5" cy="4" r="1.5"/>
            <circle cx="5" cy="12" r="1.5"/>
            <circle cx="11" cy="8" r="1.5"/>
            <path d="M5 5.5v5"/>
            <path d="M6.5 12H9.5a1.5 1.5 0 0 0 1.5-1.5V9"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          :class="{ active: mainView === 'chat' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setMainView', 'chat')"
          title="Chat Rooms"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M2 3.5A1.5 1.5 0 0 1 3.5 2h9A1.5 1.5 0 0 1 14 3.5v6a1.5 1.5 0 0 1-1.5 1.5H6.5L3.5 14v-3H3.5A1.5 1.5 0 0 1 2 9.5v-6Z"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          :class="{ active: mainView === 'terminal' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setMainView', 'terminal')"
          title="Terminal"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M2 3.5A1.5 1.5 0 0 1 3.5 2h9A1.5 1.5 0 0 1 14 3.5v9a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 12.5v-9Z"/>
            <path d="M5 6l2 2-2 2"/>
            <path d="M8.5 10H11"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('openSettings')"
          title="Settings (Space v s)"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="8" cy="8" r="1.5"/>
            <circle cx="8" cy="8" r="4.2"/>
            <g stroke-width="2.4">
              <path d="M8 3.8v-2M10.97 5.03l1.41-1.41M12.2 8h2M10.97 10.97l1.41 1.41M8 12.2v2M5.03 10.97l-1.41 1.41M3.8 8h-2M5.03 5.03l-1.41-1.41"/>
            </g>
          </svg>
        </button>
        <button
          v-if="isAdmin"
          class="workspace-activity-button"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('openAdmin')"
          title="Admin (Space m a)"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M8 1.5 13 3.5v4c0 3-2 5.5-5 7-3-1.5-5-4-5-7v-4L8 1.5Z"/>
            <path d="M5.5 8l1.7 1.7L10.5 6"/>
          </svg>
        </button>
        <button
          v-if="isAdmin"
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === 'plugins' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'plugins')"
          title="Plugin Management"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M9.5 2.5h3a1 1 0 0 1 1 1v3h-1.2a1.3 1.3 0 0 0 0 2.6H13.5v3a1 1 0 0 1-1 1h-3v-1.2a1.3 1.3 0 0 0-2.6 0V13h-3a1 1 0 0 1-1-1V9.5h1.2a1.3 1.3 0 0 0 0-2.6H2.5v-3a1 1 0 0 1 1-1h3v1.2a1.3 1.3 0 0 0 2.6 0V2.5Z"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === 'manage' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'manage')"
          title="Capability List"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="2.5" y="2.5" width="4.5" height="4.5" rx="1"/>
            <rect x="9" y="2.5" width="4.5" height="4.5" rx="1"/>
            <rect x="2.5" y="9" width="4.5" height="4.5" rx="1"/>
            <rect x="9" y="9" width="4.5" height="4.5" rx="1"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === 'timers' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'timers')"
          title="Scheduled Tasks"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="8" cy="8" r="5.5"/>
            <path d="M8 4.5V8l2.5 1.5"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === 'orchestration' }"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'orchestration')"
          title="Orchestration View"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="1.5" y="2" width="4" height="3.5" rx="1"/>
            <rect x="1.5" y="10.5" width="4" height="3.5" rx="1"/>
            <rect x="10.5" y="6.25" width="4" height="3.5" rx="1"/>
            <path d="M5.5 3.75h2.5v4.25h2.5"/>
            <path d="M5.5 12.25h2.5V8h2.5"/>
          </svg>
        </button>
        <!-- Plugin-provided sidebar view entries (option 2: the plugin config.yaml's frontend.sidebar_views) -->
        <button
          v-for="ext in pluginSidebarViews"
          :key="'plugin-view-' + ext.id"
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === ('plugin:' + ext.id) }"
          tabindex="-1"
          :title="ext.title"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'plugin:' + ext.id)"
        >
          <span v-if="ext.iconSvg" class="workspace-activity-plugin-icon" v-html="ext.iconSvg"></span>
          <svg v-else viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M6.5 2.5a1.5 1.5 0 0 1 3 0V3h2.5a1 1 0 0 1 1 1v2.5h.5a1.5 1.5 0 0 1 0 3H13V12a1 1 0 0 1-1 1H9.5v.5a1.5 1.5 0 0 1-3 0V13H4a1 1 0 0 1-1-1V9.5h-.5a1.5 1.5 0 0 1 0-3H3V4a1 1 0 0 1 1-1h2.5v-.5Z"/>
          </svg>
        </button>
        <!-- Plugin-provided tool_panel entries (the plugin config.yaml's frontend.tool_panels) -->
        <button
          v-for="ext in pluginToolPanels"
          :key="'plugin-tool-' + ext.id"
          class="workspace-activity-button"
          :class="{ active: showSidebar && sidebarView === ('plugin-tool:' + ext.id) }"
          tabindex="-1"
          :title="ext.title"
          @mousedown.prevent
          @click="$emit('setSidebarView', 'plugin-tool:' + ext.id)"
        >
          <span v-if="ext.iconSvg" class="workspace-activity-plugin-icon" v-html="ext.iconSvg"></span>
          <svg v-else viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M6.5 2.5a1.5 1.5 0 0 1 3 0V3h2.5a1 1 0 0 1 1 1v2.5h.5a1.5 1.5 0 0 1 0 3H13V12a1 1 0 0 1-1 1H9.5v.5a1.5 1.5 0 0 1-3 0V13H4a1 1 0 0 1-1-1V9.5h-.5a1.5 1.5 0 0 1 0-3H3V4a1 1 0 0 1 1-1h2.5v-.5Z"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('openTopology')"
          title="Network Topology"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="4" cy="4" r="1.5"/>
            <circle cx="12" cy="4" r="1.5"/>
            <circle cx="8" cy="12" r="1.5"/>
            <path d="M5.5 4H10.5"/>
            <path d="M5 5.5 6.8 10.5"/>
            <path d="M11 5.5 9.2 10.5"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('openDocs')"
          title="Documentation (Space m h)"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="8" cy="8" r="6"/>
            <path d="M6.3 6.4a1.7 1.7 0 1 1 2.8 1.3c-.8.6-1.1 1-1.1 1.8"/>
            <circle cx="8" cy="11.6" r="0.4" fill="currentColor" stroke="none"/>
          </svg>
        </button>
        <button
          class="workspace-activity-button"
          tabindex="-1"
          @mousedown.prevent
          @click="$emit('openAbout')"
          title="About"
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="8" cy="8" r="6"/>
            <path d="M8 7.2V11"/>
            <circle cx="8" cy="5.2" r="0.4" fill="currentColor" stroke="none"/>
          </svg>
        </button>
      </div>
      <slot name="sidebar"></slot>
      <div class="workspace-panel-content workspace-panel-content-main">
<!-- File tabs: they belong only to the "file view" and sit at the top of the main area (not spanning the activity bar/sidebar).
             In free-split mode they are rendered inside each file pane instead (see App.vue #pane-content);
             they are no longer rendered here, to avoid the tab strip spanning the entire workspace width. -->
        <div class="workspace-tabs" v-if="!$slots['pane-tree'] && mainView === 'file' && tabs.length > 0">
          <div
            v-for="tab in tabs"
            :key="tab.path"
            class="workspace-tab"
            :class="{ active: activeTabPath === tab.path }"
            @click="$emit('activateTab', tab.path)"
            @contextmenu.prevent.stop="$emit('tabContextMenu', tab.path, $event)"
          >
            <span class="workspace-tab-name">{{ tab.name }}</span>
            <span v-if="tab.isDirty" class="workspace-tab-dirty">●</span>
            <button class="workspace-tab-close" tabindex="-1" @mousedown.prevent @click.stop="$emit('closeTab', tab.path)">✕</button>
          </div>
          <!-- The unsplit state also offers the save / read-only toggle (acting on the currently active file),
                consistent with each pane's toolbar in the split state, avoiding "cannot toggle editable when unsplit". -->
          <div class="workspace-pane-actions">
            <button
              class="workspace-pane-action"
              :disabled="!hasActiveTab"
              tabindex="-1"
              @mousedown.prevent
              @click.stop="$emit('save')"
              title="Save current file"
            ><span v-html="WORKSPACE_ICONS.save"></span></button>
            <button
              class="workspace-pane-action"
              :class="{ editable: isEditable }"
              :disabled="!hasActiveTab"
              tabindex="-1"
              @mousedown.prevent
              @click.stop="$emit('toggleEditable')"
              :title="isEditable ? 'Switch to read-only mode' : 'Switch to edit mode'"
            ><span v-html="isEditable ? WORKSPACE_ICONS.unlock : WORKSPACE_ICONS.lock"></span></button>
          </div>
        </div>
<!-- Free-split mode: App.vue provides the whole pane tree (including each leaf's content);
             the original single-view content is no longer rendered, avoiding two rendering paths coexisting. -->
        <slot name="pane-tree"></slot>
        <template v-if="!$slots['pane-tree']">
<!-- Area title bar for the unsplit state: same source as each pane's title bar in the split state (WorkspacePaneHeader),
             ensuring "there is a split entry even when unsplit". Passed in by App.vue (including the root leaf and split callbacks). -->
        <slot name="main-view-header"></slot>
        <slot name="main-view"></slot>
        <div v-show="mainView === 'file'" class="workspace-main-file-view">
          <div v-if="tabs.length === 0" class="workspace-placeholder">
            <div class="workspace-placeholder-icon" v-html="WORKSPACE_ICONS.placeholder"></div>
            <div class="workspace-placeholder-title">Click a file in the file tree to open the code editor</div>
            <div class="workspace-placeholder-text">Supports Monaco syntax highlighting, IntelliSense, code folding, multi-tab switching, and saving.</div>
          </div>
          <div v-else ref="editorContainerRef" class="workspace-monaco-container"></div>
        </div>
        </template>
      </div>
    </div>
    <div
      v-for="direction in resizeDirections"
      :key="direction"
      :class="['workspace-resize-handle', `workspace-resize-${direction}`]"
      @mousedown="$emit('startResize', $event, direction)"
    ></div>
  </aside>
</template>

<script setup>
import { ref, defineProps, defineEmits } from 'vue'

// Hand-drawn 16x16 stroke linear SVG icons (currentColor inherits the theme color), consistent with the global style
const WORKSPACE_ICONS = {
  save: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 2.5h9l1.5 1.5v9.5a1 1 0 0 1-1 1h-10a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1z"/><path d="M5 2.5v4h5v-4M5 13.5v-5h6v5"/></svg>',
  lock: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/></svg>',
  unlock: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 4.9-.8"/></svg>',
  placeholder: '<svg viewBox="0 0 16 16" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 1.5h8v13l-1.5-1-1.5 1-1.5-1-1.5 1-1.5-1z"/><path d="M6 5.5h4M6 8h4M6 10.5h2.5"/></svg>',
}

const props = defineProps({
  visible: Boolean,
  active: Boolean,
  embedded: Boolean,
  interaction: Object,
  panelStyle: Object,
  agentName: String,
  activeTab: Object,
  activeTabPath: String,
  tabs: Array,
  isMaximized: Boolean,
  showSidebar: Boolean,
  sidebarView: String,
  mainView: { type: String, default: 'file' },
  resizeDirections: Array,
  isAdmin: { type: Boolean, default: false },
  isEditable: { type: Boolean, default: false },
  hasActiveTab: { type: Boolean, default: false },
  pluginSidebarViews: { type: Array, default: () => [] },
  pluginToolPanels: { type: Array, default: () => [] }
})

const emit = defineEmits([
  'focus',
  'startMove',
  'toggleMaximize',
  'save',
  'close',
  'activateTab',
  'closeTab',
  'tabContextMenu',
  'toggleEditable',
  'setSidebarView',
  'setMainView',
  'startResize',
  'closeSidebar',
  'openSettings',
  'openDocs',
  'openAdmin',
  'openAbout',
  'openTopology'
])

const editorContainerRef = ref(null)

defineExpose({
  editorContainerRef
})
</script>

<style scoped>
.workspace-panel {
  position: fixed;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius);
  box-shadow: var(--tile-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  user-select: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.workspace-panel-active {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 1px var(--color-accent), 0 0 12px rgba(32, 200, 255, 0.15);
}

.workspace-panel-dragging {
  transition: none;
}

.workspace-panel-embedded {
  position: relative !important;
  width: 100% !important;
  height: 100% !important;
  top: auto !important;
  left: auto !important;
  border-radius: 4px;
}

.workspace-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 10px;
  border-bottom: 1px solid var(--color-border-subtle);
  background: var(--color-bg-primary);
  cursor: move;
  gap: 8px;
  min-height: 28px;
}

.workspace-panel-title-group {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.workspace-panel-header h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.workspace-panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.workspace-panel-actions .close-btn {
  width: 22px;
  height: 22px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-hover);
  border: none;
  border-radius: var(--tile-radius-xs);
  color: #8ba3b8;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}

.workspace-panel-actions .close-btn:hover {
  background: var(--color-bg-tertiary);
  color: #e6edf3;
}

.workspace-tabs {
  display: flex;
  align-items: stretch;
  gap: 2px;
  padding: 4px 4px 0;
  background: var(--color-bg-primary);
  overflow-x: auto;
  flex-shrink: 0;
}

.workspace-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  max-width: 220px;
  padding: 6px 10px;
  border: none;
  border-bottom: none;
  border-radius: var(--tile-radius-xs) var(--tile-radius-xs) 0 0;
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 12px;
  line-height: 1.2;
}

.workspace-tab.active {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}

.workspace-tab-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-tab-dirty {
  color: #ff8520;
  font-size: 10px;
}

.workspace-tab-close {
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 0;
}
/* Save / read-only buttons at the right of the unsplit-state tab strip (same as the split-state pane toolbar) */
.workspace-pane-actions {
  position: sticky;
  right: 0;
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 2px;
  padding-left: 6px;
  background: var(--color-bg-secondary, #1e1e1e);
}
.workspace-pane-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
}
.workspace-pane-action:hover:not(:disabled) {
  background: var(--color-bg-hover, rgba(255, 255, 255, 0.08));
}
.workspace-pane-action.editable {
  color: var(--color-accent, #4a9eff);
}
.workspace-pane-action:disabled {
  opacity: 0.4;
  cursor: default;
}

.workspace-main {
  flex: 1;
  min-height: 0;
  display: flex;
  background: var(--color-bg-primary);
}

.workspace-activity-bar {
  width: 44px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  border-right: 1px solid var(--color-border-subtle);
  background: var(--color-bg-primary);
}

.workspace-activity-button {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  line-height: 1;
  border: 1px solid transparent;
  border-radius: var(--tile-radius);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease-out;
}

.workspace-activity-button:hover,
.workspace-activity-button.active {
  color: var(--color-text-primary);
  background: var(--color-accent-subtle);
  border-color: var(--color-border-active);
}

/* Agent icon: uses the main icon (the HaijunBot mascot), which must be scaled to match the emoji icons visually */
.workspace-activity-icon {
  width: 20px;
  height: 20px;
  display: block;
  object-fit: contain;
}

.workspace-activity-plugin-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}
.workspace-activity-plugin-icon svg {
  width: 16px;
  height: 16px;
}

.workspace-panel-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.workspace-panel-content-main {
  /* Tabs are pinned to the top and each content area scrolls on its own (Monaco/embedded views each have their own scroll containers),
     so this container does not scroll as a whole, avoiding the tabs scrolling away with the content. */
  overflow: hidden;
}

/* Main-area file view: fills the main area; internally the placeholder / Monaco container each expand */
.workspace-main-file-view {
  flex: 1;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.workspace-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: var(--color-text-secondary);
  text-align: center;
}

.workspace-placeholder-icon {
  font-size: 48px;
  opacity: 0.6;
}

.workspace-placeholder-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.workspace-placeholder-text {
  font-size: 13px;
  line-height: 1.6;
  max-width: 320px;
}

.workspace-monaco-container {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.workspace-resize-handle {
  position: absolute;
  background: transparent;
  z-index: 10;
}

.workspace-resize-n,
.workspace-resize-s {
  left: 10px;
  right: 10px;
  height: 6px;
  cursor: ns-resize;
}

.workspace-resize-n {
  top: 0;
}

.workspace-resize-s {
  bottom: 0;
}

.workspace-resize-e,
.workspace-resize-w {
  top: 10px;
  bottom: 10px;
  width: 6px;
  cursor: ew-resize;
}

.workspace-resize-e {
  right: 0;
}

.workspace-resize-w {
  left: 0;
}

.workspace-resize-ne,
.workspace-resize-nw,
.workspace-resize-se,
.workspace-resize-sw {
  width: 14px;
  height: 14px;
}

.workspace-resize-ne {
  top: 0;
  right: 0;
  cursor: nesw-resize;
}

.workspace-resize-nw {
  top: 0;
  left: 0;
  cursor: nwse-resize;
}

.workspace-resize-se {
  bottom: 0;
  right: 0;
  cursor: nwse-resize;
}

.workspace-resize-sw {
  bottom: 0;
  left: 0;
  cursor: nesw-resize;
}
</style>