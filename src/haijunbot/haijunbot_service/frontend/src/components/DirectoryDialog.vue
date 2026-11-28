<template>
  <div :class="embedded ? 'dir-modal-embedded' : 'palette-overlay'" v-if="visible">
    <div class="palette-panel dir-modal" :class="{ embedded }">
      <div class="dir-modal-header" v-if="!embedded">
        <h2>{{ title }}</h2>
        <button class="dir-close-btn" @click="$emit('cancel')">×</button>
      </div>
      <div class="path-header">
        <button class="path-btn" @click="$emit('refresh', currentPath)"><span v-html="DIR_ICONS.refresh"></span> Refresh</button>
        <button class="path-btn" @click="$emit('go-parent')"><span v-html="DIR_ICONS.up"></span></button>
      </div>
      <div class="current-path">{{ currentPath }}</div>
      <div class="dir-search">
        <input
          ref="searchInput"
          :value="searchText"
          @input="$emit('update:searchText', $event.target.value)"
          type="text"
          class="dir-search-input"
          placeholder="Search directory..."
          @keydown="onSearchKeydown"
        />
      </div>
      <div class="dir-list" ref="dirListRef" v-if="filteredDirs.length > 0 || (fileSelectable && fileList.length > 0)">
        <div
          v-for="dir in filteredDirs"
          :key="dir.path"
          class="dir-item"
          :class="{ selected: selectedDir === dir.path }"
          @click="$emit('select', dir.path); $emit('enter', dir.path, false)"
        >
          <div class="dir-icon" v-html="DIR_ICONS.folder"></div>
          <div class="dir-name">{{ dir.name }}</div>
          <div class="dir-path">{{ dir.path }}</div>
        </div>
        <!-- file items (rendered only in fileSelectable mode, e.g. picking an orchestration file) -->
        <div
          v-for="file in (fileSelectable ? fileList : [])"
          :key="file.path"
          class="dir-item file-item"
          :class="{ selected: selectedFile === file.path }"
          @click="$emit('select-file', file.path)"
        >
          <div class="dir-icon" v-html="fileIcon"></div>
          <div class="dir-name">{{ file.name }}</div>
          <div class="dir-path">{{ file.path }}</div>
        </div>
      </div>
      <div class="empty-state" v-else>
        <p>{{ fileSelectable ? 'No subdirectories or files in this directory' : 'No subdirectories in this directory' }}</p>
      </div>
      <div class="dir-modal-actions" v-if="!embedded">
        <button class="btn secondary" @click="$emit('cancel')">Cancel</button>
        <button class="btn primary" @click="$emit('confirm')">Confirm</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

// Hand-drawn 16x16 stroke line SVG icons (currentColor inherits the theme color), consistent with the global style
const DIR_ICONS = {
  refresh: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 8a5 5 0 1 1-1.5-3.5M13 2.5V6h-3.5"/></svg>',
  up: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 12.5v-9M3.5 8 8 3.5 12.5 8"/></svg>',
  folder: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 4.5v7a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H8.2L6.7 4.5H2.5a1 1 0 0 0-1 1z"/></svg>',
  file: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 2.5h7l3 3v8a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1z"/><path d="M10 2.5v3h3M5.5 8h5M5.5 10.5h5"/></svg>',
}
const props = defineProps({
  visible: Boolean,
  currentPath: String,
  selectedDir: String,
  searchText: String,
  // embedded mode: no overlay or title bar; the outer container hosts it (reuses the same directory filter UI for "Open Directory")
  embedded: {
    type: Boolean,
    default: false
  },
  // title (only shown in non-embedded mode)
  title: {
    type: String,
    default: 'Select Working Directory'
  },
  filteredDirs: {
    type: Array,
    default: () => []
  },
  // file selection mode: when true, renders the file items from fileList below the directory list (e.g. picking an orchestration file)
  fileSelectable: {
    type: Boolean,
    default: false
  },
  // file list (only rendered when fileSelectable is true); each item has name/path
  fileList: {
    type: Array,
    default: () => []
  },
  // selected file path (for highlighting)
  selectedFile: {
    type: String,
    default: ''
  },
  // file item icon
  fileIcon: {
    type: String,
    default: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 2.5h7l3 3v8a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1z"/><path d="M10 2.5v3h3M5.5 8h5M5.5 10.5h5"/></svg>'
  }
})


