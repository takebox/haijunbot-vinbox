<!-- Network topology large overlay (opened by clicking the mini-diagram next to the pet) -->
<template>
  <transition name="topo-fade">
    <div v-if="visible" class="topo-overlay" @click.self="close">
      <div class="topo-panel" role="dialog" aria-label="Network topology">
        <div class="topo-header">
          <div class="topo-title">
            <span class="topo-title-ico" v-html="TOPO_ICONS.map"></span>
            <span>Network topology</span>
            <span class="topo-sub">{{ counts.online }}/{{ counts.nodes }} nodes online · {{ counts.agents }} agents<template v-if="counts.waiting > 0"> · {{ counts.waiting }} awaiting input</template></span>
          </div>
          <button class="topo-close" title="Close (Esc)" @click="close">✕</button>
        </div>

        <div class="topo-body" ref="bodyEl" @mousemove="onMove" @mouseleave="hovered = null">
          <!-- Top-left stats card -->
          <div class="topo-stats">
            <div class="topo-stats-title">Agent overview</div>
            <div class="topo-stats-list">
              <div class="topo-stats-item" :style="{ '--stat-color': AGENT_COLORS.running }">
                <span class="topo-stats-icon">▶</span>
                <span class="topo-stats-label">Running</span>
                <span class="topo-stats-value">{{ counts.running || 0 }}</span>
              </div>
              <div class="topo-stats-item" :style="{ '--stat-color': AGENT_COLORS.waiting }">
                <span class="topo-stats-icon">⏸</span>
                <span class="topo-stats-label">Awaiting input</span>
                <span class="topo-stats-value">{{ counts.waiting || 0 }}</span>
              </div>
              <div class="topo-stats-item" :style="{ '--stat-color': AGENT_COLORS.stopped }">
                <span class="topo-stats-icon">⏹</span>
                <span class="topo-stats-label">Stopped</span>
                <span class="topo-stats-value">{{ counts.stopped || 0 }}</span>
              </div>
            </div>
            <div class="topo-stats-foot">Total: {{ counts.agents || 0 }} agents</div>
          </div>

          <svg class="topo-svg" :width="W" :height="H" :viewBox="`0 0 ${W} ${H}`">
            <defs>
              <radialGradient id="topo-bg" cx="50%" cy="50%" r="70%">
                <stop offset="0%" stop-color="rgba(32,200,255,0.10)" />
                <stop offset="100%" stop-color="rgba(4,8,16,0)" />
              </radialGradient>
              <filter id="topo-glow" x="-80%" y="-80%" width="260%" height="260%">
                <feGaussianBlur stdDeviation="3" result="b" />
                <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
              <linearGradient id="topo-center-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#ffe89a" />
                <stop offset="100%" stop-color="#f0b429" />
              </linearGradient>
            </defs>

            <rect :width="W" :height="H" fill="url(#topo-bg)" />

            <!-- Links: master -> each node -->
            <g class="topo-links">
              <line
                v-for="l in lines"
                :key="'L' + l.id"
                :x1="layout.center.x"
                :y1="layout.center.y"
                :x2="l.x"
                :y2="l.y"
                :stroke="l.state === 'offline' ? 'rgba(255,93,108,0.35)' : '#20c8ff'"
                :stroke-opacity="l.state === 'offline' ? 1 : 0.55"
                :stroke-width="l.hot ? 2.4 : 1.6"
                :stroke-dasharray="l.state === 'offline' ? '6 5' : ''"
                class="topo-link"
                :class="{ 'is-hot': l.hot, 'is-flow': l.state !== 'offline' }"
              />
            </g>

            <!-- Links: node -> its agents -->
            <g class="topo-agent-links">
              <line
                v-for="al in agentLinks"
                :key="'AL' + al.id"
                :x1="al.x1"
                :y1="al.y1"
                :x2="al.x2"
                :y2="al.y2"
                :stroke="agentColor(al.state)"
                stroke-width="1"
                stroke-dasharray="3 3"
                opacity="0.45"
              />
            </g>

            <!-- Links: master -> local execution-surface nodes (browser extension / local background service), curved -->
            <!-- Must be rendered before the nodes: SVG has no z-index, later-rendered elements are on top, otherwise links cover the gateway nodes -->
            <g class="topo-links-local">
              <path
                v-for="l in localLinks"
                :key="'LL' + l.id"
                :d="l.d"
                :stroke="l.state === 'offline' ? 'rgba(255,93,108,0.35)' : '#20c8ff'"
                :stroke-opacity="l.state === 'offline' ? 1 : 0.55"
                :stroke-width="l.hot ? 2.4 : 1.6"
                :stroke-dasharray="l.state === 'offline' ? '6 5' : ''"
                class="topo-link"
                :class="{ 'is-hot': l.hot, 'is-flow': l.state !== 'offline' }"
                fill="none"
              />
            </g>

            <!-- Agent nodes (robot shape; code_agent has goggles, stopped agents are not drawn) -->
            <g
              v-for="a in agentLayout.agents"
              :key="'A' + a.id"
              class="topo-agent"
              :class="['st-' + a.state, a.type === 'code_agent' ? 'is-code' : 'is-chat']"
              @mouseenter="hovered = a.nodeId"
            >
              <circle v-if="a.state === 'waiting' || a.state === 'running'" :cx="a.x" :cy="a.y" :r="AGENT_R + 4" :stroke="agentColor(a.state)" stroke-width="1" fill="none" class="topo-ring" />
              <circle :cx="a.x" :cy="a.y" :r="AGENT_R + 1" :fill="agentFill(a.state)" :stroke="agentColor(a.state)" stroke-width="1.4" />
              <!-- Robot head -->
              <rect :x="a.x - AGENT_R + 3" :y="a.y - AGENT_R + 4" :width="AGENT_R * 2 - 6" :height="AGENT_R * 2 - 8" rx="4"
                    :fill="agentColor(a.state)" class="topo-bot-head" />
              <!-- Antenna -->
              <line :x1="a.x" :y1="a.y - AGENT_R + 3" :x2="a.x" :y2="a.y - AGENT_R - 1"
                    :stroke="agentColor(a.state)" stroke-width="1.4" />
              <circle :cx="a.x" :cy="a.y - AGENT_R - 2.5" r="1.8" :fill="agentColor(a.state)" />
              <!-- Eyes: code_agent uses a horizontal visor, ordinary agents use two round eyes -->
              <template v-if="a.type === 'code_agent'">
                <rect :x="a.x - AGENT_R + 5" :y="a.y - 3" :width="AGENT_R * 2 - 10" :height="4.4" rx="2.2"
                      fill="#041018" class="topo-goggle" />
              </template>
              <template v-else>
                <circle :cx="a.x - 3.4" :cy="a.y - 0.6" r="1.6" fill="#041018" />
                <circle :cx="a.x + 3.4" :cy="a.y - 0.6" r="1.6" fill="#041018" />
              </template>
              <!-- Mouth/status light -->
              <rect :x="a.x - 3" :y="a.y + 4" :width="6" :height="2" rx="1" fill="#041018" opacity="0.75" />
              <text :x="a.labelX" :y="a.labelY" :text-anchor="a.labelAnchor" :dominant-baseline="a.labelBaseline" class="topo-agent-label">{{ agentShort(a.name) }}</text>
            </g>

            <!-- Other nodes (server chassis shape) -->
            <g
              v-for="n in nodePoints"
              :key="n.id"
              class="topo-node"
              :class="['st-' + n.state, { 'is-hot': hovered === n.id }]"
              @mouseenter="hovered = n.id"
            >
              <rect v-if="n.state !== 'offline'" :x="n.x - NODE_R - 4" :y="n.y - NODE_R * 0.86 - 4" :width="NODE_R * 2 + 8" :height="NODE_R * 1.72 + 8" rx="9"
                    :stroke="n.color" stroke-width="1.4" fill="none" class="topo-ring" />
              <!-- Chassis body -->
              <rect :x="n.x - NODE_R" :y="n.y - NODE_R * 0.86" :width="NODE_R * 2" :height="NODE_R * 1.72" rx="6"
                    :fill="n.fill" :stroke="n.color" stroke-width="1.8" class="topo-server" />
              <!-- Top slot -->
              <line :x1="n.x - NODE_R + 6" :y1="n.y - NODE_R * 0.86 + 7" :x2="n.x + NODE_R - 6" :y2="n.y - NODE_R * 0.86 + 7"
                    :stroke="n.color" stroke-width="1.4" opacity="0.6" />
              <!-- Cooling grille -->
              <line v-for="k in 3" :key="'g' + k"
                    :x1="n.x - NODE_R + 8" :y1="n.y - NODE_R * 0.86 + 6 + k * 4.6"
                    :x2="n.x + NODE_R - 16" :y2="n.y - NODE_R * 0.86 + 6 + k * 4.6"
                    :stroke="n.color" stroke-width="1" opacity="0.35" />
              <!-- Status LED -->
              <circle :cx="n.x + NODE_R - 10" :cy="n.y - 2" r="2.4" :fill="n.color" class="topo-led" />
              <circle :cx="n.x + NODE_R - 10" :cy="n.y + 5" r="2.4" :fill="n.color" opacity="0.4" />
              <!-- Bottom status bar -->
              <rect :x="n.x - NODE_R + 6" :y="n.y + NODE_R * 0.86 - 8" :width="NODE_R * 2 - 12" :height="3" rx="1.5"
                    :fill="n.color" opacity="0.5" />
              <text :x="n.x" :y="n.y + NODE_R * 0.86 + 16" text-anchor="middle" class="topo-node-label">{{ n.short }}</text>
              <text :x="n.x" :y="n.y + NODE_R * 0.86 + 29" text-anchor="middle" class="topo-node-count">{{ n.drawAgents.length }}/{{ n.agents.length }} agent</text>
            </g>

            <!-- Local execution-surface nodes (browser extension on the left, local background service on the right; circular shape, clearly distinct from server chassis) -->
            <g
              v-for="n in localNodes"
              :key="n.id"
              class="topo-node is-local"
              :class="['st-' + n.state, { 'is-hot': hovered === n.id }]"
              @mouseenter="hovered = n.id"
            >
              <title>{{ n.title }}</title>
              <circle v-if="n.state !== 'offline'" :cx="n.x" :cy="n.y" :r="ACCESS_R + 5"
                      :stroke="n.color" stroke-width="1.4" fill="none" class="topo-ring" />
              <!-- Circular body -->
              <circle :cx="n.x" :cy="n.y" :r="ACCESS_R"
                      :fill="n.fill" :stroke="n.color" stroke-width="1.8" class="topo-server" />
              <!-- Type icon -->
              <g :transform="`translate(${n.x - 8}, ${n.y - 8})`">
                <svg v-if="n.icon === 'extension'" viewBox="0 0 16 16" width="16" height="16" fill="none" :stroke="n.color" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M6 3.5A1.5 1.5 0 0 1 9 3.5V4h1.5A1.5 1.5 0 0 1 12 5.5V7h.5a1.5 1.5 0 0 1 0 3H12v1.5A1.5 1.5 0 0 1 10.5 13H9v.5a1.5 1.5 0 0 1-3 0V13H4.5A1.5 1.5 0 0 1 3 11.5V10h-.5a1.5 1.5 0 0 1 0-3H3V5.5A1.5 1.5 0 0 1 4.5 4H6z"/>
                </svg>
                <svg v-else-if="n.icon === 'daemon'" viewBox="0 0 16 16" width="16" height="16" fill="none" :stroke="n.color" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="2" y="3" width="12" height="8" rx="1.5"/>
                  <path d="M5.5 13.5h5M8 11v2.5"/>
                </svg>
              </g>
              <!-- Label text: vertically stacked when portrait (top row below, bottom row above), side by side when landscape (left column on the right, right column on the left), both facing inward -->
              <text :x="n.labelAbove === null ? (n.anchor === 'start' ? n.x + ACCESS_R + 16 : n.x - ACCESS_R - 16) : n.x"
                    :y="n.labelAbove === null ? n.y : (n.labelAbove ? n.y - ACCESS_R - 16 : n.y + ACCESS_R + 16)"
                    :text-anchor="n.anchor" class="topo-node-label">{{ n.short }}</text>
              <text :x="n.labelAbove === null ? (n.anchor === 'start' ? n.x + ACCESS_R + 16 : n.x - ACCESS_R - 16) : n.x"
                    :y="n.labelAbove === null ? n.y + 13 : (n.labelAbove ? n.y - ACCESS_R - 29 : n.y + ACCESS_R + 29)"
                    :text-anchor="n.anchor" class="topo-node-count">{{ n.sub }}</text>
            </g>

            <!-- Center master (same server-chassis style as child nodes; only color/size distinguish the hub) -->
            <g class="topo-node is-center" :class="'st-' + model.center.state" @mouseenter="hovered = 'master'">
              <rect v-if="model.center.state !== 'offline'" :x="layout.center.x - CENTER_W / 2 - 5" :y="layout.center.y - CENTER_H / 2 - 5" :width="CENTER_W + 10" :height="CENTER_H + 10" rx="11"
                    :stroke="centerColor" stroke-width="1.4" fill="none" class="topo-ring" />
              <!-- Chassis body -->
              <rect :x="layout.center.x - CENTER_W / 2" :y="layout.center.y - CENTER_H / 2" :width="CENTER_W" :height="CENTER_H" rx="7"
                    :fill="centerFill" :stroke="centerColor" stroke-width="2.2" class="topo-server" filter="url(#topo-glow)" />
              <!-- Top slot -->
              <line :x1="layout.center.x - CENTER_W / 2 + 8" :y1="layout.center.y - CENTER_H / 2 + 9"
                    :x2="layout.center.x + CENTER_W / 2 - 8" :y2="layout.center.y - CENTER_H / 2 + 9"
                    :stroke="centerColor" stroke-width="1.6" opacity="0.7" />
              <!-- Cooling grille -->
              <line v-for="k in 3" :key="'mg' + k"
                    :x1="layout.center.x - CENTER_W / 2 + 10" :y1="layout.center.y - CENTER_H / 2 + 8 + k * 5.4"
                    :x2="layout.center.x + CENTER_W / 2 - 20" :y2="layout.center.y - CENTER_H / 2 + 8 + k * 5.4"
                    :stroke="centerColor" stroke-width="1.2" opacity="0.4" />
              <!-- Status LED -->
              <circle :cx="layout.center.x + CENTER_W / 2 - 12" :cy="layout.center.y - 2" r="2.8" :fill="centerColor" class="topo-led" />
              <circle :cx="layout.center.x + CENTER_W / 2 - 12" :cy="layout.center.y + 6" r="2.8" :fill="centerColor" opacity="0.4" />
              <!-- Bottom status bar -->
              <rect :x="layout.center.x - CENTER_W / 2 + 8" :y="layout.center.y + CENTER_H / 2 - 9" :width="CENTER_W - 16" :height="3.5" rx="1.75"
                    :fill="centerColor" opacity="0.55" />
              <text :x="layout.center.x" :y="layout.center.y + CENTER_H / 2 + 18" text-anchor="middle" class="topo-center-label">MASTER</text>
              <text :x="layout.center.x" :y="layout.center.y + CENTER_H / 2 + 32" text-anchor="middle" class="topo-node-count">{{ model.center.drawAgents.length }}/{{ model.center.agents.length }} agent</text>
            </g>
          </svg>

          <!-- Hover detail card -->
          <div v-if="hoverInfo" class="topo-card" :style="{ left: hoverInfo.left + 'px', top: hoverInfo.top + 'px' }">
            <div class="topo-card-title">
              <span class="topo-dot" :style="{ background: hoverInfo.color }"></span>{{ hoverInfo.title }}
            </div>
            <div class="topo-card-sub">{{ hoverInfo.sub }}</div>
            <ul v-if="hoverInfo.agents.length" class="topo-card-list">
              <li v-for="a in hoverInfo.agents" :key="a.id">
                <span class="topo-dot" :style="{ background: agentColor(a.state) }"></span>
                <span class="topo-card-type">
                  <svg v-if="a.type === 'code_agent'" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M5.5 4.5 2.5 8l3 3.5M10.5 4.5l3 3.5-3 3.5"/>
                    <path d="M9.5 3.5l-3 9"/>
                  </svg>
                  <svg v-else viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <rect x="3" y="5" width="10" height="7" rx="2"/>
                    <circle cx="5.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                    <circle cx="10.5" cy="8.5" r="0.7" fill="currentColor" stroke="none"/>
                    <path d="M6 3.5 8 5l2-1.5"/>
                    <path d="M5 12v1.5M11 12v1.5"/>
                    <path d="M3 10H1.5M14.5 10H13"/>
                  </svg>
                </span>
                <span class="topo-card-name">{{ a.name }}</span>
                <span class="topo-card-state" :style="{ color: agentColor(a.state) }">{{ AGENT_TEXT[a.state] || a.state }}</span>
              </li>
            </ul>
            <div v-else class="topo-card-empty">No agents</div>
          </div>
        </div>

        <!-- Legend -->
        <div class="topo-legend">
          <div class="topo-legend-group">
            <span class="topo-legend-h">Nodes</span>
            <span class="topo-legend-item"><i class="topo-dot" style="background:#34d99b"></i>Online</span>
            <span class="topo-legend-item"><i class="topo-dot" style="background:#ff5d6c"></i>Offline</span>
            <span class="topo-legend-item"><i class="topo-dot" style="background:#8a9bb0"></i>Unknown</span>
          </div>
          <div class="topo-legend-group">
            <span class="topo-legend-h">Agent</span>
            <span class="topo-legend-item"><i class="topo-dot" style="background:#20c8ff"></i>Running</span>
            <span class="topo-legend-item"><i class="topo-dot" style="background:#ffb347"></i>Awaiting</span>
            <span class="topo-legend-item"><i class="topo-dot" style="background:#8a9bb0"></i>Idle</span>
            <span class="topo-legend-item"><i class="topo-dot" style="background:#ff5d6c"></i>Stopped</span>
            <span class="topo-legend-item topo-legend-shape">
              <svg width="20" height="18" viewBox="0 0 20 18">
                <line x1="10" y1="2" x2="10" y2="5" stroke="#20c8ff" stroke-width="1.2" />
                <circle cx="10" cy="1.5" r="1.3" fill="#20c8ff" />
                <rect x="5" y="5" width="10" height="8" rx="2.5" fill="#20c8ff" />
                <circle cx="8.2" cy="9" r="1.1" fill="#041018" />
                <circle cx="11.8" cy="9" r="1.1" fill="#041018" />
              </svg>Standard
            </span>
            <span class="topo-legend-item topo-legend-shape">
              <svg width="20" height="18" viewBox="0 0 20 18">
                <line x1="10" y1="2" x2="10" y2="5" stroke="#20c8ff" stroke-width="1.2" />
                <circle cx="10" cy="1.5" r="1.3" fill="#20c8ff" />
                <rect x="5" y="5" width="10" height="8" rx="2.5" fill="#20c8ff" />
                <rect x="6.5" y="8" width="7" height="2" rx="1" fill="#041018" />
              </svg>Code
            </span>
          </div>
          <div class="topo-legend-group">
            <span class="topo-legend-h">Access points</span>
            <span class="topo-legend-item topo-legend-shape">
              <svg width="20" height="18" viewBox="0 0 20 18">
                <circle cx="10" cy="9" r="7" fill="rgba(8,18,30,0.95)" stroke="#34d99b" stroke-width="1.4" />
                <g transform="translate(4,3)">
                  <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="#34d99b" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M6 3.5A1.5 1.5 0 0 1 9 3.5V4h1.5A1.5 1.5 0 0 1 12 5.5V7h.5a1.5 1.5 0 0 1 0 3H12v1.5A1.5 1.5 0 0 1 10.5 13H9v.5a1.5 1.5 0 0 1-3 0V13H4.5A1.5 1.5 0 0 1 3 11.5V10h-.5a1.5 1.5 0 0 1 0-3H3V5.5A1.5 1.5 0 0 1 4.5 4H6z"/>
                  </svg>
                </g>
              </svg>Browser extension
            </span>
            <span class="topo-legend-item topo-legend-shape">
              <svg width="20" height="18" viewBox="0 0 20 18">
                <circle cx="10" cy="9" r="7" fill="rgba(8,18,30,0.95)" stroke="#34d99b" stroke-width="1.4" />
                <g transform="translate(4,3)">
                  <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="#34d99b" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="12" height="8" rx="1.5"/>
                    <path d="M5.5 13.5h5M8 11v2.5"/>
                  </svg>
                </g>
              </svg>Background service
            </span>
          </div>
          <span class="topo-legend-hint">Esc to close</span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { buildTopology, layoutTopology, layoutAgents, formatBrowserLabel } from './topology.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  nodes: { type: Array, default: () => [] },
  agents: { type: Array, default: () => [] },
  getStatusClass: { type: Function, default: () => 'running' },
  nodeDisplayNames: { type: Object, default: () => ({}) },
  // Connected browser extension sessions (gateway /api/browser-ext/sessions, with name / extension_version)
  extensionSessions: { type: Array, default: () => [] },
  // Connected background service sessions (gateway /api/daemon/sessions, with name / platform / daemon_version)
  daemonSessions: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:visible', 'close'])

