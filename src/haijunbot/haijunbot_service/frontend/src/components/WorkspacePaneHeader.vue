<template>
  <!-- Workspace pane title bar: rendered by each leaf when split, or by App.vue for the single pane when not split.
       Unifies title/status/split/close buttons in both cases to avoid the "no split entry when unsplit" inconsistency. -->
  <div class="workspace-pane-leaf-header">
    <span class="workspace-pane-leaf-title">{{ getTitle ? getTitle(node) : (node.view === 'session' ? 'Session' : 'Files') }}</span>
    <span v-if="getStatus && getStatus(node)" class="workspace-pane-leaf-status">{{ getStatus(node) }}</span>
    <div class="workspace-pane-leaf-actions">
      <button
        v-if="canMaximize"
        tabindex="-1"
        class="workspace-pane-leaf-btn"
        :title="maximized ? 'Restore pane' : 'Maximize pane'"
        @mousedown.prevent
        @click.stop="$emit('maximize', node.id)"
      >{{ maximized ? '⤡' : '⛶' }}</button>
      <button v-if="canSplit" tabindex="-1" class="workspace-pane-leaf-btn" title="Split horizontally" @mousedown.prevent @click.stop="$emit('split', node.id, 'row')">◫</button>
      <button v-if="canSplit" tabindex="-1" class="workspace-pane-leaf-btn" title="Split vertically" @mousedown.prevent @click.stop="$emit('split', node.id, 'column')">⬓</button>
      <button
        v-if="canClose"
        tabindex="-1"
        class="workspace-pane-leaf-btn"
        title="Close this pane"
        @mousedown.prevent
        @click.stop="$emit('close', node.id)"
      >✕</button>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  canSplit: { type: Boolean, default: true },
  canClose: { type: Boolean, default: true },
  canMaximize: { type: Boolean, default: true },
  maximized: { type: Boolean, default: false },
  getTitle: { type: Function, default: null },
  getStatus: { type: Function, default: null },
})

defineEmits(['split', 'close', 'maximize'])
</script>

<style scoped>
.workspace-pane-leaf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 8px;
  min-height: 24px;
  background: var(--color-bg-primary);
  border-bottom: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.workspace-pane-leaf-title {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.workspace-pane-leaf-status {
  margin-left: auto;
  margin-right: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workspace-pane-leaf-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.workspace-pane-leaf-btn {
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 3px;
}

.workspace-pane-leaf-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}
</style>