const emit = defineEmits(['update:visible', 'update:searchText', 'cancel', 'confirm', 'refresh', 'go-parent', 'select', 'enter', 'search-keydown', 'select-file'])

// Directory search box keydown handler: stop propagation to document so it does not
// trigger the global Enter listener that creates the Agent modal (the same event that
// confirms and closes this dialog, if it bubbles, would wrongly trigger creation once
// dirDialogOpen is already false)
function onSearchKeydown(event) {
  event.stopPropagation()
  emit('search-keydown', event)
}

const searchInput = ref(null)
const dirListRef = ref(null)

watch(() => props.visible, (newVal) => {
  if (newVal) {
    setTimeout(() => {
      searchInput.value?.focus()
    }, 100)
  }
})

// expose refs for parent components
defineExpose({
  searchInput,
  dirListRef
})
</script>

<style scoped>
.palette-overlay {
  position: fixed;
  inset: 0;
  background: rgba(4, 8, 16, 0.55);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 3000;
  padding: 12vh 20px 20px;
}

.palette-panel {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius);
  box-shadow: var(--tile-shadow, 0 8px 30px rgba(0, 120, 190, 0.25));
  overflow: hidden;
  width: 100%;
}

.dir-modal {
  max-width: 700px;
  width: 95%;
  max-height: 72vh;
  display: flex;
  flex-direction: column;
}

/* embedded mode: no fullscreen, no overlay; fills the outer container (reuses the directory filter UI for "Open Directory") */
.dir-modal-embedded {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.dir-modal.embedded {
  max-width: none;
  width: 100%;
  max-height: none;
  flex: 1;
  min-height: 0;
  border: none;
  border-radius: var(--tile-radius-sm, 4px);
  box-shadow: none;
}

.dir-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border-subtle);
}

.dir-modal-header h2 {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-primary);
  font-weight: 600;
}

.dir-close-btn {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.dir-close-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
}

.path-header {
  display: flex;
  gap: 8px;
  padding: 8px 12px 0;
}

.path-btn {
  flex: 1;
  padding: 6px 10px;
  background: transparent;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius-sm);
  font-size: 12px;
  cursor: pointer;
}

.path-btn:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
}

.current-path {
  margin: 8px 12px 0;
  padding: 7px 10px;
  background: var(--color-bg-primary);
  border-radius: var(--tile-radius-sm);
  font-family: 'Consolas', 'Microsoft YaHei', monospace;
  font-size: 12px;
  color: var(--color-text-secondary);
  word-break: break-all;
  line-height: 1.4;
}

.dir-search {
  padding: 8px 12px;
}

.dir-search-input {
  width: 100%;
  padding: 7px 10px;
  background: transparent;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius-sm);
  color: var(--color-text-primary);
  font-size: 13px;
  font-family: inherit;
}

.dir-search-input:focus {
  outline: none;
  border-color: rgba(32, 200, 255, 0.35);
}

.dir-search-input::placeholder {
  color: var(--color-text-secondary);
}

.dir-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px;
}

.dir-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  cursor: pointer;
  border-radius: var(--tile-radius-sm);
  color: var(--color-text-primary);
  font-size: 13px;
}

.dir-item:hover {
  background: var(--color-bg-hover);
}

.dir-item.selected {
  background: var(--color-bg-hover);
  box-shadow: inset 0 0 0 1px rgba(32, 200, 255, 0.35);
}

.dir-item.selected:hover {
  background: var(--color-bg-hover);
}

/* file items: distinguished from directory items (file icon, secondary color for the name) */
.file-item .dir-name {
  font-weight: 400;
  color: var(--color-text-secondary);
}

.dir-icon {
  font-size: 14px;
  width: 18px;
  text-align: center;
  flex: none;
}

.dir-name {
  font-size: 13px;
  color: var(--color-text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dir-path {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-left: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 55%;
}

.empty-state {
  text-align: center;
  padding: 24px 12px;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.dir-modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 10px 12px;
  border-top: 1px solid var(--color-border-subtle);
}

.btn {
  padding: 7px 16px;
  border: none;
  border-radius: var(--tile-radius-sm);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.btn.secondary {
  background: transparent;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-subtle);
}

.btn.secondary:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.btn.primary {
  background: var(--color-accent);
  color: #060911;
}

.btn.primary:hover {
  background: var(--color-accent);
  filter: brightness(1.08);
}
</style>