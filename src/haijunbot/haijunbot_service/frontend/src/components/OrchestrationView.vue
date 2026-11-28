<!-- Pipeline orchestration DAG visualization view (hand-drawn SVG, pure frontend rendering).
     - compact mode: embedded in the sidebar (narrow)
     - full mode: large overlay (wide)
     Both share the same rendering logic, differing only in size/density. -->
<template>
  <div
    class="orch-view"
    :class="mode === 'full' ? 'is-full' : 'is-compact'"
  >
    <!-- compact mode: the sidebar only holds the list; clicking an item opens the large overlay to view the DAG -->
    <div
      v-if="mode === 'compact'"
      class="orch-list"
    >
      <div
        v-if="!pipelines.length"
        class="orch-empty"
      >
        <svg
          width="42"
          height="42"
          viewBox="0 0 24 24"
          fill="none"
          opacity="0.5"
        >
          <circle
            cx="5"
            cy="6"
            r="2.2"
            stroke="currentColor"
            stroke-width="1.3"
          />
          <circle
            cx="19"
            cy="6"
            r="2.2"
            stroke="currentColor"
            stroke-width="1.3"
          />
          <circle
            cx="12"
            cy="18"
            r="2.2"
            stroke="currentColor"
            stroke-width="1.3"
          />
          <path
            d="M6.5 7.5 10.6 16M17.5 7.5 13.4 16M7 6h10"
            stroke="currentColor"
            stroke-width="1.3"
            stroke-linecap="round"
          />
        </svg>
        <div class="orch-empty-title">
          No orchestration flows
        </div>
        <div class="orch-empty-sub">
          Run a pipeline with a flow and its DAG progress will be shown here in real time
        </div>
      </div>
      <button
        v-for="p in pipelines"
        :key="p.pipelineId"
        class="orch-list-item"
        :class="{ active: p.pipelineId === activeId }"
        :title="p.orchestrationFile"
        @click="openFromList(p)"
      >
        <span
          class="orch-tab-dot"
          :class="'fin-' + p.finalStatus"
        />
        <span class="orch-list-main">
          <span class="orch-list-row1">
            <span class="orch-list-name">{{ shortName(p) }}</span>
            <span class="orch-list-meta">{{ listMeta(p) }}</span>
          </span>
          <span class="orch-list-row2">
            <span class="orch-list-dir" :title="p.workingDir">{{ p.workingDir || '—' }}</span>
            <span class="orch-list-time">{{ fmtTime(p.startedAt) }}</span>
          </span>
        </span>
        <span
          class="orch-list-del"
          title="Delete this pipeline record"
          @click.stop="removeFromList(p)"
        >✕</span>
      </button>
    </div>

    <!-- full mode: top Tab for switching between multiple flows + large DAG -->
    <template v-else>
      <div
        v-if="pipelines.length"
        class="orch-tabs"
      >
        <button
          v-for="p in pipelines"
          :key="p.pipelineId"
          class="orch-tab"
          :class="{ active: p.pipelineId === activeId }"
          :title="p.orchestrationFile"
          @click="$emit('select', p.pipelineId)"
        >
          <span
            class="orch-tab-dot"
            :class="'fin-' + p.finalStatus"
          />
          <span class="orch-tab-name">{{ shortName(p) }}</span>
        </button>
      </div>

      <!-- Empty state -->
      <div
        v-if="!active"
        class="orch-empty"
      >
        <svg
          width="42"
          height="42"
          viewBox="0 0 24 24"
          fill="none"
          opacity="0.5"
        >
          <circle
            cx="5"
            cy="6"
            r="2.2"
            stroke="currentColor"
            stroke-width="1.3"
          />
          <circle
            cx="19"
            cy="6"
            r="2.2"
            stroke="currentColor"
            stroke-width="1.3"
          />
          <circle
            cx="12"
            cy="18"
            r="2.2"
            stroke="currentColor"
            stroke-width="1.3"
          />
          <path
            d="M6.5 7.5 10.6 16M17.5 7.5 13.4 16M7 6h10"
            stroke="currentColor"
            stroke-width="1.3"
            stroke-linecap="round"
          />
        </svg>
        <div class="orch-empty-title">
          No orchestration flows
        </div>
        <div class="orch-empty-sub">
          Run a pipeline with a flow and its DAG progress will be shown here in real time
        </div>
      </div>

      <template v-else>
        <!-- Stats cards -->
        <div class="orch-stats">
          <div
            class="orch-stat"
            :style="{ '--c': STATUS_COLORS.running }"
          >
            <span class="orch-stat-v">{{ statCounts.running }}</span>
            <span class="orch-stat-l">Running</span>
          </div>
          <div
            class="orch-stat"
            :style="{ '--c': STATUS_COLORS.completed }"
          >
            <span class="orch-stat-v">{{ statCounts.completed }}</span>
            <span class="orch-stat-l">Completed</span>
          </div>
          <div
            class="orch-stat"
            :style="{ '--c': STATUS_COLORS.failed }"
          >
            <span class="orch-stat-v">{{ statCounts.failed }}</span>
            <span class="orch-stat-l">Failed</span>
          </div>
          <div
            class="orch-stat"
            :style="{ '--c': STATUS_COLORS.skipped }"
          >
            <span class="orch-stat-v">{{ statCounts.skipped }}</span>
            <span class="orch-stat-l">Skipped</span>
          </div>
          <div
            class="orch-stat orch-stat-wide"
            :style="{ '--c': '#7f8ea3' }"
          >
            <span class="orch-stat-v">{{ elapsedText }}</span>
            <span class="orch-stat-l">Elapsed · Parallel {{ active.maxWorkers || 1 }}</span>
          </div>
        </div>

        <!-- Gate approval overlay (shown in full mode when gate_blocked) -->
        <div
          v-if="isGateBlocked"
          class="orch-approval"
        >
          <div class="orch-approval-head">
            <span class="orch-approval-title">⛔ Gate awaiting approval</span>
            <span class="orch-approval-stage">Stage: {{ active.gateStage || '—' }}</span>
          </div>
          <div
            v-if="active.approvalPath"
            class="orch-approval-path"
            :title="active.approvalPath"
          >
            Approval report: {{ active.approvalPath }}
          </div>
          <textarea
            v-model="approvalNote"
            class="orch-approval-note"
            rows="2"
            placeholder="Approval note (optional)"
          />
          <div class="orch-approval-actions">
            <button
              class="orch-btn is-approve"
              :disabled="approvalBusy"
              @click="submitApproval('approve')"
            >✓ Approve</button>
            <button
              class="orch-btn is-reject"
              :disabled="approvalBusy"
              @click="submitApproval('reject')"
            >✕ Reject</button>
            <button
              class="orch-btn is-retry"
              :disabled="approvalBusy"
              @click="submitApproval('retry')"
            >↻ Retry</button>
          </div>
          <div
            v-if="approvalLog.length"
            class="orch-approval-log"
          >
            <div class="orch-approval-log-title">
              Approval log
            </div>
            <div
              v-for="(a, i) in approvalLog"
              :key="i"
              class="orch-approval-item"
            >
              <span class="orch-approval-act" :class="'act-' + a.action">{{ approvalActionLabel(a.action) }}</span>
              <span class="orch-approval-who">{{ a.approver || 'System' }}</span>
              <span
                v-if="a.note"
                class="orch-approval-note-text"
                :title="a.note"
              >{{ a.note }}</span>
              <span class="orch-approval-time">{{ fmtApprovalTime(a.ts) }}</span>
            </div>
          </div>
        </div>

        <!-- DAG canvas -->
        <div
          class="orch-canvas"
          @mouseleave="hoverStage = ''"
        >
          <svg
            :viewBox="`0 0 ${layout.width} ${layout.height}`"
            :width="layout.width"
            :height="layout.height"
            class="orch-svg"
          >
            <defs>
              <filter
                id="orch-glow"
                x="-60%"
                y="-60%"
                width="220%"
                height="220%"
              >
                <feGaussianBlur
                  stdDeviation="2.4"
                  result="b"
                />
                <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
              <marker
                id="orch-arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path
                  d="M0 0 L10 5 L0 10 z"
                  fill="rgba(120,150,190,0.7)"
                />
              </marker>
              <linearGradient
                id="orch-edge-flow"
                x1="0"
                y1="0"
                x2="1"
                y2="0"
              >
                <stop
                  offset="0%"
                  stop-color="rgba(32,200,255,0)"
                />
                <stop
                  offset="50%"
                  stop-color="rgba(32,200,255,0.9)"
                />
                <stop
                  offset="100%"
                  stop-color="rgba(32,200,255,0)"
                />
              </linearGradient>
            </defs>

            <!-- Edges -->
            <g class="orch-edges">
              <path
                v-for="(e, i) in layout.edges"
                :key="'E' + i"
                :d="edgePath(layout.positions[e.from], layout.positions[e.to])"
                class="orch-edge"
                :class="{ 'is-flow': edgeFlowing(e) }"
                fill="none"
                marker-end="url(#orch-arrow)"
              />
            </g>

            <!-- Nodes -->
            <g
              v-for="n in nodes"
              :key="n.stage"
              class="orch-node"
              :class="['st-' + n.status, { 'is-gate': n.gate, 'is-loop': n.kind === 'loop', 'is-hover': hoverStage === n.stage, 'is-clickable': !!n.agentId }]"
              :transform="`translate(${layout.positions[n.stage].x},${layout.positions[n.stage].y})`"
              @mouseenter="hoverStage = n.stage"
              @click="onNodeClick(n)"
            >
              <rect
                class="orch-node-bg"
                :width="NODE_W"
                :height="NODE_H"
                rx="10"
                :filter="n.status === 'running' ? 'url(#orch-glow)' : ''"
              />
              <rect
                class="orch-node-accent"
                x="0"
                y="0"
                width="4"
                :height="NODE_H"
                rx="2"
              />
              <text
                class="orch-node-stage"
                x="14"
                y="24"
              >{{ n.stage }}</text>
              <text
                class="orch-node-agent"
                x="14"
                y="42"
              >{{ n.agent }}</text>
              <text
                v-if="n.gate"
                class="orch-node-gate"
                :x="NODE_W - 12"
                y="24"
                text-anchor="end"
              >🚧</text>
              <text
                v-if="n.kind === 'loop'"
                class="orch-node-loop"
                :x="NODE_W - 12"
                y="24"
                text-anchor="end"
              >🔁</text>
              <text
                v-if="n.kind === 'loop' && n.maxIterations"
                class="orch-node-loop-iter"
                :x="NODE_W - 12"
                y="42"
                text-anchor="end"
              >{{ n.iteration || 0 }}/{{ n.maxIterations }}</text>
              <text
                v-if="n.retryCount"
                class="orch-node-retry"
                :x="NODE_W - 12"
                y="42"
                text-anchor="end"
              >↻{{ n.retryCount }}</text>
              <circle
                v-if="n.status === 'running'"
                class="orch-node-pulse"
                :cx="NODE_W - 16"
                cy="14"
                r="4"
              />
            </g>
          </svg>

          <!-- hover details -->
          <div
            v-if="hoverNode"
            class="orch-tip"
            :style="tipStyle"
          >
            <div class="orch-tip-stage">
              {{ hoverNode.stage }}
            </div>
            <div class="orch-tip-row">
              <span>Agent</span><b>{{ hoverNode.agent }}</b>
            </div>
            <div class="orch-tip-row">
              <span>Status</span><b :style="{ color: statusColor(hoverNode.status) }">{{ statusLabel(hoverNode.status) }}</b>
            </div>
            <div
              v-if="hoverNode.output"
              class="orch-tip-row"
            >
              <span>Output</span><b>{{ hoverNode.output }}</b>
            </div>
            <div
              v-if="hoverNode.dependsOn.length"
              class="orch-tip-row"
            >
              <span>Depends on</span><b>{{ hoverNode.dependsOn.join(', ') }}</b>
            </div>
            <div
              v-if="hoverNode.error"
              class="orch-tip-row orch-tip-err"
            >
              <span>Error</span><b>{{ hoverNode.error }}</b>
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { layoutDag, edgePath as buildEdgePath, LAYOUT } from './dagLayout.js'