const W = 1200
const H = 640
const NODE_R = 30
// Master node chassis size (slightly larger than child nodes, same shape)
const CENTER_W = 76
const CENTER_H = 66
const AGENT_R = 13
// Child-node agent orbit radius (smaller, to avoid colliding with adjacent nodes/their agents)
const AGENT_RING = 62
// Center agent orbit radius (slightly larger, to clear the center decorative ring and the MASTER label)
const CENTER_AGENT_RING = 70
// Reservation from the agent ring's outer edge to the canvas edge (agent radius + label space)
const AGENT_EDGE_PAD = AGENT_R + 24

const model = computed(() => buildTopology(props.nodes, props.agents, props.getStatusClass))
// Pass in the chassis sizes: ensure the orbit radius is large enough that node chassis do not touch the center chassis
// (otherwise the master->node link directly above would be fully covered by the two chassis)
const layout = computed(() => layoutTopology(model.value, W, H, {
  centerHalfH: CENTER_H / 2,
  nodeHalfH: NODE_R * 0.86,
  minGap: 14,
  // Shrink the orbit radius to pull child nodes toward the center, giving the top/bottom access points
  // (browser extension / background service) more room — the mobile SVG scales down as a whole, and with
  // insufficient gap the access points end up touching the child nodes.
  // Reducing the desktop 0.34 -> 0.26 increases the top gap from ~32px to ~83px; on mobile (~0.31 scale) it looks like ~10px -> 26px.
  radius: Math.min(W, H) * 0.26,
}))
const counts = computed(() => model.value.counts)
// Agents included in the drawing (stopped agents are not drawn, only shown as data)
const agentLayout = computed(() =>
  layoutAgents(model.value, layout.value, {
    ring: AGENT_RING,
    centerRing: CENTER_AGENT_RING,
    agentRadius: AGENT_R,
    labelGap: 16,
    canvas: { width: W, height: H },
    edgePad: AGENT_EDGE_PAD,
  }),
)

