<!-- Real-time mini network topology next to pet (pure SVG, click to expand full view) -->
<template>
  <div class="pt-mini" :style="{ left: x + 'px', top: y + 'px' }" @click="onOpen" :title="tip">
    <svg class="pt-mini-svg" :width="W" :height="H" :viewBox="`0 0 ${W} ${H}`">
      <defs>
        <filter id="pt-mini-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="1.6" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      <!-- Links: master -> nodes -->
      <line
        v-for="l in lines"
        :key="l.id"
        :x1="layout.center.x"
        :y1="layout.center.y"
        :x2="l.x"
        :y2="l.y"
        :stroke="l.color"
        :stroke-width="l.active ? 1.1 : 0.8"
        :stroke-dasharray="l.state === 'offline' ? '2 2' : ''"
        :opacity="l.state === 'offline' ? 0.4 : 0.75"
      />

      <!-- Center node -->
      <g class="pt-mini-node is-center" :class="'st-' + model.center.state">
        <circle :cx="layout.center.x" :cy="layout.center.y" r="7.5" :fill="centerFill" filter="url(#pt-mini-glow)" />
        <circle :cx="layout.center.x" :cy="layout.center.y" r="7.5" :stroke="centerColor" stroke-width="1" fill="none" class="pt-pulse" />
        <text :x="layout.center.x" :y="layout.center.y + 2.6" text-anchor="middle" class="pt-mini-ico">★</text>
        <!-- Agent dots on center (stopped agents not drawn) -->
        <circle
          v-for="(a, ai) in centerDrawAgents.slice(0, 6)"
          :key="a.id"
          :cx="layout.center.x + 8 + (ai % 3) * 4"
          :cy="layout.center.y - 8 + Math.floor(ai / 3) * 4"
          r="1.6"
          :fill="agentColor(a.state)"
        />
      </g>

      <!-- Access points: browser extension (top) / daemon (bottom), one dot per online session -->
      <!-- 96x96 space is minimal, only dots not names, names shown via title tooltip -->
      <g v-for="n in accessPoints" :key="n.id" class="pt-mini-node">
        <title>{{ n.title }}</title>
        <circle :cx="n.x" :cy="n.y" r="2.6" :stroke="n.color" :fill="n.fill" stroke-width="0.8" />
      </g>

      <!-- Other nodes -->
      <g
        v-for="n in nodePoints"
        :key="n.id"
        class="pt-mini-node"
        :class="'st-' + n.state"
      >
        <circle :cx="n.x" :cy="n.y" :stroke="n.color" :fill="n.fill" stroke-width="1" />
        <circle v-if="n.state !== 'offline'" :cx="n.x" :cy="n.y" r="5.5" :stroke="n.color" stroke-width="1" fill="none" class="pt-pulse" />
        <!-- Agent dots on node (stopped agents not drawn) -->
        <circle
          v-for="(a, ai) in n.drawAgents.slice(0, 6)"
          :key="a.id"
          :cx="n.x + 6 + (ai % 3) * 4"
          :cy="n.y - 6 + Math.floor(ai / 3) * 4"
          r="1.6"
          :fill="agentColor(a.state)"
        />
      </g>
    </svg>

    <div class="pt-mini-badge" :class="{ 'is-wait': model.counts.waiting > 0 }">
      <span class="pt-mini-badge-dot"></span>{{ model.counts.agents }}
    </div>
    <div class="pt-mini-tip">{{ model.counts.online }}/{{ model.counts.nodes }} online<template v-if="model.counts.waiting > 0"> · {{ model.counts.waiting }} waiting</template></div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { buildTopology, layoutTopology, formatBrowserLabel } from './topology.js'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  agents: { type: Array, default: () => [] },
  getStatusClass: { type: Function, default: () => 'running' },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  // Connected browser extension sessions (gateway /api/browser-ext/sessions, includes name / extension_version)
  extensionSessions: { type: Array, default: () => [] },
  // Connected daemon sessions (gateway /api/daemon/sessions, includes name / platform / daemon_version)
  daemonSessions: { type: Array, default: () => [] },
  // Whether local daemon is installed and running (local loopback /api/status detection): true means skip install prompt
  localDaemonOnline: { type: Boolean, default: false },
})

