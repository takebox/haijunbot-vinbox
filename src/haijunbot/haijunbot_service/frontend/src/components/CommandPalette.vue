<template>
  <transition name="cmd-fade">
    <div v-if="visible" class="cmd-overlay" @click.self="close" @keydown.stop>
      <div class="cmd-panel" role="dialog" aria-label="Command palette">
        <div class="cmd-search">
          <span class="cmd-search-ico">⌘</span>
          <input
            ref="inputEl"
            class="cmd-input"
            v-model="query"
            type="text"
            :placeholder="placeholder"
            autocomplete="off"
            spellcheck="false"
            @keydown="onInputKeydown"
            @blur="onInputBlur"
          />
          <span class="cmd-esc-hint">Esc</span>
        </div>

        <div class="cmd-list">
          <template v-if="groups.length > 0">
            <div v-for="g in groups" :key="g.group" class="cmd-group">
              <div class="cmd-group-title">{{ g.group }}</div>
              <button
                v-for="entry in g.actions"
                :key="entry.action.id"
                class="cmd-item"
                :class="{ 'is-active': entry.flatIndex === activeIndex, 'is-disabled': entry.disabled, 'agent-running': entry.action.statusClass === 'running', 'agent-stopped': entry.action.statusClass === 'stopped' }"
                :disabled="entry.disabled"
                :ref="el => setItemRef(el, entry.flatIndex)"
                @click="run(entry.action)"
                @mousemove="onItemHover(entry.flatIndex)"
              >
                <span class="cmd-item-ico" v-html="entry.action.icon"></span>
                <span class="cmd-item-label">
                  <span class="cmd-item-title">{{ entry.action.label }}<span v-if="entry.action.en" class="cmd-item-en">{{ entry.action.en }}</span></span>
                  <span v-if="entry.action.shortcut && entry.action.condition" class="cmd-item-meta">{{ entry.action.condition }}</span>
                  <span v-else-if="Array.isArray(entry.action.meta)" class="cmd-item-meta"><template v-for="(m, i) in entry.action.meta" :key="i"><span v-if="m.icon" class="cmd-meta-icon" v-html="m.icon"></span>{{ m.text }}<span v-if="i < entry.action.meta.length - 1" class="cmd-meta-sep"> </span></template></span>
                  <span v-else-if="entry.action.meta" class="cmd-item-meta">{{ entry.action.meta }}</span>
                </span>
                <span v-if="entry.action.shortcut" class="cmd-item-shortcut">{{ entry.action.shortcut }}</span>
              </button>
            </div>
          </template>
          <div v-else class="cmd-empty">{{ emptyText }}</div>
        </div>

        <div class="cmd-footer">
          <span><b>↑↓</b> Select</span>
          <span><b>Enter</b> {{ isAgentMode ? 'Open in current panel' : isFileMode ? 'Open file' : 'Run' }}</span>
          <span v-if="isAgentMode"><b>Tab</b> Open in new panel</span>
          <span v-if="isFileMode"><b>⌫</b> Back to commands</span>
          <span v-else-if="!isAgentMode"><b>a&gt;</b> Switch Agent<b>f&gt;</b> Search files</span>
          <span v-else><b>⌫</b> Back to commands</span>
          <span><b>Esc</b> Close</span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { filterActions, groupActions } from '../actions/registry.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  actions: { type: Array, default: () => [] },
  ctx: { type: Object, default: () => ({}) },
  title: { type: String, default: 'Search commands…' },
  // Pre-filled input when opened (e.g. 'a>' to go straight to the Agent list)
  initialQuery: { type: String, default: '' },
})

const emit = defineEmits(['update:visible', 'run', 'close'])

const query = ref('')
const activeIndex = ref(0)
const inputEl = ref(null)
const itemRefs = new Map()

// ===== Recently used: record executed command ids (up to 5, most recent first), persisted to localStorage =====
const RECENT_STORAGE_KEY = 'haijunbot_cmd_palette_recent'
const RECENT_LIMIT = 5

function loadRecentIds() {
  try {
    const raw = localStorage.getItem(RECENT_STORAGE_KEY)
    const parsed = JSON.parse(raw || '[]')
    return Array.isArray(parsed) ? parsed.filter(id => typeof id === 'string').slice(0, RECENT_LIMIT) : []
  } catch (err) {
    return []
  }
}