const NODE_COLORS = { online: '#34d99b', offline: '#ff5d6c', unknown: '#8a9bb0' }
const AGENT_COLORS = { running: '#20c8ff', waiting: '#ffb347', idle: '#8a9bb0', stopped: '#ff5d6c' }
const AGENT_TEXT = { running: 'Running', waiting: 'Awaiting input', idle: 'Idle', stopped: 'Stopped' }

// Hand-drawn 16x16 stroke linear SVG icons (currentColor inherits the theme color), replacing the old emoji-style icons
const TOPO_ICONS = {
  map: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 3.5 6 2l4 1.5L14 3v9.5l-4 1-4-1.5L2 13z"/><path d="M6 2v9.5M10 3.5V13"/></svg>',
}

function nodeColor(state) {
  return NODE_COLORS[state] || NODE_COLORS.unknown
}
function agentColor(state) {
  return AGENT_COLORS[state] || AGENT_COLORS.idle
}
function agentFill(state) {
  const c = agentColor(state)
  return c + '33'
}
function agentShort(name) {
  const s = String(name || '')
  if (!s) return ''
  return s.length > 8 ? s.slice(0, 7) + '…' : s
}

const hovered = ref(null)
const bodyEl = ref(null)
const mouse = ref({ x: 0, y: 0 })