const W = 96
const H = 96

const model = computed(() => buildTopology(props.nodes, props.agents, props.getStatusClass))
// Incoming node circle size: ensures ring radius is large enough that node circles don't touch center circle
// (otherwise the master->node link directly above would be completely covered by both circles)
const layout = computed(() => layoutTopology(model.value, W, H, {
  centerHalfH: 7.5,
  nodeHalfH: 5.5,
  minGap: 3,
}))

// Access point layout responsive to screen orientation: width>height (PC) uses left/right columns, height>width (mobile) uses top/bottom rows
const isPortrait = ref(typeof window !== 'undefined' && window.innerHeight > window.innerWidth)
function updateOrientation() {
  isPortrait.value = window.innerHeight > window.innerWidth
}
onMounted(() => window.addEventListener('resize', updateOrientation))
onBeforeUnmount(() => window.removeEventListener('resize', updateOrientation))

const NODE_COLORS = {
  online: '#34d99b',
  offline: '#ff5d6c',
  unknown: '#8a9bb0',
}

function nodeColor(state) {
  return NODE_COLORS[state] || NODE_COLORS.unknown
}

const AGENT_COLORS = {
  running: '#20c8ff',
  waiting: '#ffb347',
  idle: '#8a9bb0',
  stopped: '#ff5d6c',
}

function agentColor(state) {
  return AGENT_COLORS[state] || AGENT_COLORS.idle
}

const centerDrawAgents = computed(() => model.value.center.drawAgents || [])

const nodePoints = computed(() => {
  const posMap = new Map(layout.value.nodes.map(p => [p.id, p]))
  return model.value.nodes.map(node => {
    const p = posMap.get(node.id) || { x: layout.value.center.x, y: layout.value.center.y }
    const color = nodeColor(node.state)
    return {
      id: node.id,
      x: p.x,
      y: p.y,
      state: node.state,
      color,
      fill: node.state === 'offline' ? 'rgba(255,93,108,0.16)' : 'rgba(8,18,30,0.95)',
      agents: node.agents,
      drawAgents: node.drawAgents || [],
    }
  })
})

const lines = computed(() =>
  nodePoints.value.map(n => ({
    id: n.id,
    x: n.x,
    y: n.y,
    state: n.state,
    color: n.color,
    active: n.agents.length > 0,
  }))
)

// Access-end dots: browser extensions (top row) / daemon services (bottom row), one dot per online session.
// Data comes from the gateway session list (props); names are only used for the title hover hint (text does not fit in 96x96).
// Layout adapts to screen orientation: side-by-side columns when width > height (PC), stacked rows when height > width (mobile).
const accessPoints = computed(() => {
  const cx = layout.value.center.x
  const cy = layout.value.center.y
  const gap = 8
  // Portrait (mobile): extensions on the top row, daemon on the bottom row, each evenly spaced horizontally
  const placeRow = (count, fixedY) => {
    if (count <= 0) return []
    const total = (count - 1) * gap
    const start = cx - total / 2
    const xs = []
    for (let i = 0; i < count; i++) {
      xs.push({ x: Math.min(Math.max(start + i * gap, 5), W - 5), y: fixedY })
    }
    return xs
  }
  // Landscape (PC): extensions in the left column, daemon in the right column, each evenly spaced vertically
  const placeCol = (count, fixedX) => {
    if (count <= 0) return []
    const total = (count - 1) * gap
    const start = cy - total / 2
    const ys = []
    for (let i = 0; i < count; i++) {
      ys.push({ x: fixedX, y: Math.min(Math.max(start + i * gap, 5), H - 5) })
    }
    return ys
  }
  const portrait = isPortrait.value
  const extPos = portrait ? placeRow(props.extensionSessions.length, 6) : placeCol(props.extensionSessions.length, 6)
  const daemonPos = portrait ? placeRow(props.daemonSessions.length, H - 6) : placeCol(props.daemonSessions.length, W - 6)
  const points = []
  props.extensionSessions.forEach((s, i) => {
    const name = String((s && s.name) || '').trim() || 'Browser Extension'
    const browserLabel = formatBrowserLabel(s && s.browser_info, s && s.extension_version)
    const p = extPos[i] || { x: cx, y: 6 }
    points.push({
      id: `ext-${s.session_id || i}`,
      x: p.x,
      y: p.y,
      color: nodeColor('online'),
      fill: 'rgba(8,18,30,0.95)',
      title: `Browser Extension · ${name}${browserLabel ? ` · ${browserLabel}` : ''}`,
    })
  })
  props.daemonSessions.forEach((s, i) => {
    const name = String((s && s.name) || '').trim() || 'Daemon'
    const p = daemonPos[i] || { x: cx, y: H - 6 }
    points.push({
      id: `daemon-${s.session_id || i}`,
      x: p.x,
      y: p.y,
      color: nodeColor('online'),
      fill: 'rgba(8,18,30,0.95)',
      title: `Daemon · ${name}`,
    })
  })
  return points
})