const recentIds = ref(loadRecentIds())

function recordRecent(actionId) {
  if (!actionId) return
  const next = [actionId, ...recentIds.value.filter(id => id !== actionId)].slice(0, RECENT_LIMIT)
  recentIds.value = next
  try {
    localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(next))
  } catch (err) {
    /* Ignore write failures (e.g. private mode) */
  }
}

function isDisabled(action) {
  if (typeof action.enabled === 'function') return !action.enabled(props.ctx || {})
  // Agent switch entries carry a boolean disabled directly to avoid conflicting with the enabled callback check above
  return action?.disabled === true
}

// ===== Agent switch mode: when a> or A> is typed, the list shows Agents instead =====
const AGENT_PREFIX = /^\s*a>\s*/i
const isAgentMode = computed(() => AGENT_PREFIX.test(query.value))
const agentQuery = computed(() => query.value.replace(AGENT_PREFIX, ''))

// ===== File search mode: when f> or F> is typed, the list shows files in the current Agent workspace =====
// Searching is done by App.vue calling the backend API (results come back via ctx.fileSearchResults); this only handles prefix detection and rendering.
const FILE_PREFIX = /^\s*f>\s*/i
const isFileMode = computed(() => FILE_PREFIX.test(query.value))
const fileQuery = computed(() => query.value.replace(FILE_PREFIX, ''))

const placeholder = computed(() => {
  if (isAgentMode.value) return 'Search Agents…'
  if (isFileMode.value) return 'Search files…'
  return props.title
})

const emptyText = computed(() => {
  if (isAgentMode.value) return 'No matching Agents'
  if (isFileMode.value) {
    if (props.ctx?.fileSearchLoading) return 'Searching…'
    if (props.ctx?.fileSearchError) return props.ctx.fileSearchError
    if (!fileQuery.value.trim()) return 'Type a file name to search the current Agent workspace'
    return 'No matching files'
  }
  return 'No matching commands'
})

// Agent icons: distinguished only by type (code_agent / regular agent), consistent with the lobby/tree-node convention,
// all 16x16 stroke line SVGs (currentColor inherits the color).
// Running state is distinguished by color (see agentEntries' statusClass and the .cmd-item-ico color styles).
// Agent meta icons (command palette meta labels): 16x16 stroke line SVGs (currentColor inherits the color)
const COMMAND_META_ICONS = {
  monitor: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2.5" width="12" height="8.5" rx="1.5"/><path d="M6 13.5h4M8 11v2.5"/></svg>',
  proxy: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="4" cy="4" r="1.8"/><circle cx="12" cy="4" r="1.8"/><circle cx="8" cy="12" r="1.8"/><path d="M5.5 5 7 10.5M10.5 5 9 10.5M5.5 4h5"/></svg>',
  brain: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2.5a2 2 0 0 0-2 2v.5a2 2 0 0 0-2 2 2 2 0 0 0-1 1.7 2 2 0 0 0 1 1.7 2 2 0 0 0 2 2v.6a2 2 0 0 0 4 0v-.6a2 2 0 0 0 2-2 2 2 0 0 0 1-1.7 2 2 0 0 0-1-1.7 2 2 0 0 0-2-2V4.5a2 2 0 0 0-2-2z"/><path d="M8 2.5v11"/></svg>',
  bolt: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 1.5 3 9h4l-1 5.5 6-7.5H8z"/></svg>',
  leaf: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 13C3 6 7 2.5 13 2.5c.5 5-2 9.5-8 10.5z"/><path d="M3 13c2-3 5-5.5 8-7"/></svg>',
  folder: '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 4.5v7a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H8.2L6.7 4.5H2.5a1 1 0 0 0-1 1z"/></svg>',
  file: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 2.5h7l3 3v8a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1z"/><path d="M10 2.5v3h3"/></svg>',
}
const AGENT_ICON_SVG = {
  code: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5.5 4.5 2.5 8l3 3.5M10.5 4.5l3 3.5-3 3.5"/><path d="M9.5 3.5l-3 9"/></svg>',
  agent: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="10" height="7" rx="2"/><circle cx="5.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/><circle cx="10.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/><path d="M6 3.5 8 5l2-1.5"/><path d="M5 12v1.5M11 12v1.5"/><path d="M3 10H1.5M14.5 10H13"/></svg>'
}
function agentTypeIcon(agent) {
  return agent?.agent_type === 'code_agent' ? AGENT_ICON_SVG.code : AGENT_ICON_SVG.agent
}