function shortLabel(id) {
  const custom = props.nodeDisplayNames && props.nodeDisplayNames[id]
  const s = String((custom && String(custom).trim()) || id || '')
  if (s === 'master') return 'master'
  return s.length > 10 ? s.slice(0, 9) + '…' : s
}

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
      fill: node.state === 'offline' ? 'rgba(255,93,108,0.14)' : 'rgba(8,18,30,0.95)',
      short: shortLabel(node.id),
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
    hot: hovered.value === n.id,
  }))
)

// Access point nodes: browser extensions (top row), background services (bottom row), each evenly distributed horizontally.
// Both are sourced from the gateway session lists (props.extensionSessions / props.daemonSessions),
// with names taken from each session's name, so what is shown here is the clients "connected across the whole network", not just local.
const LOCAL_NODE_R = NODE_R
// Vertical padding from the canvas top/bottom edges (leave enough room so node label text is not clipped by the canvas edge)
const LOCAL_NODE_MARGIN = 56
// Access point nodes are circular (regular nodes are server chassis); radius slightly smaller than the chassis half-height to leave label space
const ACCESS_R = NODE_R * 0.67
// Horizontal spacing between multiple nodes in the same row (including chassis width)
const ACCESS_NODE_GAP = NODE_R * 1.72 + 30