const centerColor = computed(() => nodeColor(model.value.center.state))
const centerFill = computed(() =>
  model.value.center.state === 'offline' ? 'rgba(255,93,108,0.9)' : 'rgba(32,200,255,0.92)'
)

const tip = computed(() => {
  const c = model.value.counts
  const parts = [`Nodes ${c.online}/${c.nodes} online`, `Agents ${c.agents}`]
  if (c.waiting > 0) parts.push(`${c.waiting} waiting for input`)
  return parts.join(' · ') + '\nClick to view network topology'
})

const emit = defineEmits(['open'])

function onOpen() {
  emit('open')
}
</script>

<style scoped>
.pt-mini {
  position: fixed;
  z-index: 901;
  width: 96px;
  height: 96px;
  cursor: pointer;
  user-select: none;
  transition: transform 0.18s ease;
}
.pt-mini:hover {
  transform: scale(1.06);
}
.pt-mini-svg {
  display: block;
  overflow: visible;
  filter: drop-shadow(0 4px 14px rgba(0, 90, 140, 0.35));
}
.pt-mini-node text.pt-mini-ico {
  font-size: 6px;
  fill: #04222f;
  pointer-events: none;
}
.pt-pulse {
  transform-box: fill-box;
  transform-origin: center;
  animation: pt-pulse 2.2s ease-out infinite;
}
@keyframes pt-pulse {
  0% { opacity: 0.8; transform: scale(1); }
  70% { opacity: 0; transform: scale(2.1); }
  100% { opacity: 0; transform: scale(2.1); }
}
.pt-mini-badge {
  position: absolute;
  right: -4px;
  top: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  display: flex;
  align-items: center;
  gap: 3px;
  border-radius: 9px;
  background: rgba(8, 18, 30, 0.92);
  border: 1px solid rgba(32, 200, 255, 0.4);
  color: var(--color-text-primary, #e6f4ff);
  font-size: 10px;
  font-weight: 600;
}
.pt-mini-badge.is-wait {
  border-color: rgba(255, 179, 71, 0.7);
  color: #ffb347;
}
.pt-mini-badge-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #34d99b;
  box-shadow: 0 0 6px #34d99b;
}
.pt-mini-badge.is-wait .pt-mini-badge-dot {
  background: #ffb347;
  box-shadow: 0 0 6px #ffb347;
  animation: pt-blink 1s ease-in-out infinite;
}
@keyframes pt-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.pt-mini-tip {
  position: absolute;
  left: 50%;
  bottom: -18px;
  transform: translateX(-50%);
  white-space: nowrap;
  font-size: 9px;
  color: var(--color-text-secondary, #8a9bb0);
  opacity: 0;
  transition: opacity 0.18s ease;
  pointer-events: none;
}
.pt-mini:hover .pt-mini-tip {
  opacity: 1;
}
</style>