// Convert the Agent list into action objects, reusing the command palette's rendering and keyboard navigation
const agentEntries = computed(() => {
  const ctx = props.ctx || {}
  const list = Array.isArray(ctx.agentList) ? ctx.agentList : []
  const opened = ctx.openedAgentIds instanceof Set ? ctx.openedAgentIds : new Set()
  const q = agentQuery.value.trim().toLowerCase()
  const isOpened = agent => opened.has(agent?.agent_id)
  // Running: agent.status is not stopped (consistent with the lobby/status-icon check)
  const isRunning = agent => !!agent && agent.status !== 'stopped'
  return list
    .filter(agent => {
      if (!q) return true
      const nodeLabel = typeof ctx.getAgentNodeLabel === 'function' ? ctx.getAgentNodeLabel(agent) : ''
      const haystack = [agent?.name, agent?.agent_id, nodeLabel].filter(Boolean).join(' ').toLowerCase()
      return haystack.includes(q)
    })
    // Running Agents come first; then ones with an open panel come first; the rest keep their original order
    .sort((a, b) => {
      const runningDiff = (isRunning(b) ? 1 : 0) - (isRunning(a) ? 1 : 0)
      if (runningDiff !== 0) return runningDiff
      return (isOpened(b) ? 1 : 0) - (isOpened(a) ? 1 : 0)
    })
    .map(agent => {
      const nodeLabel = typeof ctx.getAgentNodeLabel === 'function' ? ctx.getAgentNodeLabel(agent) : ''
      const metaParts = []
      if (nodeLabel) metaParts.push({ icon: COMMAND_META_ICONS.monitor, text: nodeLabel })
      if (agent?.proxy_node) metaParts.push({ icon: COMMAND_META_ICONS.proxy, text: `Proxy ${agent.proxy_node}` })
      if (agent?.llm_group) metaParts.push({ icon: COMMAND_META_ICONS.brain, text: agent.llm_group })
      if (agent?.quick_mode) metaParts.push({ icon: COMMAND_META_ICONS.bolt, text: 'Turbo' })
      if (agent?.worktree) metaParts.push({ icon: COMMAND_META_ICONS.leaf, text: 'worktree' })
      if (agent?.working_dir) metaParts.push({ icon: COMMAND_META_ICONS.folder, text: agent.working_dir })
      return {
        id: `agent-switch:${agent.agent_id}`,
        label: agent?.name || agent?.agent_id,
        en: agent?.agent_id,
        group: 'Switch Agent',
        icon: agentTypeIcon(agent),
        // Running state: used for icon color distinction (running dark green / not running dark red), consistent with the isRunning used for sorting
        statusClass: isRunning(agent) ? 'running' : 'stopped',
        keywords: [nodeLabel],
        meta: metaParts.length ? metaParts : undefined,
        // All Agents are selectable: visible ones are switched to (activated), invisible ones get a Panel created and opened in the current area.
        // So they are not grayed out - even selecting the current Agent itself is meaningful (switches focus back to its session).
        disabled: false,
        isAgentEntry: true,
        run: (c, openMode) => c.switchToAgent && c.switchToAgent(agent, openMode),
      }
    })
})

// File entries: mapped from the backend fuzzy-search results (ctx.fileSearchResults) called by App.vue,
// reusing the command palette's rendering and keyboard navigation. Results contain only files, not rules/custom commands.
const fileEntries = computed(() => {
  const ctx = props.ctx || {}
  const list = Array.isArray(ctx.fileSearchResults) ? ctx.fileSearchResults : []
  return list.map(item => {
    const filePath = item?.file_path || ''
    const name = item?.name || filePath.split('/').pop() || filePath
    return {
      id: `file-open:${filePath}`,
      label: name,
      group: 'Files',
      icon: COMMAND_META_ICONS.file,
      keywords: [filePath],
      meta: filePath,
      isFileEntry: true,
      run: c => c.openFileResult && c.openFileResult(item),
    }
  })
})