// Horizontal coordinates of single-row nodes: evenly distributed around master's x, clamped within the canvas
function accessRowXs(count, centerX) {
  if (count <= 0) return []
  const total = (count - 1) * ACCESS_NODE_GAP
  const start = centerX - total / 2
  const minX = LOCAL_NODE_R + 22
  const maxX = Math.max(minX, W - LOCAL_NODE_R - 22)
  const xs = []
  for (let i = 0; i < count; i++) {
    xs.push(Math.min(Math.max(start + i * ACCESS_NODE_GAP, minX), maxX))
  }
  return xs
}

// Vertical coordinates of single-column nodes: evenly distributed around master's y, clamped within the canvas
function accessColumnYs(count, centerY) {
  if (count <= 0) return []
  const total = (count - 1) * ACCESS_NODE_GAP
  const start = centerY - total / 2
  const minY = ACCESS_R + 22
  const maxY = Math.max(minY, H - ACCESS_R - 22)
  const ys = []
  for (let i = 0; i < count; i++) {
    ys.push(Math.min(Math.max(start + i * ACCESS_NODE_GAP, minY), maxY))
  }
  return ys
}

// Session display name: prefer the session's name from the gateway; fall back by type when missing
function accessSessionName(session, fallback) {
  const name = String((session && session.name) || '').trim()
  return name || fallback
}