const props = defineProps({
  // [{ pipelineId, orchestrationFile, stages: Map, stageOrder: [], startedAt, finishedAt, finalStatus, maxWorkers, ... }]
  pipelines: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
  mode: { type: String, default: 'compact' }, // compact | full
})

const emit = defineEmits(['select', 'jump-agent', 'expand', 'remove', 'approve', 'reject', 'retry'])

const NODE_W = LAYOUT.NODE_W
const NODE_H = LAYOUT.NODE_H

const STATUS_COLORS = {
  pending: '#5a6b80',
  running: '#20c8ff',
  completed: '#37d67a',
  failed: '#ff5d6c',
  skipped: 'rgba(140,160,185,0.55)',
}

const hoverStage = ref('')

const active = computed(() => {
  if (!props.pipelines.length) return null
  return props.pipelines.find((p) => p.pipelineId === props.activeId) || props.pipelines[0]
})

const nodes = computed(() => {
  if (!active.value) return []
  const st = active.value
  const order = st.stageOrder && st.stageOrder.length ? st.stageOrder : [...st.stages.keys()]
  return order.map((s) => st.stages.get(s)).filter(Boolean)
})

const layout = computed(() => layoutDag(nodes.value))

const statCounts = computed(() => {
  const c = { running: 0, completed: 0, failed: 0, skipped: 0 }
  for (const n of nodes.value) {
    if (c[n.status] !== undefined) c[n.status] += 1
  }
  return c
})