// "Recently used" entries: map recorded command ids to action objects; shown only when there is no search term and not in Agent mode
const recentActions = computed(() => {
  if (isAgentMode.value || isFileMode.value || query.value.trim()) return []
  const byId = new Map((props.actions || []).map(a => [a.id, a]))
  return recentIds.value.map(id => byId.get(id)).filter(Boolean)
})

// Filter + flatten (use a continuous index for keyboard navigation, decoupled from grouped display)
const flatEntries = computed(() => {
  let flatIndex = 0
  const matched = isAgentMode.value
    ? agentEntries.value
    : isFileMode.value
      ? fileEntries.value
      : filterActions(props.actions, query.value)
  // Pin recently used entries to the top (group marked as "Recently used" and aggregated by groupActions into the topmost group), and remove them from the regular list to avoid duplicates
  const recentIdSet = new Set(recentActions.value.map(a => a.id))
  const recentEntries = recentActions.value.map(action => ({
    action: { ...action, group: 'Recently used' },
    disabled: isDisabled(action),
    flatIndex: flatIndex++,
  }))
  const restEntries = matched
    .filter(action => !recentIdSet.has(action.id))
    .map(action => ({
      action,
      disabled: isDisabled(action),
      flatIndex: flatIndex++,
    }))
  return isAgentMode.value || isFileMode.value ? restEntries : [...recentEntries, ...restEntries]
})

const entryById = computed(() => new Map(flatEntries.value.map(e => [e.action.id, e])))

// Organize by group; elements reference flat entries (keeping flatIndex)
const groups = computed(() =>
  groupActions(flatEntries.value.map(e => e.action)).map(g => ({
    group: g.group,
    actions: g.actions.map(a => entryById.value.get(a.id)).filter(Boolean),
  }))
)

function setItemRef(el, index) {
  if (el) itemRefs.set(index, el)
  else itemRefs.delete(index)
}

function move(delta) {
  const total = flatEntries.value.length
  if (total === 0) return
  let next = activeIndex.value
  for (let i = 0; i < total; i++) {
    next = (next + delta + total) % total
    if (!flatEntries.value[next]?.disabled) break
  }
  activeIndex.value = next
  scrollActiveIntoView()
}

function scrollActiveIntoView() {
  nextTick(() => {
    const el = itemRefs.get(activeIndex.value)
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest' })
    }
  })
}

function onItemHover(index) {
  activeIndex.value = index
}

function run(action, openMode = 'current') {
  if (!action || isDisabled(action)) return
  // Agent / file entries are not commands and are not recorded in "Recently used"
  if (!action.isAgentEntry && !action.isFileEntry) recordRecent(action.id)
  emit('run', action, openMode)
}

function close() {
  emit('update:visible', false)
  emit('close')
}

// Global Escape: whether focus is in the input or elsewhere in the panel, a single Esc closes it.
// Use the window capture phase to ensure it is handled before other keydowns and is unaffected by overlay @keydown.stop.
function handleGlobalEscape(event) {
  if (!props.visible) return
  if (event.key === 'Escape' || event.code === 'Escape' || event.keyCode === 27) {
    event.preventDefault()
    event.stopPropagation()
    close()
  }
}

onMounted(() => window.addEventListener('keydown', handleGlobalEscape, true))
onBeforeUnmount(() => window.removeEventListener('keydown', handleGlobalEscape, true))

// Input blur: some IMEs/browsers do not dispatch keydown when Esc is pressed while the input is focused,
// only triggering blur (which users perceive as "the first Esc makes focus disappear"). So we close when focus actually leaves the panel,
// ensuring a single Esc closes it. Check at the end of the event loop to avoid closing accidentally when clicking an option inside the panel.
function onInputBlur() {
  setTimeout(() => {
    if (!props.visible) return
    const overlay = document.querySelector('.cmd-overlay')
    const active = document.activeElement
    if (overlay && active && overlay.contains(active)) return
    close()
  }, 0)
}

function onInputKeydown(event) {
  // With Ctrl/Alt/Meta modifiers, hand off to global shortcuts and do not do list navigation
  if (event.ctrlKey || event.altKey || event.metaKey) return
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const entry = flatEntries.value[activeIndex.value]
    if (entry && !entry.disabled) run(entry.action, 'current')
  } else if (event.key === 'Tab' && isAgentMode.value) {
    // Agent mode: Tab opens in a new Panel
    event.preventDefault()
    const entry = flatEntries.value[activeIndex.value]
    if (entry && !entry.disabled) run(entry.action, 'new')
  } else if (event.key === 'Escape') {
    event.preventDefault()
    close()
  }
}