// Truncate overly long names (the label below the chassis has limited width)
function accessShortName(name) {
  const s = String(name || '')
  if (s.length > 10) return s.slice(0, 9) + '…'
  return s
}

const localNodes = computed(() => {
  const cx = layout.value.center.x
  const cy = layout.value.center.y
  // Place access points outside the ringed child nodes (closer to the canvas edge) to avoid overlapping them:
  // child nodes are server chassis, so use their chassis half-height (NODE_R) as the ringed child boundary
  const childTop = nodePoints.value.length
    ? Math.min(...nodePoints.value.map(n => n.y - NODE_R))
    : cy
  const childBottom = nodePoints.value.length
    ? Math.max(...nodePoints.value.map(n => n.y + NODE_R))
    : cy
  const childLeft = nodePoints.value.length
    ? Math.min(...nodePoints.value.map(n => n.x - NODE_R))
    : cx
  const childRight = nodePoints.value.length
    ? Math.max(...nodePoints.value.map(n => n.x + NODE_R))
    : cx
  // Keep access points as far as possible from the ringed child nodes (larger gap) while not letting their
  // centers go past the canvas-edge padding. ACCESS_GAP is the target distance from an access point's center to a
  // child node's chassis edge; the mobile SVG scales down as a whole, so a tight gap would make access points
  // touch the child nodes — hence the generous margin here (combined with the smaller orbit radius).
  const ACCESS_GAP = 110
  // Layout is responsive to screen orientation: two columns when width > height (PC), two rows when height > width (mobile)
  const portrait = isPortrait.value
  let extPos = []
  let daemonPos = []
  if (portrait) {
    // Portrait (mobile): extension top row, daemon bottom row, each evenly distributed horizontally
    const topY = Math.max(ACCESS_R, Math.min(LOCAL_NODE_MARGIN + ACCESS_R, childTop - ACCESS_GAP))
    const bottomY = Math.min(H - ACCESS_R, Math.max(H - LOCAL_NODE_MARGIN - ACCESS_R, childBottom + ACCESS_GAP))
    const extXs = accessRowXs(props.extensionSessions.length, cx)
    const daemonXs = accessRowXs(props.daemonSessions.length, cx)
    extPos = extXs.map(x => ({ x, y: topY, labelAbove: false, anchor: 'middle' }))
    daemonPos = daemonXs.map(x => ({ x, y: bottomY, labelAbove: true, anchor: 'middle' }))
  } else {
    // Landscape (PC): extension left column, daemon right column, each evenly distributed vertically
    const leftX = LOCAL_NODE_MARGIN + ACCESS_R
    const rightX = W - LOCAL_NODE_MARGIN - ACCESS_R
    const extYs = accessColumnYs(props.extensionSessions.length, cy)
    const daemonYs = accessColumnYs(props.daemonSessions.length, cy)
    extPos = extYs.map(y => ({ x: leftX, y, labelAbove: null, anchor: 'start' }))
    daemonPos = daemonYs.map(y => ({ x: rightX, y, labelAbove: null, anchor: 'end' }))
  }
  const nodes = []
  props.extensionSessions.forEach((s, i) => {
    const name = accessSessionName(s, 'Browser extension')
    // Subtitle shows "browser name main-version · extension version", letting users tell browsers/devices apart
    const browserLabel = formatBrowserLabel(s && s.browser_info, s && s.extension_version)
    const p = extPos[i] || { x: cx, y: cy, labelAbove: false, anchor: 'middle' }
    nodes.push({
      id: `ext-${s.session_id || i}`,
      x: p.x,
      y: p.y,
      masterX: cx,
      masterY: cy,
      state: 'online',
      color: nodeColor('online'),
      fill: 'rgba(8,18,30,0.95)',
      short: accessShortName(name),
      sub: browserLabel || 'Browser extension',
      icon: 'extension',
      labelAbove: p.labelAbove,
      anchor: p.anchor,
      title: `Browser extension · ${name}${browserLabel ? ` · ${browserLabel}` : ''}`,
    })
  })
  props.daemonSessions.forEach((s, i) => {
    const name = accessSessionName(s, 'Background service')
    const platform = String((s && s.platform) || '').trim()
    const version = String((s && s.daemon_version) || '').trim()
    // The daemon-reported version may already carry a v prefix (e.g. v5.0.5); avoid concatenating into vv5.0.5
    const versionLabel = version ? (/^v/i.test(version) ? version : `v${version}`) : ''
    const detail = [platform, versionLabel].filter(Boolean).join(' · ')
    const p = daemonPos[i] || { x: cx, y: cy, labelAbove: true, anchor: 'middle' }
    nodes.push({
      id: `daemon-${s.session_id || i}`,
      x: p.x,
      y: p.y,
      masterX: cx,
      masterY: cy,
      state: 'online',
      color: nodeColor('online'),
      fill: 'rgba(8,18,30,0.95)',
      short: accessShortName(name),
      sub: detail || 'Background service',
      icon: 'daemon',
      labelAbove: p.labelAbove,
      anchor: p.anchor,
      title: `Background service · ${name}${detail ? ` · ${detail}` : ''}`,
    })
  })
  return nodes
})
const localLinks = computed(() =>
  localNodes.value.map(n => ({
    id: n.id,
    d: `M ${n.masterX} ${n.masterY} L ${n.x} ${n.y}`,
    state: n.state,
    hot: hovered.value === n.id,
  }))
)