const elapsedText = computed(() => {
  const st = active.value
  if (!st) return '—'
  const end = st.finishedAt || Date.now()
  const sec = Math.max(0, Math.round((end - st.startedAt) / 1000))
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}m${s}s`
})

const hoverNode = computed(() => nodes.value.find((n) => n.stage === hoverStage.value) || null)

const tipStyle = computed(() => {
  const n = hoverNode.value
  if (!n) return {}
  const pos = layout.value.positions[n.stage]
  return { left: `${pos.x + NODE_W + 10}px`, top: `${pos.y}px` }
})

function shortName(p) {
  const f = p.orchestrationFile || p.pipelineId
  const base = f.split('/').pop() || p.pipelineId
  return base.replace(/\.(ya?ml)$/, '')
}

function edgeFlowing(e) {
  const from = active.value?.stages.get(e.from)
  const to = active.value?.stages.get(e.to)
  return from?.status === 'completed' && (to?.status === 'running' || to?.status === 'pending')
}

function statusColor(s) {
  return STATUS_COLORS[s] || '#7f8ea3'
}

function statusLabel(s) {
  return { pending: 'Pending', running: 'Running', completed: 'Completed', failed: 'Failed', skipped: 'Skipped' }[s] || s
}

function edgePath(a, b) {
  if (!a || !b) return ''
  return buildEdgePath(a, b)
}

function onNodeClick(n) {
  if (n.agentId) emit('jump-agent', n.agentId)
}

// compact list: clicking an item selects that flow and opens the large overlay to view the DAG (the sidebar only holds the list; the graph is viewed in full in the overlay)
function openFromList(p) {
  emit('select', p.pipelineId)
  emit('expand')
}
// compact list: delete a record (the actual deletion is performed by the parent component)
function removeFromList(p) {
  emit('remove', p.pipelineId)
}
// List row secondary info: status + time
function listMeta(p) {
  const label = { preview: 'Preview', running: 'Running', completed: 'Completed', failed: 'Failed', gate_blocked: 'Awaiting approval' }[p.finalStatus] || 'Completed'
  if (p.finalStatus === 'preview') return label
  const end = p.finishedAt || Date.now()
  const sec = Math.max(0, Math.round((end - p.startedAt) / 1000))
  return `${label} · ${fmtDuration(sec)}`
}
// Format seconds into a readable duration (e.g. 90s / 3m20s / 1h5m)
function fmtDuration(sec) {
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return `${m}m${s}s`
  const h = Math.floor(m / 60)
  return `${h}h${m % 60}m`
}
// Format a timestamp as MM-DD HH:mm
function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ---- Gate approval overlay ----
const approvalNote = ref('')
const approvalBusy = ref(false)

// Show the approval overlay only in full mode when the current flow is gate_blocked (awaiting approval)
const isGateBlocked = computed(() => {
  if (props.mode !== 'full') return false
  return !!active.value && active.value.finalStatus === 'gate_blocked'
})

// Approval log: take the current flow's approvals (including pending/approve/reject/retry), newest first
const approvalLog = computed(() => {
  const st = active.value
  if (!st || !Array.isArray(st.approvals)) return []
  return [...st.approvals].sort((a, b) => (b.ts || 0) - (a.ts || 0))
})

function approvalActionLabel(action) {
  return { pending: 'Pending approval', approve: 'Approve', reject: 'Reject', retry: 'Retry' }[action] || action || '—'
}

function fmtApprovalTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// Submit an approval decision: hand the action and note to the parent component (which records to the backend and re-runs)
function submitApproval(action) {
  if (approvalBusy.value || !active.value) return
  const note = approvalNote.value.trim()
  emit(action, { pipelineId: active.value.pipelineId, note })
  approvalNote.value = ''
}
</script>

<style scoped>
.orch-view {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: linear-gradient(180deg, rgba(10, 16, 26, 0.96), rgba(6, 10, 18, 0.98));
  color: #d8e2f0;
  overflow: hidden;
}

/* compact list */
.orch-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.orch-list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(90, 120, 160, 0.22);
  background: rgba(18, 26, 40, 0.7);
  color: #9db0c8;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s;
}
.orch-list-item:hover { border-color: rgba(32, 200, 255, 0.5); color: #d8e2f0; }
.orch-list-item.active {
  border-color: rgba(32, 200, 255, 0.75);
  background: rgba(32, 200, 255, 0.12);
  color: #eaf6ff;
}
.orch-list-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.orch-list-row1 { display: flex; align-items: center; gap: 8px; min-width: 0; }
.orch-list-row2 { display: flex; align-items: center; gap: 8px; min-width: 0; }
.orch-list-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.orch-list-meta { font-size: 10px; color: #7f8ea3; flex: 0 0 auto; }
.orch-list-dir { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; color: #6b7d93; }
.orch-list-time { flex: 0 0 auto; font-size: 10px; color: #6b7d93; }
.orch-list-del {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 5px;
  color: #7f8ea3;
  font-size: 11px;
  opacity: 0;
  cursor: pointer;
  transition: all 0.15s;
}
.orch-list-item:hover .orch-list-del { opacity: 0.8; }
.orch-list-del:hover { opacity: 1 !important; color: #ff5d6c; background: rgba(255, 93, 108, 0.15); }

/* Tabs */
.orch-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(90, 120, 160, 0.22);
  overflow-x: auto;
  flex: 0 0 auto;
}
.orch-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid rgba(90, 120, 160, 0.28);
  background: rgba(20, 30, 46, 0.7);
  color: #9db0c8;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.orch-tab:hover { border-color: rgba(32, 200, 255, 0.5); color: #d8e2f0; }
.orch-tab.active {
  border-color: rgba(32, 200, 255, 0.75);
  background: rgba(32, 200, 255, 0.12);
  color: #eaf6ff;
  box-shadow: 0 0 12px rgba(32, 200, 255, 0.25);
}
.orch-tab-dot { width: 7px; height: 7px; border-radius: 50%; background: #5a6b80; flex: 0 0 auto; }
.orch-tab-dot.fin-completed { background: #37d67a; box-shadow: 0 0 6px #37d67a; }
.orch-tab-dot.fin-preview { background: #9db0c8; }
.orch-tab-dot.fin-failed { background: #ff5d6c; box-shadow: 0 0 6px #ff5d6c; }
.orch-tab-dot.fin-gate_blocked { background: #f0b429; box-shadow: 0 0 6px #f0b429; }
.orch-tab-dot.fin-running { background: #20c8ff; box-shadow: 0 0 6px #20c8ff; animation: orch-blink 1.2s ease-in-out infinite; }

/* Empty */
.orch-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #7f8ea3;
  padding: 24px;
  text-align: center;
}
.orch-empty-title { font-size: 14px; color: #9db0c8; }
.orch-empty-sub { font-size: 12px; opacity: 0.8; }

/* Stats */
.orch-stats {
  display: flex;
  gap: 8px;
  padding: 10px;
  flex: 0 0 auto;
  overflow-x: auto;
}
.orch-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 58px;
  padding: 6px 10px;
  border-radius: 10px;
  background: rgba(18, 26, 40, 0.8);
  border: 1px solid color-mix(in srgb, var(--c) 40%, transparent);
  box-shadow: inset 0 0 14px color-mix(in srgb, var(--c) 12%, transparent);
}
.orch-stat-v { font-size: 17px; font-weight: 600; color: var(--c); }
.orch-stat-l { font-size: 10px; color: #8b9cb3; white-space: nowrap; }
.orch-stat-wide { min-width: 96px; }

/* Canvas */
.orch-canvas {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 8px;
}
.orch-svg { display: block; }

/* Edges */
.orch-edge {
  stroke: rgba(120, 150, 190, 0.45);
  stroke-width: 1.6;
}
.orch-edge.is-flow {
  stroke: #20c8ff;
  stroke-width: 2;
  stroke-dasharray: 8 8;
  animation: orch-dash 0.9s linear infinite;
}

/* Nodes */
.orch-node-bg {
  fill: rgba(22, 32, 48, 0.95);
  stroke: rgba(90, 120, 160, 0.4);
  stroke-width: 1.2;
  transition: all 0.18s;
}
.orch-node-accent { fill: #5a6b80; }
.orch-node-stage { fill: #eaf2ff; font-size: 13px; font-weight: 600; }
.orch-node-agent { fill: #8b9cb3; font-size: 10.5px; }
.orch-node-gate { font-size: 12px; }
.orch-node-retry { fill: #f0b429; font-size: 10px; }
.orch-node-loop { font-size: 12px; }
.orch-node-loop-iter { fill: #b98cff; font-size: 10px; }
.orch-node.is-loop .orch-node-bg { stroke-dasharray: 6 3; }
.orch-node.is-loop .orch-node-accent { fill: #b98cff; }
.orch-node-pulse { fill: #20c8ff; animation: orch-pulse 1.1s ease-in-out infinite; }
.orch-node.is-clickable { cursor: pointer; }
.orch-node.is-hover .orch-node-bg { stroke-width: 2; }
.orch-node:hover .orch-node-bg { filter: brightness(1.15); }

/* Status colors */
.orch-node.st-pending .orch-node-accent { fill: #5a6b80; }
.orch-node.st-running .orch-node-bg { stroke: #20c8ff; }
.orch-node.st-running .orch-node-accent { fill: #20c8ff; }
.orch-node.st-completed .orch-node-bg { stroke: #37d67a; }
.orch-node.st-completed .orch-node-accent { fill: #37d67a; }
.orch-node.st-failed .orch-node-bg { stroke: #ff5d6c; }
.orch-node.st-failed .orch-node-accent { fill: #ff5d6c; }
.orch-node.st-skipped { opacity: 0.55; }
.orch-node.st-skipped .orch-node-bg { stroke-dasharray: 5 4; }
.orch-node.st-skipped .orch-node-accent { fill: rgba(140, 160, 185, 0.55); }
.orch-node.is-gate .orch-node-bg { stroke: #f0b429; }

/* Tooltip */
.orch-tip {
  position: absolute;
  z-index: 5;
  min-width: 160px;
  max-width: 260px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(12, 18, 28, 0.97);
  border: 1px solid rgba(32, 200, 255, 0.35);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
  font-size: 11px;
  pointer-events: none;
}
.orch-tip-stage { font-size: 12px; font-weight: 600; color: #eaf2ff; margin-bottom: 5px; }
.orch-tip-row { display: flex; gap: 8px; line-height: 1.7; }
.orch-tip-row span { color: #7f8ea3; flex: 0 0 34px; }
.orch-tip-row b { color: #c6d4e6; font-weight: 500; word-break: break-all; }
.orch-tip-err b { color: #ff8a94; }

/* Approval panel */
.orch-approval {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 8;
  width: 300px;
  max-width: calc(100% - 24px);
  padding: 12px;
  border-radius: 12px;
  background: rgba(14, 22, 34, 0.97);
  border: 1px solid rgba(240, 180, 41, 0.5);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.55), 0 0 24px rgba(240, 180, 41, 0.15);
  font-size: 12px;
  color: #d8e2f0;
}
.orch-approval-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.orch-approval-title { font-size: 13px; font-weight: 600; color: #f0b429; }
.orch-approval-stage { font-size: 11px; color: #9db0c8; }
.orch-approval-path {
  font-size: 11px;
  color: #8b9cb3;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.orch-approval-note {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid rgba(90, 120, 160, 0.3);
  background: rgba(10, 16, 26, 0.8);
  color: #d8e2f0;
  font-size: 12px;
  font-family: inherit;
}
.orch-approval-note:focus { outline: none; border-color: rgba(32, 200, 255, 0.6); }
.orch-approval-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.orch-btn {
  flex: 1;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid rgba(90, 120, 160, 0.35);
  background: rgba(20, 30, 46, 0.8);
  color: #d8e2f0;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.orch-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.orch-btn.is-approve:hover:not(:disabled) { border-color: #37d67a; color: #37d67a; background: rgba(55, 214, 122, 0.12); }
.orch-btn.is-reject:hover:not(:disabled) { border-color: #ff5d6c; color: #ff5d6c; background: rgba(255, 93, 108, 0.12); }
.orch-btn.is-retry:hover:not(:disabled) { border-color: #20c8ff; color: #20c8ff; background: rgba(32, 200, 255, 0.12); }
.orch-approval-log {
  margin-top: 10px;
  border-top: 1px solid rgba(90, 120, 160, 0.2);
  padding-top: 8px;
  max-height: 160px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.orch-approval-log-title { font-size: 11px; color: #7f8ea3; }
.orch-approval-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #9db0c8;
}
.orch-approval-act {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: 5px;
  font-size: 10px;
}
.orch-approval-act.act-pending { background: rgba(240, 180, 41, 0.18); color: #f0b429; }
.orch-approval-act.act-approve { background: rgba(55, 214, 122, 0.18); color: #37d67a; }
.orch-approval-act.act-reject { background: rgba(255, 93, 108, 0.18); color: #ff5d6c; }
.orch-approval-act.act-retry { background: rgba(32, 200, 255, 0.18); color: #20c8ff; }
.orch-approval-who { flex: 0 0 auto; color: #c6d4e6; }
.orch-approval-note-text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #8b9cb3; }
.orch-approval-time { flex: 0 0 auto; color: #6b7d93; font-size: 10px; }

@keyframes orch-dash { to { stroke-dashoffset: -16; } }
@keyframes orch-pulse { 0%, 100% { opacity: 1; r: 4; } 50% { opacity: 0.35; r: 5.5; } }
@keyframes orch-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