watch(
  () => props.visible,
  visible => {
    if (visible) {
      query.value = props.initialQuery || ''
      activeIndex.value = 0
      itemRefs.clear()
      nextTick(() => inputEl.value?.focus())
    } else {
      itemRefs.clear()
    }
  },
  { immediate: true }
)

watch(query, () => {
  activeIndex.value = 0
  // File mode: search as you type (backend fuzzy search called by App.vue); clear results when leaving file mode
  if (isFileMode.value) {
    if (typeof props.ctx?.searchWorkspaceFiles === 'function') {
      props.ctx.searchWorkspaceFiles(fileQuery.value)
    }
  } else if (typeof props.ctx?.clearWorkspaceFileSearch === 'function') {
    props.ctx.clearWorkspaceFileSearch()
  }
})

defineExpose({ focus: () => inputEl.value?.focus() })
</script>

<style scoped>
.cmd-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 12vh;
  background: rgba(4, 8, 16, 0.55);
  backdrop-filter: blur(2px);
}

.cmd-panel {
  width: min(560px, 92vw);
  max-height: 62vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius, 10px);
  box-shadow: var(--tile-shadow, 0 8px 30px rgba(0, 120, 190, 0.25));
  overflow: hidden;
}

.cmd-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border-subtle);
}

.cmd-search-ico {
  color: var(--color-accent);
  font-size: 14px;
  opacity: 0.85;
}

.cmd-input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text-primary);
  font-size: 14px;
  font-family: inherit;
}

.cmd-input::placeholder {
  color: var(--color-text-secondary);
}

.cmd-esc-hint {
  font-size: 10px;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: 4px;
  padding: 1px 5px;
  opacity: 0.8;
}

.cmd-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.cmd-group-title {
  padding: 6px 8px 2px;
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
  opacity: 0.75;
}

.cmd-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  background: transparent;
  border: none;
  border-radius: var(--tile-radius-sm, 6px);
  color: var(--color-text-primary);
  font-size: 13px;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
}

.cmd-item.is-active {
  background: var(--color-bg-hover);
  box-shadow: inset 0 0 0 1px rgba(32, 200, 255, 0.35);
}

.cmd-item.is-disabled {
  color: var(--color-text-secondary);
  opacity: 0.45;
  cursor: not-allowed;
}

.cmd-item-ico {
  width: 18px;
  text-align: center;
  font-size: 14px;
  flex: none;
}

/* Overall color distinction for Agent running state: running dark green, not running dark red (applies to the entire list item text,
   including the title and meta/en subtext, to avoid being overridden by the secondary colors of .cmd-item-meta/.cmd-item-en) */
.cmd-item.agent-running,
.cmd-item.agent-running .cmd-item-meta,
.cmd-item.agent-running .cmd-item-en {
  color: #4a9a6a;
}

.cmd-item.agent-stopped,
.cmd-item.agent-stopped .cmd-item-meta,
.cmd-item.agent-stopped .cmd-item-en {
  color: #b0574f;
}

.cmd-item-label {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.cmd-item-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cmd-item-meta {
  font-size: 11px;
  color: var(--color-text-secondary);
  opacity: 0.8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cmd-item-en {
  margin-left: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
  opacity: 0.7;
}

.cmd-item-shortcut {
  font-size: 10px;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: 4px;
  padding: 1px 5px;
  flex: none;
}

.cmd-empty {
  padding: 24px 12px;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.cmd-footer {
  display: flex;
  gap: 14px;
  padding: 7px 12px;
  border-top: 1px solid var(--color-border-subtle);
  font-size: 11px;
  color: var(--color-text-secondary);
}

.cmd-footer b {
  color: var(--color-text-primary);
  font-weight: 600;
}

.cmd-fade-enter-active,
.cmd-fade-leave-active {
  transition: opacity 0.14s ease;
}

.cmd-fade-enter-from,
.cmd-fade-leave-to {
  opacity: 0;
}
</style>