// Node -> agent links: each agent connects back to its owning node (master connects to the center)
const agentLinks = computed(() => {
  const posMap = new Map(layout.value.nodes.map(p => [p.id, p]))
  return agentLayout.value.agents
    .map(a => {
      const origin = a.nodeId === 'master' ? layout.value.center : posMap.get(a.nodeId)
      if (!origin) return null
      return { id: a.id, x1: origin.x, y1: origin.y, x2: a.x, y2: a.y, state: a.state }
    })
    .filter(Boolean)
})

const centerColor = computed(() => {
  const state = model.value.center.state
  if (state === 'offline') return '#ff5d6c'
  if (state === 'unknown') return '#8a9bb0'
  // Online master node emphasized in gold to distinguish it from child nodes (green/blue)
  return '#ffd75e'
})
const centerFill = computed(() => {
  const state = model.value.center.state
  if (state === 'offline') return 'rgba(255,93,108,0.85)'
  if (state === 'unknown') return 'rgba(138,155,176,0.8)'
  // Online master node: gold gradient fill
  return 'url(#topo-center-fill)'
})

const hoverInfo = computed(() => {
  const id = hovered.value
  if (!id) return null
  const isCenter = id === 'master'
  const node = isCenter ? model.value.center : model.value.nodes.find(n => n.id === id)
  if (!node) return null
  const color = nodeColor(node.state)
  const stateText = node.state === 'online' ? 'Online' : node.state === 'offline' ? 'Offline' : 'Unknown'
  return {
    title: node.id,
    sub: `${stateText} · ${node.agents.length} agents`,
    color,
    agents: node.agents,
    left: Math.min(Math.max(mouse.value.x + 14, 10), W - 210),
    top: Math.min(Math.max(mouse.value.y + 14, 10), H - 40),
  }
})

function onMove(e) {
  const el = bodyEl.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const svg = el.querySelector('svg')
  const scale = svg ? svg.clientWidth / W || 1 : 1
  mouse.value = {
    x: (e.clientX - rect.left) / scale,
    y: (e.clientY - rect.top) / scale,
  }
}

function close() {
  emit('update:visible', false)
  emit('close')
}

function onKeydown(e) {
  if (e.key === 'Escape' && props.visible) {
    e.stopPropagation()
    close()
  }
}

// Access-point layout is responsive to screen orientation: two columns when width > height (PC), two rows when height > width (mobile)
const isPortrait = ref(typeof window !== 'undefined' && window.innerHeight > window.innerWidth)
function updateOrientation() {
  isPortrait.value = window.innerHeight > window.innerWidth
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown, true)
  window.addEventListener('resize', updateOrientation)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown, true)
  window.removeEventListener('resize', updateOrientation)
})

defineExpose({ close })
</script>

<style scoped>
.topo-overlay {
  position: fixed;
  inset: 0;
  z-index: 2950;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4vh 20px;
  background: rgba(4, 8, 16, 0.6);
  backdrop-filter: blur(3px);
}
.topo-panel {
  width: 96vw;
  height: 92vh;
  max-width: 1600px;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius, 10px);
  box-shadow: 0 12px 44px rgba(0, 120, 190, 0.3);
  overflow: hidden;
}
.topo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-subtle);
}
.topo-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.topo-title-ico {
  font-size: 16px;
}
.topo-sub {
  font-size: 11px;
  font-weight: 400;
  color: var(--color-text-secondary);
}
.topo-close {
  flex: none;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius-xs, 6px);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 0;
}
.topo-close:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}
.topo-body {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.topo-svg {
  display: block;
  width: 100%;
  height: 100%;
}
/* Top-left stats card */
.topo-stats {
  position: absolute;
  left: 14px;
  top: 14px;
  z-index: 3;
  min-width: 148px;
  padding: 10px 12px;
  background: rgba(8, 16, 28, 0.92);
  border: 1px solid rgba(32, 200, 255, 0.28);
  border-radius: var(--tile-radius-sm, 8px);
  box-shadow: 0 8px 24px rgba(0, 60, 100, 0.35);
  backdrop-filter: blur(4px);
  pointer-events: none;
  user-select: none;
}
.topo-stats-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--color-text-secondary, #8a9bb0);
  margin-bottom: 8px;
}
.topo-stats-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.topo-stats-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-primary, #e6f4ff);
}
.topo-stats-icon {
  flex: none;
  width: 14px;
  text-align: center;
  font-size: 10px;
  color: var(--stat-color, #8a9bb0);
}
.topo-stats-label {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
}
.topo-stats-value {
  flex: none;
  min-width: 20px;
  text-align: right;
  font-weight: 700;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
  color: var(--stat-color, #e6f4ff);
}
.topo-stats-foot {
  margin-top: 8px;
  padding-top: 7px;
  border-top: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.08));
  font-size: 10px;
  color: var(--color-text-secondary, #8a9bb0);
}
.topo-link {
  transition: stroke-width 0.15s ease;
}
.topo-link.is-flow {
  stroke-dasharray: 8 6;
  animation: topo-flow 1.2s linear infinite;
}
@keyframes topo-flow {
  to { stroke-dashoffset: -14; }
}
.topo-agent {
  cursor: default;
}
.topo-bot-head {
  opacity: 0.92;
}
.topo-goggle {
  opacity: 0.95;
}
.topo-agent-label {
  font-size: 10px;
  fill: var(--color-text-secondary, #8a9bb0);
  pointer-events: none;
}
.topo-ring {
  transform-box: fill-box;
  transform-origin: center;
  animation: topo-pulse 2.6s ease-out infinite;
}
@keyframes topo-pulse {
  0% { opacity: 0.7; transform: scale(1); }
  75% { opacity: 0; transform: scale(1.7); }
  100% { opacity: 0; transform: scale(1.7); }
}
.topo-node {
  cursor: default;
}
.topo-node.is-hot > .topo-server {
  filter: url(#topo-glow);
}
/* Local execution-surface nodes: do not participate in the hover detail card (no agents), shown as status only */
.topo-node.is-local {
  cursor: default;
}
.topo-node.is-local > .topo-node-label {
  font-size: 11px;
  font-weight: 600;
}
.topo-links-local .topo-link {
  stroke-linecap: round;
}
.topo-server {
  transition: filter 0.15s ease;
}
.topo-led {
  filter: drop-shadow(0 0 3px currentColor);
  animation: topo-led-blink 2.2s ease-in-out infinite;
}
@keyframes topo-led-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
.topo-node-label {
  font-size: 11px;
  fill: var(--color-text-secondary, #8a9bb0);
  pointer-events: none;
}
.topo-node-count {
  font-size: 10px;
  fill: var(--color-text-secondary, #8a9bb0);
  opacity: 0.8;
  pointer-events: none;
}
.topo-center-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  fill: #3a2a00;
  pointer-events: none;
}
.topo-node.is-center > .topo-node-count {
  fill: #ffe89a;
  opacity: 0.9;
}
.topo-card {
  position: absolute;
  width: 190px;
  padding: 8px 10px;
  background: rgba(8, 16, 28, 0.96);
  border: 1px solid rgba(32, 200, 255, 0.3);
  border-radius: var(--tile-radius-sm, 8px);
  box-shadow: 0 8px 24px rgba(0, 60, 100, 0.4);
  pointer-events: none;
  z-index: 2;
}
.topo-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary, #e6f4ff);
  word-break: break-all;
}
.topo-card-sub {
  margin-top: 2px;
  font-size: 10px;
  color: var(--color-text-secondary, #8a9bb0);
}
.topo-card-list {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  max-height: 140px;
  overflow: hidden;
}
.topo-card-list li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  padding: 2px 0;
}
.topo-card-type {
  flex: none;
  font-size: 11px;
}
.topo-card-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-primary, #e6f4ff);
}
.topo-card-state {
  flex: none;
  font-size: 10px;
}
.topo-card-empty {
  margin-top: 6px;
  font-size: 10px;
  color: var(--color-text-secondary, #8a9bb0);
}
.topo-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
  flex: none;
}
.topo-legend {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
  padding: 10px 16px;
  border-top: 1px solid var(--color-border-subtle);
  font-size: 11px;
  color: var(--color-text-secondary);
}
.topo-legend-group {
  display: flex;
  align-items: center;
  gap: 10px;
}
.topo-legend-h {
  font-size: 10px;
  letter-spacing: 0.06em;
  opacity: 0.7;
}
.topo-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.topo-legend-shape {
  padding: 1px 6px;
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--tile-radius-xs, 6px);
  font-size: 10px;
}
.topo-legend-shape svg {
  display: block;
  flex: none;
}
.topo-legend-hint {
  margin-left: auto;
  font-size: 10px;
  opacity: 0.7;
}
.topo-fade-enter-active,
.topo-fade-leave-active {
  transition: opacity 0.16s ease;
}
.topo-fade-enter-from,
.topo-fade-leave-to {
  opacity: 0;
}
</style>
