<template>
  <!-- Pet widget: floats on the page, can be dragged and remembers its position -->
  <Teleport to="body">
    <div
      v-show="petVisible"
      class="pet-float"
      :class="petClasses"
      :style="{ left: petPos.x + 'px', top: petPos.y + 'px' }"
      aria-hidden="true"
      @contextmenu.prevent
    >
      <div class="pet-inner">
        <div class="pet-glow"></div>
        <div class="pet-rune-ring" aria-hidden="true">
          <div class="pet-rune-orbit">
            <span
              v-for="(b, i) in petRuneBits"
              :key="i"
              class="pet-rune-bit"
              :style="petRuneBitStyle(i)"
            ><span class="pet-rune-glyph">{{ b }}</span></span>
          </div>
          <div class="pet-rune-core"></div>
        </div>
        <div class="pet-bubble">{{ petBubbleText }}</div>
        <div class="pet-body">
          <div class="pet-head" :style="petHeadStyle">
            <div class="pet-ear l"></div>
            <div class="pet-ear r"></div>
            <div class="pet-eye l"><div class="pet-pupil" :style="petPupilStyle"></div></div>
            <div class="pet-eye r"><div class="pet-pupil" :style="petPupilStyle"></div></div>
            <div class="pet-mouth"></div>
          </div>
          <div class="pet-tail"></div>
        </div>
        <div class="pet-shadow"></div>
        <div class="pet-spark s1"></div>
        <div class="pet-spark s2"></div>
        <div class="pet-spark s3"></div>
        <div class="pet-orbit orbit-a" aria-hidden="true">
          <div class="pet-orbit-track">
            <span class="pet-orbit-mote"></span>
            <span class="pet-orbit-mote"></span>
            <span class="pet-orbit-mote"></span>
          </div>
        </div>
        <div class="pet-orbit orbit-b" aria-hidden="true">
          <div class="pet-orbit-track">
            <span class="pet-orbit-rune">✦</span>
            <span class="pet-orbit-rune">✧</span>
            <span class="pet-orbit-rune">✶</span>
          </div>
        </div>
        <div class="pet-zzz z1">z</div>
        <div class="pet-zzz z2">z</div>
        <div class="pet-zzz z3">Z</div>
        <div
          v-if="petBadgeText"
          class="pet-badge"
          :class="{ 'is-alert': petWaitingAgents.length > 0, 'is-clickable': petWaitingAgents.length > 0 }"
          :title="petWaitingAgents.length > 0 ? (petWaitingAgents.length + ' items Agent Waiting for input，ClickGo to to Next') : (petRunningCount + ' items Agent Running middle ')"
          @pointerdown.stop
          @click.stop="onPetBadgeClick"
        >{{ petBadgeText }}</div>
        <div class="pet-label">✦ HAIJUNBOT ✦</div>
        <button
          class="pet-sfx-btn"
          :class="{ 'is-off': !petSfxOn }"
          :title="petSfxOn ? 'Turn off pet SFX' : 'Turn on pet SFX'"
          @click.stop="togglePetSfx"
        >{{ petSfxOn ? '🔊' : '🔇' }}</button>
        <button
          class="pet-pin-btn"
          :class="{ 'is-on': petPinned }"
          :title="petPinned ? 'Unpin (allow the pet to roam)' : 'Pin pet (forbid the pet to roam)'"
          @click.stop="togglePetPin"
        >{{ petPinned ? '📌' : '📍' }}</button>
        <button
          class="pet-power-btn"
          :class="{ 'is-on': petPowerSave }"
          :title="petPowerSave ? 'Turn off power-saving mode (restore effects)' : 'Turn on power-saving mode (turn off effects, lower power usage)'"
          @click.stop="togglePetPowerSave"
        >{{ petPowerSave ? '🔋' : '⚡' }}</button>
        <div
          class="pet-hit"
          @pointerdown="onPetPointerDown"
          @pointermove="onPetPointerMove"
          @pointerup="onPetPointerUp"
          @pointercancel="onPetPointerUp"
          @contextmenu.prevent.stop
          @mouseenter="petHover = true; clearPetEdgeLeaveTimer()"
          @mouseleave="petHover = false"
        ></div>
      </div>
    </div>

    <!-- Edge-docked collapsed state: the hover-out trigger element fixed at the inner side edge of the screen (most of the pet is outside the viewport, relying on it to accept mouse entry).
         positioned independently in .pet-float (position:fixed), does not follow the pet's slide-in/slide-out animation movement,
         otherwise during the animation the trigger element would run off-screen along with the pet, causing the mouse cursor to repeatedly enter/leave and jitter.
         In the expanded state, retraction is instead determined by document's mousemove (see onPetMouseMove),
         to avoid the pet's hot zone sweeping across the mouse cursor position mid-animation, stealing hover and causing repeated jitter -->
    <div
      v-show="petEdge && !petEdgeRevealed && petVisible"
      class="pet-edge-trigger"
      :class="petEdge === 'left' ? 'is-left' : 'is-right'"
      :style="{ top: petPos.y + 'px', height: petH() + 'px', width: petEdgePeek() + 'px' }"
      @mouseenter="onPetEdgeEnter"
      @pointerdown.stop.prevent="onPetEdgeActivate"
      @click.stop.prevent="onPetEdgeActivate"
    ></div>

    <!-- Mini network topology beside the pet (hidden together with the pet in the edge-docked collapsed state) -->
    <PetMiniTopology
      v-show="petVisible && petTopoOn && !petPowerSaveActive && (!petEdge || petEdgeRevealed)"
      :nodes="nodes"
      :agents="agentList || []"
      :getStatusClass="getStatusClass"
      :extensionSessions="extensionSessions || []"
      :daemonSessions="daemonSessions || []"
      :localDaemonOnline="localDaemonOnline"
      :x="petMiniPos.x"
      :y="petMiniPos.y"
      @open="petOpenTopology"
    />
    <!-- Restore button after hiding -->
    <button
      v-if="props.isConnected && petHidden"
      class="pet-restore"
      :style="{ left: restorePos.x + 'px', top: restorePos.y + 'px' }"
      title="Bring pet back (draggable)"
      @pointerdown="onRestorePointerDown"
      @pointermove="onRestorePointerMove"
      @pointerup="onRestorePointerUp"
      @pointercancel="onRestorePointerUp"
      @contextmenu.prevent.stop
    >🐾</button>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import PetMiniTopology from './PetMiniTopology.vue'

const props = defineProps({
  isConnected: { type: Boolean, default: true },
  windowWidth: Number,
  agentList: Array,
  agentStatuses: Map,
  isWaitingInput: Function,
  currentAgentId: String,
  nodes: { type: Array, default: () => [] },
  getStatusClass: Function,
  // Connected browser extension sessions (Gateway /api/browser-ext/sessions), passed through to the mini topology
  extensionSessions: { type: Array, default: () => [] },
  // Connected backend service sessions (Gateway /api/daemon/sessions), passed through to the mini topology
  daemonSessions: { type: Array, default: () => [] },
  // Whether a backend service is already installed and running locally (local loopback /api/status probe), passed through to the mini topology for the hide install guide
  localDaemonOnline: { type: Boolean, default: false },
})
const emit = defineEmits([
  'petSyncStatus',
  'petInterruptCurrent',
  'petGotoWaiting',
  'petToggleSidebar',
  'petOpenTopology',
  'petOpenCommandPalette',
  'openQuickCreate',
])

// ==================== Pet widget ====================
const PET_POS_KEY = 'haijunbot_pet_pos'
const PET_TOPO_KEY = 'haijunbot_pet_topo'
const PET_RESTORE_POS_KEY = 'haijunbot_pet_restore_pos'
const PET_HIDDEN_KEY = 'haijunbot_pet_hidden'
const PET_POWER_SAVE_KEY = 'haijunbot_pet_power_save'
const PET_PIN_KEY = 'haijunbot_pet_pinned'
const PET_EDGE_KEY = 'haijunbot_pet_edge'
// Edge-dock threshold: when dragging ends, if the distance to the screen's left/right edge is less than this value it snaps
const PET_EDGE_SNAP = 24
// Width (in pixels) still exposed after edge-dock collapse: ensures a corner of the pet is still visible in the collapsed state, for easy locating
const PET_EDGE_PEEK_DESKTOP = 28
const PET_EDGE_PEEK_MOBILE = 40
// Delay (in milliseconds) before retracting after the mouse leaves: avoids jitter when moving between the trigger element and the pet
const PET_EDGE_LEAVE_DELAY = 160
// The mobile pet is scaled down by half overall (matching .pet-float's scale(0.5)); this is the actual visual size
const PET_SCALE_MOBILE = 0.5
const PET_W = 200
const PET_H = 230
const RESTORE_W = 40
const RESTORE_H = 40
// Pet visual size: mobile is half of desktop (kept consistent with the CSS zoom)
function petW() {
  return isMobileView.value ? Math.round(PET_W * PET_SCALE_MOBILE) : PET_W
}
function petH() {
  return isMobileView.value ? Math.round(PET_H * PET_SCALE_MOBILE) : PET_H
}
// Width exposed after edge-dock collapse: the mobile pet is scaled down by scale(0.5), so a larger original value is needed to expose a recognizable corner
function petEdgePeek() {
  return isMobileView.value ? PET_EDGE_PEEK_MOBILE : PET_EDGE_PEEK_DESKTOP
}
const petPos = ref({ x: 0, y: 0 })
const restorePos = ref({ x: 0, y: 0 })
const petHover = ref(false)
const petDrag = ref(false)
const petJump = ref(false)
const petAction = ref('')
const petPupil = ref({ x: 0, y: 0 })
const petTilt = ref(0)
const petFaceDir = ref(1)   // Facing: 1 = right, -1 = left
// Enrich interactions with new states
const petSleep = ref(false)      // Dozing
const petPetting = ref(false)    // Being petted
const petHidden = ref(false)     // AlreadyHide
const petWalking = ref(false)    // Robot strolling
const petSpeech = ref('')        // Robot lines
const petTopoOn = ref(true)      // Whether to show the mini topology
const petCast = ref('')          // Spell type being cast ('' means not casting)
const petPowerSave = ref(false)  // Power-saving mode: turns off all decorative effects and constant computations (can be enabled on both mobile and desktop)
const petPinned = ref(false)     // Pin pet: forbids the robot from strolling (does not affect other interactions)
// Edge-docked hidden: 'left' | 'right' | null; non-null means already snapped to that side and collapsed
const petEdge = ref(null)
// Whether it temporarily slides out in the edge-docked collapsed state (expands when the mouse enters)
const petEdgeRevealed = ref(false)
// Timer for delayed retraction after the mouse leaves in the edge-docked state
let petEdgeLeaveTimer = 0

// Whether on mobile (used for overall pet scaling, etc.; no longer restricted by the power-saving mode toggle)
const isMobileView = computed(() => (props.windowWidth || window.innerWidth) <= 768)
// Whether power-saving mode is in effect: takes effect as soon as the toggle is on (can be used on both mobile and desktop)
const petPowerSaveActive = computed(() => petPowerSave.value)

// Overhead digit magic circle: a ring of 0/1 spirit runes, fantasy style, linked to the follow state
const PET_RUNE_COUNT = 18
const PET_RUNE_RADIUS = 62
const petRuneBits = Array.from({ length: PET_RUNE_COUNT }, (_, i) =>
  (i * 7 + 3) % 3 === 0 ? '1' : '0'
)
function petRuneBitStyle(i) {
  const step = 360 / PET_RUNE_COUNT
  const angle = i * step
  // Per-character robot phase/duration, creating a staggered feel of flickering spirit light
  const delay = ((i * 37) % 100) / 100 * 2.4
  const dur = 1.8 + ((i * 53) % 100) / 100 * 1.6
  return {
    transform: `rotate(${angle}deg) translateY(-${PET_RUNE_RADIUS}px)`,
    '--rune-glow-delay': delay.toFixed(2) + 's',
    '--rune-glow-dur': dur.toFixed(2) + 's',
  }
}

// When not connected (e.g. login UI), the pet and its attached UI are not shown
const petVisible = computed(() => props.isConnected && !petHidden.value)

// Robot line library
const PET_LINES = [
  'Hi there~',
  'Keep up the good work today too!',
  'Need any help?',
  'I am right here with you~',
  'Remember to take a break, okay',
  'Hehe, you got to pet me',
  'Any new tasks?',
  'I have always been here ✦',
]

// Encouragement line library: shown by the robot on a schedule, replacing the original always-on "need input" tip
const PET_ENCOURAGE_LINES = [
  'Keep going, you can do it!',
  'Take it slow, no rush~',
  'You are already awesome ✦',
  'Hold on just a little longer!',
  'Have a sip of water and rest a bit',
  'I am here, do not worry~',
  'Thanks for your hard work today too',
  'Everything will get better',
  'Take a deep breath and keep it up!',
  'I see all your efforts',
  'Do not put too much pressure on yourself',
  'Charge ahead! I am with you ✦',
]

// PetStatus：waiting（Has Agent Waiting for input）| running（Has Agent Running middle ）| idle
const petState = computed(() => {
  const list = props.agentList || []
  if (list.some(a => props.isWaitingInput && props.isWaitingInput(a))) return 'waiting'
  const statuses = props.agentStatuses
  if (statuses && list.some(a => {
    const st = statuses.get(a.agent_id)
    return st && (st.execution_status === 'running' || st.execution_status === 'executing')
  })) return 'running'
  return 'idle'
})

// Bubble text: only shows temporary lines (no longer always shown while waiting for input)
const petBubbleText = computed(() => {
  return petSpeech.value
})

// ==================== Gateway actions: pet status aggregation ====================
// List of agents waiting for input
const petWaitingAgents = computed(() =>
  (props.agentList || []).filter(a => props.isWaitingInput && props.isWaitingInput(a))
)

// Number of running agents
const petRunningCount = computed(() => {
  const list = props.agentList || []
  const statuses = props.agentStatuses
  if (!statuses) return 0
  return list.filter(a => {
    const st = statuses.get(a.agent_id)
    return st && (st.execution_status === 'running' || st.execution_status === 'executing')
  }).length
})

// Badge text: show the waiting count first, then the running count
const petBadgeText = computed(() => {
  if (petWaitingAgents.value.length > 0) return String(petWaitingAgents.value.length)
  if (petRunningCount.value > 0) return String(petRunningCount.value)
  return ''
})

// Click the overhead badge: go to the next agent waiting for input (the parent component handles cycling)
function onPetBadgeClick() {
  if (petWaitingAgents.value.length === 0) return
  emit('petGotoWaiting')
}

// Category of the currently cast spell (array/throw/beam/swarm), used to distinguish effects and the state class
const PET_CAST_KINDS = {
  thunder: 'array', flame: 'array', frost: 'array', star: 'array',
  rune: 'throw', bolt: 'beam', sword: 'beam', swarm: 'swarm',
}
const petCastKind = computed(() => PET_CAST_KINDS[petCast.value] || '')

const petClasses = computed(() => [
  'is-' + petState.value,
  {
    'is-hover': petHover.value,
    'is-drag': petDrag.value,
    'is-jump': petJump.value,
    'is-speak': !!petSpeech.value,
    'is-sleep': petSleep.value,
    'is-petting': petPetting.value,
    'is-walk': petWalking.value,
    'face-left': petFaceDir.value < 0,
    'rune-running': petState.value === 'running',
    'rune-waiting': petWaitingAgents.length > 0,
    'rune-sleep': petSleep.value,
    // is-casting is only used for "magic circle category" spells, to avoid overwriting the animations of other spells like act-throw
    'is-casting': petCastKind.value === 'array',
    'power-save': petPowerSaveActive.value,
    'pet-compact': isMobileView.value,
  },
  petAction.value ? 'act-' + petAction.value : '',
  petCast.value ? 'cast-' + petCast.value : '',
])
// Whether viewing the mini topology (open and pet visible/awake; not shown in power-saving mode, to avoid constant rendering)
const petWatchingTopo = computed(() => petTopoOn.value && !petPowerSaveActive.value && !petHidden.value && !petSleep.value)

// Horizontal offset of the mini map relative to the pet's center: -1 left / 0 center / 1 right
const petTopoDirX = computed(() => {
  const headCx = petPos.value.x + petW() / 2
  const topoCx = petMiniPos.value.x + 48
  const d = topoCx - headCx
  if (d > 8) return 1
  if (d < -8) return -1
  return 0
})

// Actual pupil offset: when viewing the mini map, look up (in its direction), otherwise follow the mouse cursor
const petEffectivePupil = computed(() => {
  if (petWatchingTopo.value && !petHover.value && !petDrag.value) {
    return { x: petTopoDirX.value * 3, y: -4 }
  }
  return petPupil.value
})

const petPupilStyle = computed(() => ({
  transform: `translate(calc(-50% + ${petEffectivePupil.value.x}px), calc(-50% + ${petEffectivePupil.value.y}px))`,
}))

// Mini topology position: placed in front above the pet's head (without covering the pet's body); when space is insufficient, falls back below/to the side, and is kept within the viewport
const petMiniPos = computed(() => {
  const MINI = 96
  const vw = window.innerWidth
  const vh = window.innerHeight
  const maxX = Math.max(4, vw - MINI - 4)
  const maxY = Math.max(4, vh - MINI - 4)
  const clampX = (x) => Math.max(4, Math.min(maxX, x))
  const clampY = (y) => Math.max(4, Math.min(maxY, y))

  // Preferred: centered above the pet's head (the pet looks up at it)
  const topX = petPos.value.x + petW() / 2 - MINI / 2
  const topY = petPos.value.y - MINI - 6
  if (topY >= 4) return { x: clampX(topX), y: topY }

  // Fallback 1: centered below the pet
  const belowY = petPos.value.y + petH() + 6
  if (belowY <= maxY) return { x: clampX(topX), y: belowY }

  // Fallback 2: right of the pet
  const sideX = petPos.value.x + petW() + 6
  const sideY = petPos.value.y + petH() / 2 - MINI / 2
  if (sideX <= maxX) return { x: sideX, y: clampY(sideY) }

  // Final: left of the pet
  return { x: clampX(petPos.value.x - MINI - 6), y: clampY(sideY) }
})

const petHeadStyle = computed(() => {
  if (petHover.value || petDrag.value) return {}
  // When viewing the mini topology: look up (slight upward shift) and lean toward the side of the mini map
  if (petWatchingTopo.value) {
    const tilt = petTopoDirX.value * 4
    return { transform: `translateX(-50%) translateY(-3px) rotate(${tilt}deg)` }
  }
  return { transform: `translateX(-50%) rotate(${petTilt.value}deg)` }
})

function clampPetPos(x, y) {
  const maxX = Math.max(0, window.innerWidth - petW())
  const maxY = Math.max(0, window.innerHeight - petH())
  return { x: Math.max(0, Math.min(maxX, x)), y: Math.max(0, Math.min(maxY, y)) }
}

// ==================== Edge-docked hiding ====================
// X of the pet's top-left corner when edge-docked collapsed: docked left exposes a little of its right side, docked right exposes a little of its left side
function petEdgeCollapsedX(edge) {
  return edge === 'left' ? -(petW() - petEdgePeek()) : window.innerWidth - petEdgePeek()
}

// X of the pet's top-left corner when edge-docked expanded: flush against that side's edge
function petEdgeExpandedX(edge) {
  return edge === 'left' ? 0 : Math.max(0, window.innerWidth - petW())
}

// Update the pet's x based on the edge-dock state and whether it temporarily slides out (the docked state skips clamping, allowing it to go outside the viewport)
function applyPetEdge() {
  if (!petEdge.value) return
  const x = petEdgeRevealed.value
    ? petEdgeExpandedX(petEdge.value)
    : petEdgeCollapsedX(petEdge.value)
  petPos.value = { x, y: petPos.value.y }
}

// Drag end: snapped and collapsed when near the left/right edge, otherwise edge-docking is canceled
function snapPetToEdge() {
  const x = petPos.value.x
  const maxX = Math.max(0, window.innerWidth - petW())
  const nearLeft = x <= PET_EDGE_SNAP
  const nearRight = x >= maxX - PET_EDGE_SNAP
  if (nearLeft || nearRight) {
    petEdge.value = nearLeft ? 'left' : 'right'
    petEdgeRevealed.value = false
    applyPetEdge()
  } else {
    petEdge.value = null
    petEdgeRevealed.value = false
  }
  savePetEdge()
}

// Mouse enter: temporarily slides out in the edge-docked state, for easy interaction
function onPetEdgeEnter() {
  if (!petEdge.value || petEdgeRevealed.value) return
  clearPetEdgeLeaveTimer()
  petEdgeRevealed.value = true
  applyPetEdge()
}

// Click/touch trigger element: bring the pet fully back onto the screen (completely releasing edge-docking).
// On desktop, when the mouse enters the trigger element, onPetEdgeEnter already makes it temporarily slide out; clicking here likewise releases edge-docking,
// avoiding the flicker of "slid out then retracted again by mousemove"; on mobile there is no hover, so a click brings it back directly.
function onPetEdgeActivate() {
  if (!petEdge.value) return
  clearPetEdgeLeaveTimer()
  const edge = petEdge.value
  // First slide out to that side's edge, then release edge-docking and clamp back into the visible area, avoiding a position jump
  const expandedX = petEdgeExpandedX(edge)
  petEdge.value = null
  petEdgeRevealed.value = false
  petPos.value = clampPetPos(expandedX, petPos.value.y)
  savePetEdge()
  savePetPos()
  petSfxChirp()
}

// Mouse leave: slides back and collapses in the edge-docked state (delayed execution, avoiding jitter when moving between the trigger element and the pet)
function onPetEdgeLeave() {
  if (!petEdge.value || !petEdgeRevealed.value) return
  clearPetEdgeLeaveTimer()
  petEdgeLeaveTimer = window.setTimeout(() => {
    petEdgeLeaveTimer = 0
    if (!petEdge.value || !petEdgeRevealed.value) return
    petEdgeRevealed.value = false
    applyPetEdge()
  }, PET_EDGE_LEAVE_DELAY)
}

function clearPetEdgeLeaveTimer() {
  if (petEdgeLeaveTimer) {
    clearTimeout(petEdgeLeaveTimer)
    petEdgeLeaveTimer = 0
  }
}

function savePetEdge() {
  try {
    localStorage.setItem(PET_EDGE_KEY, petEdge.value || '')
  } catch (e) {
    console.warn('[AGENT_SIDEBAR] Failed to save pet edge:', e)
  }
}

function initPetEdge() {
  let saved = ''
  try {
    saved = localStorage.getItem(PET_EDGE_KEY) || ''
  } catch (e) {
    saved = ''
  }
  if (saved === 'left' || saved === 'right') {
    petEdge.value = saved
    petEdgeRevealed.value = false
    applyPetEdge()
  }
}

// The restore button is independent of the pet's size and can be dragged to any corner of the screen
function clampRestorePos(x, y) {
  const maxX = Math.max(0, window.innerWidth - RESTORE_W)
  const maxY = Math.max(0, window.innerHeight - RESTORE_H)
  return { x: Math.max(0, Math.min(maxX, x)), y: Math.max(0, Math.min(maxY, y)) }
}

function saveRestorePos() {
  try {
    localStorage.setItem(PET_RESTORE_POS_KEY, JSON.stringify(restorePos.value))
  } catch (e) {
    console.warn('[AGENT_SIDEBAR] Failed to save pet restore position:', e)
  }
}

function initRestorePos() {
  let saved = null
  try {
    saved = JSON.parse(localStorage.getItem(PET_RESTORE_POS_KEY) || 'null')
  } catch (e) {
    saved = null
  }
  if (saved && typeof saved.x === 'number' && typeof saved.y === 'number') {
    restorePos.value = clampRestorePos(saved.x, saved.y)
    restoreUserMoved = true
    return
  }
  // Defaults to match the pet's current position
  restorePos.value = clampRestorePos(petPos.value.x, petPos.value.y)
}

function savePetPos() {
  try {
    localStorage.setItem(PET_POS_KEY, JSON.stringify(petPos.value))
  } catch (e) {
    console.warn('[AGENT_SIDEBAR] Failed to save pet position:', e)
  }
}

function initPetPos() {
  let saved = null
  try {
    saved = JSON.parse(localStorage.getItem(PET_POS_KEY) || 'null')
  } catch (e) {
    saved = null
  }
  if (saved && typeof saved.x === 'number' && typeof saved.y === 'number') {
    petPos.value = clampPetPos(saved.x, saved.y)
    return
  }
  // DefaultPosition：SidebarBottomCentered
  const sidebar = document.querySelector('.agent-sidebar')
  const rect = sidebar ? sidebar.getBoundingClientRect() : { left: 0, width: 320 }
  petPos.value = clampPetPos(
    rect.left + (rect.width - petW()) / 2,
    window.innerHeight - petH() - 8
  )
}

let petRaf = 0
function onPetMouseMove(e) {
  // Edge-docked expanded state: use the mouse position to determine whether it is still within the "pet ∪ trigger element" range, deciding retraction.
  // Does not rely on the element's mouseleave, to avoid the pet's hot zone sweeping across the mouse cursor position mid-slide-out animation, stealing hover and causing repeated jitter
  if (petVisible.value && petEdge.value && petEdgeRevealed.value) {
    const f = document.querySelector('.pet-float')
    if (f) {
      const r = f.getBoundingClientRect()
      // The pet rectangle (including the part exposed when collapsed) and the inner-side screen trigger element together form the "keep expanded" area
      const inPet = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom
      const inTrigger = petEdge.value === 'left'
        ? e.clientX <= petEdgePeek()
        : e.clientX >= window.innerWidth - petEdgePeek()
      if (inPet || inTrigger) clearPetEdgeLeaveTimer()
      else onPetEdgeLeave()
    }
  }
  if (petRaf) return
  petRaf = requestAnimationFrame(() => {
    petRaf = 0
    // Does not track the mouse cursor while sleeping/hidden
    if (petSleep.value || petHidden.value) return
    const head = document.querySelector('.pet-float .pet-head')
    if (!head) return
    const r = head.getBoundingClientRect()
    const cx = r.left + r.width / 2
    const cy = r.top + r.height / 2
    const dx = e.clientX - cx
    const dy = e.clientY - cy
    const d = Math.hypot(dx, dy) || 1
    const max = 4.5
    petPupil.value = {
      x: (dx / d) * Math.min(max, d / 14),
      y: (dy / d) * Math.min(max, d / 14),
    }
    if (!petHover.value && !petDrag.value) {
      petTilt.value = Math.max(-6, Math.min(6, dx / 22))
    }
  })
}

let petDragging = false
let petMoved = false
let petStartX = 0
let petStartY = 0
let petOriginX = 0
let petOriginY = 0

// Interaction decision timer
let petClickTimer = 0    // Single-click delay decision
let petSpeechTimer = 0   // Line bubble
let petHideTimer = 0     // Hide timer (kept for compatibility)
let petPettingFxTimer = 0      // Petting heart loop

// Long press triggers one-sentence agent creation: holding the main pet for 600ms without moving triggers it
const PET_LONG_PRESS_MS = 600
let petLongPressTimer = 0      // Long press decision timer
let petLongPressFired = false  // Long press already triggered this gesture (suppresses subsequent single/double clicks)

// ==================== Pet radial menu ====================
let petMenuLongPressTimer = 0               // Restore button long press decision

function onPetPointerDown(e) {
  if (e.button !== undefined && e.button !== 0) return  // Left button only
  stopPetWalk()
  petDragging = true
  petMoved = false
  petLongPressFired = false
  petStartX = e.clientX
  petStartY = e.clientY
  petOriginX = petPos.value.x
  petOriginY = petPos.value.y
  // Start long press decision: no movement within 600ms (not turning into a drag) triggers one-sentence agent creation
  clearTimeout(petLongPressTimer)
  petLongPressTimer = window.setTimeout(() => {
    petLongPressTimer = 0
    petLongPressFired = true
    emit('openQuickCreate')
  }, PET_LONG_PRESS_MS)
  e.target.setPointerCapture?.(e.pointerId)
  e.preventDefault()
}

// Right-click: intercepts the browser default menu and does nothing (the track menu is no longer triggered by right-click)

function onPetPointerMove(e) {
  if (!petDragging) return
  const dx = e.clientX - petStartX
  const dy = e.clientY - petStartY
  if (!petMoved && Math.hypot(dx, dy) > 5) {
    petMoved = true
    petDrag.value = true
    // Already determined to be a drag: cancel the long press trigger, to avoid accidentally opening one-sentence creation during dragging
    if (petLongPressTimer) {
      clearTimeout(petLongPressTimer)
      petLongPressTimer = 0
    }
    if (petPetting.value) stopPetting()
  }
  if (petMoved) {
    petPos.value = clampPetPos(petOriginX + dx, petOriginY + dy)
  }
}

function onPetPointerUp(e) {
  if (!petDragging) return
  petDragging = false
  clearTimeout(petLongPressTimer)
  petLongPressTimer = 0
  e.target.releasePointerCapture?.(e.pointerId)
  if (petMoved) {
    petDrag.value = false
    snapPetToEdge()
    savePetPos()
    return
  }
  petDrag.value = false
  // Long press already triggered one-sentence creation: this release no longer responds to single/double clicks
  if (petLongPressFired) {
    petLongPressFired = false
    return
  }
  // Single / double click decision
  if (petClickTimer) {
    // Second within 300ms: double click → confetti celebration and open the command panel (behavior swapped with right-click)
    clearTimeout(petClickTimer)
    petClickTimer = 0
    onPetDoubleClick(e.clientX, e.clientY)
    return
  }
  const cx = e.clientX
  const cy = e.clientY
  petClickTimer = window.setTimeout(() => {
    petClickTimer = 0
    onPetSingleClick(cx, cy)
  }, 300)
}

// Single click: sleep then wake; otherwise jump + particles + sound effect + robot line
function onPetSingleClick(x, y) {
  if (petSleep.value) {
    wakePet()
    return
  }
  petJump.value = true
  setTimeout(() => { petJump.value = false }, 560)
  spawnPetFx(x, y)
  petSfxChirp()
  showPetSpeech()
}

// Double-click behavior: confetti celebration and open the command panel
function onPetDoubleClick(x, y) {
  wakePet()
  petJump.value = true
  setTimeout(() => { petJump.value = false }, 560)
  petAction.value = 'cheer'
  setTimeout(() => { if (petAction.value === 'cheer') petAction.value = '' }, 1600)
  spawnPetConfetti(x, y)
  spawnPetFx(x, y)
  petSfxCheer()
  showPetSpeech()
  emit('petOpenCommandPalette')
}

// Robot line bubble: shown for 2s
function showPetSpeech() {
  petSpeech.value = PET_LINES[Math.floor(Math.random() * PET_LINES.length)]
  clearTimeout(petSpeechTimer)
  petSpeechTimer = window.setTimeout(() => { petSpeech.value = '' }, 2000)
}

// Encouragement lines shown by the robot on a schedule (about once every 20~40s, shown for 4s)
let petEncourageTimer = 0
function schedulePetEncourage() {
  clearTimeout(petEncourageTimer)
  petEncourageTimer = window.setTimeout(() => {
    if (!petPowerSaveActive.value && !document.hidden && !petHidden.value && !petSleep.value &&
        !petHover.value && !petDrag.value && !petPetting.value && !petWalking.value) {
      petSpeech.value = PET_ENCOURAGE_LINES[Math.floor(Math.random() * PET_ENCOURAGE_LINES.length)]
      clearTimeout(petSpeechTimer)
      petSpeechTimer = window.setTimeout(() => { petSpeech.value = '' }, 4000)
    }
    schedulePetEncourage()
  }, 20000 + Math.random() * 20000)
}

// Confetti effect
function spawnPetConfetti(x, y) {
  const colors = ['#20c8ff', '#7ee7ff', '#ff8ad8', '#ffd166', '#a78bfa']
  for (let i = 0; i < 14; i++) {
    const el = document.createElement('div')
    el.className = 'pet-confetti'
    el.style.left = x + 'px'
    el.style.top = y + 'px'
    el.style.background = colors[i % colors.length]
    el.style.setProperty('--dx', (Math.random() * 120 - 60) + 'px')
    el.style.setProperty('--dy', (-40 - Math.random() * 70) + 'px')
    el.style.setProperty('--rot', (Math.random() * 540 - 270) + 'deg')
    el.style.animationDelay = (i * 0.02) + 's'
    document.body.appendChild(el)
    setTimeout(() => el.remove(), 1400)
  }
}

// Petting
function startPetting() {
  wakePet()
  petPetting.value = true
  petSfxPurr()
  spawnPetHearts()
  clearInterval(petPettingFxTimer)
  petPettingFxTimer = window.setInterval(spawnPetHearts, 420)
}

function stopPetting() {
  petPetting.value = false
  clearInterval(petPettingFxTimer)
  petPettingFxTimer = 0
}

// Hearts pop out (based on the pet's current position)
function spawnPetHearts() {
  const el = document.querySelector('.pet-float')
  const r = el ? el.getBoundingClientRect() : { left: petPos.value.x, top: petPos.value.y, width: petW(), height: petH() }
  const x = r.left + r.width / 2
  const y = r.top + r.height * 0.28
  for (let i = 0; i < 2; i++) {
    const h = document.createElement('div')
    h.className = 'pet-heart-fx'
    h.textContent = Math.random() > 0.5 ? '❤' : '💗'
    h.style.left = (x + (Math.random() * 40 - 20)) + 'px'
    h.style.top = (y + (Math.random() * 16 - 8)) + 'px'
    h.style.setProperty('--dx', (Math.random() * 50 - 25) + 'px')
    document.body.appendChild(h)
    setTimeout(() => h.remove(), 1300)
  }
}

// ==================== MenuAction ====================
// Feeding: food drops down + chewing
function petFeed() {
  wakePet()
  const el = document.querySelector('.pet-float')
  const r = el ? el.getBoundingClientRect() : { left: petPos.value.x, top: petPos.value.y, width: petW(), height: petH() }
  const food = document.createElement('div')
  food.className = 'pet-food'
  food.textContent = '🍖'
  food.style.left = (r.left + r.width / 2) + 'px'
  food.style.top = (r.top + r.height * 0.1) + 'px'
  document.body.appendChild(food)
  setTimeout(() => food.remove(), 900)
  setTimeout(() => {
    petAction.value = 'chomp'
    setTimeout(() => { if (petAction.value === 'chomp') petAction.value = '' }, 1000)
    petSfxChomp()
    spawnPetHearts()
  }, 520)
}

// Play ball: ball flies by + chasing
function petPlayBall() {
  wakePet()
  const el = document.querySelector('.pet-float')
  const r = el ? el.getBoundingClientRect() : { left: petPos.value.x, top: petPos.value.y, width: petW(), height: petH() }
  const ball = document.createElement('div')
  ball.className = 'pet-ball'
  ball.textContent = '🎾'
  ball.style.left = (r.left - 30) + 'px'
  ball.style.top = (r.top + r.height * 0.62) + 'px'
  ball.style.setProperty('--fly', (r.width + 70) + 'px')
  document.body.appendChild(ball)
  setTimeout(() => ball.remove(), 1500)
  petAction.value = 'chase'
  setTimeout(() => { if (petAction.value === 'chase') petAction.value = '' }, 1400)
  petSfxChirp()
}

// Doze / wake
let petSleepTimer = 0   // Timer for waking up automatically after sleeping a while
// Each time it sleeps, the robot naps for 20~40 seconds and then wakes up on its own
function schedulePetWake() {
  clearTimeout(petSleepTimer)
  petSleepTimer = window.setTimeout(() => {
    petSleepTimer = 0
    if (petSleep.value) wakePet()
  }, 20000 + Math.random() * 20000)
}

// Wake (if sleeping), and clear the auto-wake timer
function wakePet() {
  clearTimeout(petSleepTimer)
  petSleepTimer = 0
  if (petSleep.value) {
    petSleep.value = false
    petSfxChirp()
  }
}

function togglePetSleep() {
  petSleep.value = !petSleep.value
  if (petSleep.value) {
    petSpeech.value = ''
    petSfxYawn()
    schedulePetWake()
  } else {
    clearTimeout(petSleepTimer)
    petSleepTimer = 0
    petSfxChirp()
  }
}

// Singing: musical notes drift out + scale
function petSing() {
  wakePet()
  const el = document.querySelector('.pet-float')
  const r = el ? el.getBoundingClientRect() : { left: petPos.value.x, top: petPos.value.y, width: petW(), height: petH() }
  const notes = ['♪', '♫', '🎵', '♬']
  for (let i = 0; i < 6; i++) {
    const n = document.createElement('div')
    n.className = 'pet-note'
    n.textContent = notes[i % notes.length]
    n.style.left = (r.left + r.width / 2 + (Math.random() * 50 - 25)) + 'px'
    n.style.top = (r.top + r.height * 0.3) + 'px'
    n.style.setProperty('--dx', (Math.random() * 50 - 25) + 'px')
    n.style.animationDelay = (i * 0.16) + 's'
    document.body.appendChild(n)
    setTimeout(() => n.remove(), 1800)
  }
  petAction.value = 'sing'
  setTimeout(() => { if (petAction.value === 'sing') petAction.value = '' }, 1400)
  petSfxSong()
}

// Hide pet (stays hidden until manually brought back; at the same time stops related computations to save resources)
function petHide() {
  stopPetting()
  // When not manually dragged, the restore button appears at the pet's current position for a coherent experience
  if (!restoreUserMoved) {
    restorePos.value = clampRestorePos(petPos.value.x, petPos.value.y)
  }
  petHidden.value = true
  try { localStorage.setItem(PET_HIDDEN_KEY, '1') } catch (e) {}
  clearTimeout(petHideTimer)
  stopPetLoops()
}

function showPet() {
  clearTimeout(petHideTimer)
  petHidden.value = false
  try { localStorage.setItem(PET_HIDDEN_KEY, '0') } catch (e) {}
  startPetLoops()
  petSfxChirp()
}

// Toggle pet show/hide (called externally by the command panel, etc.)
function togglePet() {
  if (petHidden.value) {
    showPet()
  } else {
    petHide()
  }
}

// Restore button (🐾) drag: position independent of the pet's size, can be dragged to any corner of the screen
let restoreDragging = false
let restoreMoved = false
let restoreUserMoved = false  // Whether the user manually dragged the restore button
let restoreLongPressFired = false  // Long press already triggered this time (confetti + command panel)
let restoreClickTimer = 0     // Single-click delay decision (distinguishes single-click restore / double-click confetti + command panel)
let restoreStartX = 0
let restoreStartY = 0
let restoreOriginX = 0
let restoreOriginY = 0

function onRestorePointerDown(e) {
  if (e.button !== undefined && e.button !== 0) return  // Left button only
  restoreDragging = true
  restoreMoved = false
  restoreLongPressFired = false
  restoreStartX = e.clientX
  restoreStartY = e.clientY
  restoreOriginX = restorePos.value.x
  restoreOriginY = restorePos.value.y
  e.target.setPointerCapture?.(e.pointerId)
  e.preventDefault()
  // Long press decision: 600ms without movement then confetti celebration and open the command panel (consistent with the shown pet)
  clearTimeout(petMenuLongPressTimer)
  petMenuLongPressTimer = window.setTimeout(() => {
    if (restoreDragging && !restoreMoved) {
      restoreLongPressFired = true
      const r = restoreStageRect()
      onPetDoubleClick(r.left + r.width / 2, r.top + r.height / 2)
    }
  }, 600)
}

// Restore button (🐾) right-click in the hidden state: intercepts the browser default menu and does nothing

function onRestorePointerMove(e) {
  if (!restoreDragging) return
  const dx = e.clientX - restoreStartX
  const dy = e.clientY - restoreStartY
  if (!restoreMoved && Math.hypot(dx, dy) > 5) {
    restoreMoved = true
    clearTimeout(petMenuLongPressTimer)
  }
  if (restoreMoved) {
    restorePos.value = clampRestorePos(restoreOriginX + dx, restoreOriginY + dy)
  }
}

function onRestorePointerUp(e) {
  if (!restoreDragging) return
  restoreDragging = false
  clearTimeout(petMenuLongPressTimer)
  e.target.releasePointerCapture?.(e.pointerId)
  if (restoreMoved) {
    restoreUserMoved = true
    saveRestorePos()
    return
  }
  // Long press already triggered: confetti + command panel already executed, no longer triggers single/double clicks
  if (restoreLongPressFired) {
    restoreLongPressFired = false
    return
  }
  // Single / double click decision (consistent with the shown pet: double click → confetti celebration and open the command panel)
  if (restoreClickTimer) {
    clearTimeout(restoreClickTimer)
    restoreClickTimer = 0
    onPetDoubleClick(e.clientX, e.clientY)
    return
  }
  restoreClickTimer = window.setTimeout(() => {
    restoreClickTimer = 0
    showPet()
  }, 300)
}

// ==================== GatewayAction ====================
// Sync the state of all connected agents
function petSyncStatus() {
  emit('petSyncStatus')
  petAction.value = 'cheer'
  setTimeout(() => { if (petAction.value === 'cheer') petAction.value = '' }, 1200)
  petSfxChirp()
}

// Interrupt the current agent (manual intervention)
function petInterrupt() {
  if (!props.currentAgentId) {
    petSpeech.value = 'No agent selected'
    clearTimeout(petSpeechTimer)
    petSpeechTimer = window.setTimeout(() => { petSpeech.value = '' }, 2000)
    return
  }
  emit('petInterruptCurrent')
  petAction.value = 'chomp'
  setTimeout(() => { if (petAction.value === 'chomp') petAction.value = '' }, 1000)
  petSfxChomp()
}

// Rush to the agent waiting for input
function petGotoWaiting() {
  if (petWaitingAgents.value.length === 0) return
  emit('petGotoWaiting')
  petSfxChirp()
}

// SwitchSidebarShow/Hide
function petToggleSidebar() {
  emit('petToggleSidebar')
}

// Open the large network topology view
function petOpenTopology() {
  emit('petOpenTopology')
  petSfxChirp()
}


function spawnPetFx(x, y) {
  const icons = ['❤', '✨', '★', '💫', '✦']
  for (let i = 0; i < 4; i++) {
    const el = document.createElement('div')
    el.className = 'pet-fx'
    el.textContent = icons[Math.floor(Math.random() * icons.length)]
    el.style.left = (x + (Math.random() * 36 - 18)) + 'px'
    el.style.top = (y + (Math.random() * 14 - 7)) + 'px'
    el.style.color = Math.random() > 0.5 ? '#7ee7ff' : '#ff8ad8'
    el.style.setProperty('--rot', (Math.random() * 60 - 30) + 'deg')
    el.style.animationDelay = (i * 0.06) + 's'
    document.body.appendChild(el)
    setTimeout(() => el.remove(), 1400)
  }
}

// ==================== Fantasy spell effects ====================
// kind: array=foot magic circle | throw=toss overhead magic ring | beam=ranged spirit light | swarm=ten-thousand swords returning home
const PET_SPELLS = [
  { key: 'thunder', kind: 'array', glyphs: ['⚡', 'Thunder', '✦'], color: '#9fd8ff', glow: '#5db2ff' },
  { key: 'flame',   kind: 'array', glyphs: ['🔥', 'Flame', '✷'], color: '#ffb066', glow: '#ff7a2f' },
  { key: 'frost',   kind: 'array', glyphs: ['❄', 'Ice', '✳'], color: '#bff2ff', glow: '#6fe3ff' },
  { key: 'star',    kind: 'array', glyphs: ['✨', 'Star', '✴'], color: '#ffe6a8', glow: '#ffd166' },
  { key: 'rune',    kind: 'throw' },                          // Toss overhead digit light ring
  { key: 'bolt',    kind: 'beam', color: '#9fd8ff', glow: '#5db2ff' },  // Ranged: thunder light arrow
  { key: 'sword',   kind: 'beam', color: '#c8e6ff', glow: '#7aa8ff' },  // Ranged: sword control
  { key: 'swarm',   kind: 'swarm', color: '#cfe8ff', glow: '#6f9dff' }, // Ten-thousand swords returning home: the robot scatters in curves then returns to the nest
]

// Screen rectangle of the pet body (including the overhead magic ring), falling back to the pet position
function petStageRect() {
  const el = document.querySelector('.pet-float')
  return el
    ? el.getBoundingClientRect()
    : { left: petPos.value.x, top: petPos.value.y, width: petW(), height: petH() }
}

// Screen rectangle of the 🐾 restore button after hiding, falling back to the restore button position
function restoreStageRect() {
  const el = document.querySelector('.pet-restore')
  return el
    ? el.getBoundingClientRect()
    : { left: restorePos.value.x, top: restorePos.value.y, width: 32, height: 32 }
}

// Toss overhead magic ring: reuses the existing throw action and pet-rune-throw animation
function petCastRuneThrow() {
  petAction.value = 'throw'
  petSfxAction('throw')
  setTimeout(() => { if (petAction.value === 'throw') petAction.value = '' }, 2600)
}

// Ranged release: from the pet, a spirit light shoots out in the robot's direction and bursts open upon arrival
function petCastBeam(spell) {
  const r = petStageRect()
  const ox = r.left + r.width / 2
  const oy = r.top + r.height * 0.4
  // The robot aims at any point in the screen (including the four corners), ensuring it can hit the fullscreen range
  const tx = Math.random() * window.innerWidth
  const ty = Math.random() * window.innerHeight
  const dx = tx - ox
  const dy = ty - oy
  const dist = Math.hypot(dx, dy) || 1
  const angle = Math.atan2(dy, dx) * 180 / Math.PI
  // Duration grows with distance (the farther it flies, the longer it takes), and is slow enough to see the trajectory
  const dur = Math.max(0.75, Math.min(1.8, dist / 900))

  // Light beam
  const beam = document.createElement('div')
  beam.className = 'pet-spell-beam'
  beam.style.left = ox + 'px'
  beam.style.top = oy + 'px'
  beam.style.width = dist + 'px'
  beam.style.transform = `rotate(${angle}deg)`
  beam.style.setProperty('--spell-color', spell.color)
  beam.style.setProperty('--spell-glow', spell.glow)
  beam.style.setProperty('--beam-dur', dur + 's')
  document.body.appendChild(beam)
  setTimeout(() => beam.remove(), (dur + 0.5) * 1000)

  // Flying rune
  const bolt = document.createElement('div')
  bolt.className = 'pet-spell-bolt'
  bolt.textContent = '✦'
  bolt.style.left = ox + 'px'
  bolt.style.top = oy + 'px'
  bolt.style.color = spell.color
  bolt.style.textShadow = `0 0 10px ${spell.glow}, 0 0 20px ${spell.glow}`
  bolt.style.setProperty('--bx', dx + 'px')
  bolt.style.setProperty('--by', dy + 'px')
  bolt.style.setProperty('--beam-dur', dur + 's')
  document.body.appendChild(bolt)
  setTimeout(() => bolt.remove(), (dur + 0.5) * 1000)

  // Impact center burst point
  const hit = document.createElement('div')
  hit.className = 'pet-spell-hit'
  hit.style.left = tx + 'px'
  hit.style.top = ty + 'px'
  hit.style.borderColor = spell.glow
  hit.style.boxShadow = `0 0 26px ${spell.glow}, inset 0 0 26px ${spell.glow}`
  hit.style.animationDelay = dur + 's'
  document.body.appendChild(hit)
  setTimeout(() => hit.remove(), (dur + 0.9) * 1000)
}
// Myriad Swords Return: a group of flying swords stab outward along random curves, arcing back to all gather into the pet body
function petCastSwarm(spell) {
  const r = petStageRect()
  const ox = r.left + r.width / 2
  const oy = r.top + r.height * 0.42
  // Swords must first "charge up" before leaving the sheath: the pet body shakes once
  petAction.value = 'throw'
  setTimeout(() => { if (petAction.value === 'throw') petAction.value = '' }, 900)

  const N = 9
  const maxR = Math.min(window.innerWidth, window.innerHeight) * 0.62
  for (let i = 0; i < N; i++) {
    const sword = document.createElement('div')
    sword.className = 'pet-spell-sword'
    sword.innerHTML = '<i class="pet-sword-blade"></i><i class="pet-sword-hilt"></i>'
    sword.style.left = ox + 'px'
    sword.style.top = oy + 'px'
    sword.style.color = spell.color
    sword.style.setProperty('--spell-glow', spell.glow)

    // Target points: scatter at random angles and random distances, making each sword's path different
    const a = (i / N) * Math.PI * 2 + (Math.random() - 0.5) * 0.7
    const reach = maxR * (0.75 + Math.random() * 0.4)
    const dx = Math.cos(a) * reach
    const dy = Math.sin(a) * reach - maxR * 0.18   // slightly toward the top, like soaring upward
    // Control point: offset vertically along the main axis, forming a crescent-like curved journey (coefficient made larger to fly farther)
    const c1x = dx * 0.8 + -dy * (0.35 + Math.random() * 0.4)
    const c1y = dy * 0.8 + dx * (0.35 + Math.random() * 0.4)
    // Control point 2: return bend on the way back
    const c2x = dx * 0.9 - dy * 0.75
    const c2y = dy * 0.9 + dx * 0.75

    // offset-path's path() cannot resolve var() in CSS, so the full path string is assembled on the JS side
    sword.style.setProperty('--sw-path',
      `path('M 0 0 C ${c1x.toFixed(0)} ${c1y.toFixed(0)}, ${c2x.toFixed(0)} ${c2y.toFixed(0)}, 0 0')`)
    sword.style.setProperty('--sw-dur', (1.7 + Math.random() * 0.5).toFixed(2) + 's')
    sword.style.animationDelay = (i * 0.06 + Math.random() * 0.05).toFixed(2) + 's'
    document.body.appendChild(sword)
    setTimeout(() => sword.remove(), 3200)
  }

  // Sword formation start: a ring of sword-intent spirit light emerges at the feet
  const sigil = document.createElement('div')
  sigil.className = 'pet-spell-swarm-sigil'
  sigil.style.left = ox + 'px'
  sigil.style.top = (r.top + r.height - 26) + 'px'
  sigil.style.borderColor = spell.glow
  sigil.style.boxShadow = `0 0 18px ${spell.glow}, inset 0 0 18px ${spell.glow}`
  document.body.appendChild(sigil)
  setTimeout(() => sigil.remove(), 3400)

  // Central gathering light at the moment of returning
  const core = document.createElement('div')
  core.className = 'pet-spell-swarm-core'
  core.style.left = ox + 'px'
  core.style.top = oy + 'px'
  core.style.background = `radial-gradient(circle, #ffffff 0%, ${spell.color} 40%, transparent 72%)`
  core.style.boxShadow = `0 0 42px ${spell.glow}`
  core.style.animationDelay = '1.55s'
  document.body.appendChild(core)
  setTimeout(() => core.remove(), 2700)
}

// Cast a wave of magic: expand a rotating spirit-light magic circle at the pet's feet
function petCastSpell(spell) {
  const r = petStageRect()
  const cx = r.left + r.width / 2
  const cy = r.top + r.height - 34   // the magic circle lands at the pet's feet

  const array = document.createElement('div')
  array.className = 'pet-spell-array'
  array.style.left = cx + 'px'
  array.style.top = cy + 'px'
  array.style.setProperty('--spell-color', spell.color)
  array.style.setProperty('--spell-glow', spell.glow)

  //  Outer rotating talisman ring: a ring of spell characters
  const glyphRing = document.createElement('div')
  glyphRing.className = 'pet-array-glyphring'
  const N = 12
  for (let i = 0; i < N; i++) {
    const g = document.createElement('span')
    g.className = 'pet-array-glyph'
    g.textContent = spell.glyphs[i % spell.glyphs.length]
    const angle = (i / N) * 360
    g.style.transform = `rotate(${angle}deg) translateY(-58px)`
    glyphRing.appendChild(g)
  }
  array.appendChild(glyphRing)

  //  Inner counter-rotating engraved-line ring
  const lineRing = document.createElement('div')
  lineRing.className = 'pet-array-linering'
  array.appendChild(lineRing)

  //  Central geometric seal: two overlapping squares (rotated 45°) forming an eight-pointed star
  const seal = document.createElement('div')
  seal.className = 'pet-array-seal'
  seal.innerHTML = '<i></i><i></i>'
  array.appendChild(seal)

  //  Central light core
  const core = document.createElement('div')
  core.className = 'pet-array-core'
  array.appendChild(core)

  document.body.appendChild(array)
  setTimeout(() => array.remove(), 1900)
}

// Cast the specified spell (dispatch effects and sounds by kind)
function castSpell(spell) {
  if (!spell) return
  petCast.value = spell.key
  if (spell.kind === 'throw')      petCastRuneThrow()
  else if (spell.kind === 'beam')  petCastBeam(spell)
  else if (spell.kind === 'swarm') petCastSwarm(spell)
  else                             petCastSpell(spell)
  petSfxCast(spell.kind)
  clearTimeout(petCastClearTimer)
  petCastClearTimer = window.setTimeout(() => { petCast.value = '' }, 2600)
}

// Randomly cast a wave of magic
function castRandomSpell() {
  if (petCast.value) return
  castSpell(PET_SPELLS[Math.floor(Math.random() * PET_SPELLS.length)])
}

// Debug hook: window.__haijunbotPetCast('swarm') manually triggers the specified spell, handy for preview
function installPetCastDebugHook() {
  try {
    window.__haijunbotPetCast = (key) => {
      const spell = PET_SPELLS.find(s => s.key === key)
      if (!spell) return { ok: false, error: 'unknown spell: ' + key, available: PET_SPELLS.map(s => s.key) }
      castSpell(spell)
      return { ok: true, spell: spell.key, kind: spell.kind }
    }
    window.__haijunbotPetSpells = () => PET_SPELLS.map(s => ({ key: s.key, kind: s.kind }))
  } catch (e) {
    // Ignore: debug hook failure does not affect normal features
  }
}

// Cast a wave of magic about every 30s (±5s jitter, to avoid being too mechanical)
let petCastTimer = 0
// After casting, clear the petCast state's timer (kept separate from the scheduling timer to avoid clearing each other)
let petCastClearTimer = 0
function schedulePetCast() {
  clearTimeout(petCastTimer)
  petCastTimer = window.setTimeout(() => {
    if (!petPowerSaveActive.value && !document.hidden && !petHover.value && !petDrag.value && !petSleep.value &&
        !petHidden.value && !petPetting.value && !petWalking.value) {
      castRandomSpell()
    }
    schedulePetCast()
  }, 25000 + Math.random() * 10000)
}

// ==================== Pet sound effects (Web Audio synthesis, no external resources) ====================
const PET_SFX_KEY = 'haijunbot_pet_sfx'
const petSfxOn = ref(true)

let petAudioCtx = null
function getPetAudioCtx() {
  if (typeof window === 'undefined') return null
  // Power-save mode: do not create/reuse the AudioContext, mute all sound effects
  if (petPowerSaveActive.value) return null
  const AC = window.AudioContext || window.webkitAudioContext
  if (!AC) return null
  if (!petAudioCtx) petAudioCtx = new AC()
  if (petAudioCtx.state === 'suspended') petAudioCtx.resume()
  return petAudioCtx
}

function petTone(freq, start, dur, type, vol, slideTo) {
  const ctx = getPetAudioCtx()
  if (!ctx) return
  try {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = type || 'sine'
    const t0 = ctx.currentTime + start
    osc.frequency.setValueAtTime(freq, t0)
    if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, t0 + dur)
    gain.gain.setValueAtTime(0.0001, t0)
    gain.gain.exponentialRampToValueAtTime(vol || 0.08, t0 + 0.012)
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
    osc.start(t0)
    osc.stop(t0 + dur + 0.02)
  } catch (e) {
    // Ignore audio errors, do not affect interaction
  }
}

// Click: crisp "chirp chirp"
function petSfxChirp() {
  if (!petSfxOn.value) return
  petTone(900, 0, 0.09, 'triangle', 0.09, 1500)
  petTone(1500, 0.07, 0.11, 'triangle', 0.07, 2100)
}

// Random small action sound
function petSfxAction(action) {
  if (!petSfxOn.value) return
  switch (action) {
    case 'look':
      petTone(1200, 0, 0.07, 'sine', 0.05, 1400)
      break
    case 'yawn':
      petTone(700, 0, 0.42, 'sine', 0.06, 380)
      break
    case 'spin':
      petTone(700, 0, 0.08, 'triangle', 0.06)
      petTone(1000, 0.08, 0.08, 'triangle', 0.06)
      petTone(1400, 0.16, 0.1, 'triangle', 0.06)
      break
    case 'hop':
      petTone(600, 0, 0.12, 'sine', 0.08, 1300)
      break
    case 'throw':
      petTone(500, 0, 0.09, 'triangle', 0.07, 1600)
      petTone(1600, 0.1, 0.1, 'triangle', 0.06, 900)
      break
  }
}

// Double-click cheer
function petSfxCheer() {
  if (!petSfxOn.value) return
  petTone(880, 0, 0.1, 'triangle', 0.08, 1320)
  petTone(1320, 0.09, 0.1, 'triangle', 0.08, 1760)
  petTone(1760, 0.18, 0.18, 'triangle', 0.07, 2200)
}

// Chewing: short double tone
function petSfxChomp() {
  if (!petSfxOn.value) return
  petTone(320, 0, 0.07, 'square', 0.05, 180)
  petTone(300, 0.14, 0.07, 'square', 0.05, 170)
}

// Purr: low-frequency trill
function petSfxPurr() {
  if (!petSfxOn.value) return
  petTone(180, 0, 0.5, 'sawtooth', 0.035, 210)
  petTone(150, 0.06, 0.45, 'sine', 0.03, 175)
}

// Singing: scale sequence
function petSfxSong() {
  if (!petSfxOn.value) return
  const scale = [523, 587, 659, 784, 880, 1047]
  scale.forEach((f, i) => petTone(f, i * 0.14, 0.16, 'sine', 0.06))
}

// Dozing yawn
function petSfxYawn() {
  if (!petSfxOn.value) return
  petTone(620, 0, 0.45, 'sine', 0.06, 300)
}

// Casting: a mystic rising harmony
function petSfxCast(type) {
  if (!petSfxOn.value) return
  switch (type) {
    case 'thunder':
      petTone(220, 0, 0.5, 'sawtooth', 0.05, 880)
      petTone(660, 0.06, 0.3, 'triangle', 0.05, 1320)
      break
    case 'flame':
      petTone(300, 0, 0.4, 'sawtooth', 0.045, 620)
      petTone(880, 0.08, 0.25, 'sine', 0.05, 1180)
      break
    case 'frost':
      petTone(1600, 0, 0.35, 'sine', 0.05, 900)
      petTone(1200, 0.1, 0.3, 'triangle', 0.045, 1900)
      break
    case 'beam':   // Remote: piercing shot through the void
      petTone(1400, 0, 0.22, 'sawtooth', 0.045, 320)
      petTone(210, 0.02, 0.3, 'triangle', 0.05, 160)
      break
    case 'throw':  // Throw out magic ring
      petTone(700, 0, 0.2, 'triangle', 0.05, 1400)
      petTone(1180, 0.12, 0.35, 'sine', 0.045, 1760)
      break
    case 'swarm':  // Myriad Swords Return: clanging sword cry + howling sword aura
      petTone(2400, 0, 0.18, 'sawtooth', 0.05, 520)
      petTone(1500, 0.04, 0.3, 'triangle', 0.045, 2600)
      petTone(320, 0.5, 0.5, 'sine', 0.05, 180)
      petTone(1900, 1.5, 0.4, 'triangle', 0.045, 900)
      break
    default: // star
      petTone(784, 0, 0.16, 'sine', 0.05, 1046)
      petTone(1046, 0.14, 0.16, 'sine', 0.05, 1318)
      petTone(1318, 0.28, 0.3, 'sine', 0.045, 1568)
      break
  }
}

function togglePetSfx() {
  petSfxOn.value = !petSfxOn.value
  try {
    localStorage.setItem(PET_SFX_KEY, petSfxOn.value ? '1' : '0')
  } catch (e) {
    // IgnoreStorageAbnormal
  }
  if (petSfxOn.value) petSfxChirp()
}

// Toggle mini topology display
function togglePetTopo() {
  petTopoOn.value = !petTopoOn.value
  try {
    localStorage.setItem(PET_TOPO_KEY, petTopoOn.value ? '1' : '0')
  } catch (e) {
    // IgnoreStorageAbnormal
  }
  petSfxChirp()
}

// Random small action
// Random small action (throw is already included in spell effects, see PET_SPELLS)
const PET_ACTIONS = ['look', 'yawn', 'spin', 'hop']
// Random fun behavior: occasionally spontaneously feeds/plays ball/sings/dozes (no longer triggered by the menu)
const PET_FUN_ACTIONS = [petFeed, petPlayBall, petSing, togglePetSleep]
let petActTimer = 0
function schedulePetAction() {
  clearTimeout(petActTimer)
  petActTimer = window.setTimeout(() => {
    if (!petPowerSaveActive.value && !document.hidden && !petHover.value && !petDrag.value && !petSleep.value && !petHidden.value && !petPetting.value && !petWalking.value) {
      // About a quarter chance to trigger fun behavior, otherwise normal small action
      if (Math.random() < 0.25) {
        const fun = PET_FUN_ACTIONS[Math.floor(Math.random() * PET_FUN_ACTIONS.length)]
        fun()
      } else {
        const act = PET_ACTIONS[Math.floor(Math.random() * PET_ACTIONS.length)]
        petAction.value = act
        petSfxAction(act)
        const actDur = act === 'throw' ? 2600 : 1700
        setTimeout(() => { petAction.value = '' }, actDur)
      }
    }
    schedulePetAction()
  }, 5000 + Math.random() * 7000)
}

function onPetResize() {
  if (petEdge.value) {
    // Edge state: recompute edge position according to the new viewport width
    applyPetEdge()
    return
  }
  petPos.value = clampPetPos(petPos.value.x, petPos.value.y)
}

// ==================== Random wander ====================
let petWanderTimer = 0   // next wake-up time
let petWanderRaf = 0     // wander animation frame
// Whether free wandering is currently allowed: not fixed/dragging/hovering/sleeping/hidden/being petted, and page visible
function canPetWander() {
  return !petPinned.value && !petPowerSaveActive.value && !document.hidden && !petHover.value && !petDrag.value &&
    !petSleep.value && !petHidden.value && !petPetting.value && !petWalking.value && !petEdge.value
}

function schedulePetWander() {
  clearTimeout(petWanderTimer)
  petWanderTimer = window.setTimeout(() => {
    if (canPetWander()) startPetWalk()
    schedulePetWander()
  }, 9000 + Math.random() * 14000)
}

// Randomly choose a nearby destination: usually paces within a small range, occasionally walks a bit farther
function pickPetDestination() {
  const maxX = Math.max(0, window.innerWidth - petW())
  const maxY = Math.max(0, window.innerHeight - petH())
  const far = Math.random() < 0.15
  const rangeX = far ? window.innerWidth * 0.4 : 170
  const rangeY = far ? window.innerHeight * 0.35 : 90
  const nx = petPos.value.x + (Math.random() * 2 - 1) * rangeX
  const ny = petPos.value.y + (Math.random() * 2 - 1) * rangeY
  return {
    x: Math.max(0, Math.min(maxX, nx)),
    y: Math.max(0, Math.min(maxY, ny)),
  }
}

function startPetWalk() {
  const from = { x: petPos.value.x, y: petPos.value.y }
  const to = pickPetDestination()
  const dist = Math.hypot(to.x - from.x, to.y - from.y)
  // If the movement is too small, do not move, to avoid jittering in place
  if (dist < 40) return
  // Facing: flip according to horizontal direction
  petFaceDir.value = to.x < from.x ? -1 : 1
  petWalking.value = true
  // Move quietly without making sound, to avoid disturbing
  // After moving the pet is smaller, movement speed halved (duration doubled)
  const speedFactor = isMobileView.value ? 22 : 11
  const dur = Math.max(1600, Math.min(6000, dist * speedFactor))
  const t0 = performance.now()
  const easeInOut = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2)
  const step = (now) => {
    const t = Math.min(1, (now - t0) / dur)
    const e = easeInOut(t)
    petPos.value = clampPetPos(
      from.x + (to.x - from.x) * e,
      from.y + (to.y - from.y) * e
    )
    if (t < 1) {
      petWanderRaf = requestAnimationFrame(step)
    } else {
      petWanderRaf = 0
      petWalking.value = false
      savePetPos()
    }
  }
  cancelAnimationFrame(petWanderRaf)
  petWanderRaf = requestAnimationFrame(step)
}

//  Interrupt wandering (when dragging/interacting)
function stopPetWalk() {
  if (petWanderRaf) {
    cancelAnimationFrame(petWanderRaf)
    petWanderRaf = 0
  }
  petWalking.value = false
}

// When the pet is hidden, stop all persistent operations (small action/wander scheduling, animation frames, mouse-tracking listeners) to save resources
function stopPetLoops() {
  clearTimeout(petActTimer)
  petActTimer = 0
  clearTimeout(petWanderTimer)
  petWanderTimer = 0
  clearTimeout(petSleepTimer)
  petSleepTimer = 0
  clearTimeout(petCastTimer)
  petCastTimer = 0
  clearTimeout(petCastClearTimer)
  petCastClearTimer = 0
  petCast.value = ''
  stopPetWalk()
  clearTimeout(petEncourageTimer)
  petEncourageTimer = 0
  if (petRaf) {
    cancelAnimationFrame(petRaf)
    petRaf = 0
  }
  document.removeEventListener('mousemove', onPetMouseMove)
}

// Restart persistent operations when the pet is shown again (idempotent: will not start again if already running)
function startPetLoops() {
  if (petPowerSaveActive.value) return  // power-save mode: do not start any persistent effects or operations
  if (!petActTimer) schedulePetAction()
  if (!petWanderTimer) schedulePetWander()
  if (!petCastTimer) schedulePetCast()
  if (!petEncourageTimer) schedulePetEncourage()
  document.addEventListener('mousemove', onPetMouseMove)
}

// Toggle power-save mode: when on, stop all persistent operations and effects; when off, restore
function togglePetPowerSave() {
  petPowerSave.value = !petPowerSave.value
  try {
    localStorage.setItem(PET_POWER_SAVE_KEY, petPowerSave.value ? '1' : '0')
  } catch (e) {
    // IgnoreStorageAbnormal
  }
  if (petPowerSaveActive.value) {
    stopPetLoops()
    petAction.value = ''
    petSpeech.value = ''
    petCast.value = ''
    clearTimeout(petSpeechTimer)
    petSpeechTimer = 0
  } else {
    startPetLoops()
  }
}

// Toggle fixed state: when fixed, immediately stop the current wander and forbid further random movement
function togglePetPin() {
  petPinned.value = !petPinned.value
  try {
    localStorage.setItem(PET_PIN_KEY, petPinned.value ? '1' : '0')
  } catch (e) {
    // IgnoreStorageAbnormal
  }
  if (petPinned.value) stopPetWalk()
  petSfxChirp()
}

onMounted(() => {
  initPetPos()
  initRestorePos()
  initPetEdge()
  try {
    petSfxOn.value = localStorage.getItem(PET_SFX_KEY) !== '0'
  } catch (e) {
    petSfxOn.value = true
  }
  try {
    petTopoOn.value = localStorage.getItem(PET_TOPO_KEY) !== '0'
  } catch (e) {
    petTopoOn.value = true
  }
  try {
    petHidden.value = localStorage.getItem(PET_HIDDEN_KEY) === '1'
  } catch (e) {
    petHidden.value = false
  }
  try {
    petPowerSave.value = localStorage.getItem(PET_POWER_SAVE_KEY) === '1'
  } catch (e) {
    petPowerSave.value = false
  }
  try {
    petPinned.value = localStorage.getItem(PET_PIN_KEY) === '1'
  } catch (e) {
    petPinned.value = false
  }
  document.addEventListener('mousemove', onPetMouseMove)
  window.addEventListener('resize', onPetResize)
  installPetCastDebugHook()
  startPetLoops()
})

// When not connected (login UI), the pet is invisible; synchronously stop/restore its persistent operations
watch(() => props.isConnected, (connected) => {
  if (connected) {
    startPetLoops()
  } else {
    stopPetLoops()
  }
})

// When power-save mode takes effect or state changes (including move-end/desktop switch), synchronously start/stop persistent operations
watch(petPowerSaveActive, (active) => {
  if (active) {
    stopPetLoops()
  } else if (props.isConnected) {
    startPetLoops()
  }
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onPetMouseMove)
  window.removeEventListener('resize', onPetResize)
  clearTimeout(petLongPressTimer)
  clearTimeout(petMenuLongPressTimer)
  clearTimeout(petActTimer)
  clearTimeout(petClickTimer)
  clearTimeout(restoreClickTimer)
  clearTimeout(petSpeechTimer)
  clearTimeout(petHideTimer)
  clearInterval(petPettingFxTimer)
  clearTimeout(petWanderTimer)
  clearTimeout(petSleepTimer)
  clearTimeout(petCastTimer)
  clearTimeout(petCastClearTimer)
  clearTimeout(petEncourageTimer)
  clearTimeout(petEdgeLeaveTimer)
  if (petRaf) cancelAnimationFrame(petRaf)
  if (petWanderRaf) cancelAnimationFrame(petWanderRaf)
  try {
    delete window.__haijunbotPetCast
    delete window.__haijunbotPetSpells
  } catch (e) {
    // Ignore
  }
})

defineExpose({
  togglePet,
  hidePet: petHide,
  showPet,
})
</script>

<style scoped>
/* Pet widget: floats on the page, can be dragged and remembers its position */
.pet-float {
  position: fixed;
  z-index: 900;
  width: 200px;
  height: 230px;
  pointer-events: none;
  touch-action: none;
  /* Edge slide-in/slide-out animation (displacement uses left, to avoid conflicting with the transform of the move-end scale) */
  transition: left 0.22s ease;
}

/* Edge state: a summon trigger item fixed at the inner edge of the screen; when the mouse moves in, temporarily slides the pet out.
   Positioned independently with position:fixed in .pet-float, to avoid moving with the pet's slide-in/slide-out animation */
.pet-edge-trigger {
  position: fixed;
  width: 18px;
  pointer-events: auto;
  cursor: pointer;
  touch-action: none;
  /* Referencing the global tool item edge narrow strip: z-index needs to be higher than .pet-float(900),
     otherwise the sliver exposed when the edge collapses will be covered by the pet hotspot .pet-hit, and click/touch will not receive events.
     The collapse-state trigger item is above the pet, and clicking it summons out; the slide-out-state trigger item is hidden with v-show and does not affect pet action */
  z-index: 10000;
}
.pet-edge-trigger.is-left {
  left: 0;
}
.pet-edge-trigger.is-right {
  right: 0;
}

/* Move-end: the pet scales down to half overall. Using the top-left corner as the zoom origin, keeping petPos at the visual top-left corner,
   and staying consistent with the JS-side petW()/petH() (dimensions after zooming back) */
.pet-float.pet-compact {
  transform: scale(0.5);
  transform-origin: top left;
  /* Jump/duck height halved */
  --pet-hop: 0.5;
}

.pet-inner {
  position: relative;
  width: 100%;
  height: 100%;
}

.pet-glow {
  position: absolute;
  left: 50%;
  bottom: 26px;
  width: 236px;
  height: 52px;
  transform: translateX(-50%);
  border-radius: 50%;
  pointer-events: none;
  opacity: 0.25;
  background: radial-gradient(50% 50% at 50% 50%, rgba(32, 200, 255, 0.35) 0%, transparent 70%);
  animation: pet-glow 2.6s ease-in-out infinite;
}

/* ==================== Overhead digital light ring (a 0/1 rune ring shaped like a celestial light ring) ==================== */
.pet-rune-ring {
  position: absolute;
  left: 50%;
  top: 40px;
  width: 0;
  height: 0;
  /* Celestial light ring: flattened overall into an ellipse and slightly tilted (front low, back high), hovering above the head; mirrors with the pet's facing */
  transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1));
  pointer-events: none;
  z-index: 1;
}

/* The light ring slowly rotates as a whole, creating the sense of a spirit formation in motion (period uniformly controlled by --rune-spin-dur) */
.pet-rune-orbit {
  position: absolute;
  left: 0;
  top: 0;
  width: 0;
  height: 0;
  animation: pet-rune-spin var(--rune-spin-dur, 26s) linear infinite;
}

/* Each rune: the outer layer only handles positioning (first turn to the azimuth, then push outward along the radius), no animation */
.pet-rune-bit {
  position: absolute;
  left: 0;
  top: 0;
  width: 14px;
  height: 14px;
  margin: -7px 0 0 -7px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/*  Inner character: cancels the light ring's rotation and flattening, keeping the character always upright and not flattened; at the same time it does a breathing flicker */
.pet-rune-glyph {
  font-family: 'Courier New', Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  color: #b8f4ff;
  text-shadow: 0 0 6px rgba(126, 231, 255, 0.95), 0 0 14px rgba(32, 200, 255, 0.7);
  opacity: 0.85;
  /* Counter-rotation cancels the orbit's rotation, keeping the character always upright; flattening is handled uniformly by the container */
  animation-name: pet-rune-counter, pet-rune-glow;
  animation-duration: var(--rune-spin-dur, 26s), var(--rune-glow-dur, 2.4s);
  animation-timing-function: linear, ease-in-out;
  animation-delay: 0s, var(--rune-glow-delay, 0s);
  animation-iteration-count: infinite, infinite;
}

/* Light ring inner circle: pale cyan spirit light, setting off the pet's head (likewise flattened into an ellipse) */
.pet-rune-core {
  position: absolute;
  left: 0;
  top: 0;
  width: 124px;
  height: 124px;
  margin: -62px 0 0 -62px;
  border-radius: 50%;
  border: 1px solid rgba(126, 231, 255, 0.22);
  box-shadow: inset 0 0 24px rgba(32, 200, 255, 0.18), 0 0 18px rgba(32, 200, 255, 0.12);
  opacity: 0.7;
  animation: pet-rune-breathe 3.4s ease-in-out infinite;
}

@keyframes pet-rune-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Same period as pet-rune-spin but reversed, canceling the parent's rotation to keep the character upright; scaleY compensates for the container's flattening */
@keyframes pet-rune-counter {
  from { transform: rotate(0deg) scaleY(2.381); }
  to { transform: rotate(-360deg) scaleY(2.381); }
}

@keyframes pet-rune-glow {
  0%, 100% { opacity: 0.35; filter: brightness(0.9); }
  50% { opacity: 1; filter: brightness(1.5); }
}

@keyframes pet-rune-breathe {
  0%, 100% { opacity: 0.45; transform: scale(0.96); }
  50% { opacity: 0.85; transform: scale(1.04); }
}

/* ==================== Orbiting spirit beads/runes around the pet (same fantasy design language as the overhead light ring) ==================== */
/* Two elliptical orbits at different inclinations, counter-rotating, each carrying spirit beads/runes orbiting the body */
.pet-orbit {
  position: absolute;
  left: 50%;
  top: 46%;
  width: 0;
  height: 0;
  pointer-events: none;
  opacity: 0.75;
  transition: opacity 0.6s ease;
}

/* Orbit A: gentler, cyan spirit beads */
.pet-orbit.orbit-a {
  --orbit-tilt: 18deg;
  --orbit-squash: 0.34;
  --orbit-dur: 14s;
  transform: translateX(-50%) rotateZ(var(--orbit-tilt)) scaleY(var(--orbit-squash));
}

/* Orbit B: steeper, counter-rotating star-light runes */
.pet-orbit.orbit-b {
  --orbit-tilt: -32deg;
  --orbit-squash: 0.5;
  --orbit-dur: 20s;
  transform: translateX(-50%) rotateZ(var(--orbit-tilt)) scaleY(var(--orbit-squash));
}

.pet-orbit-track {
  position: absolute;
  left: 0;
  top: 0;
  width: 0;
  height: 0;
  animation: pet-orbit-spin var(--orbit-dur, 16s) linear infinite;
}

/* The counter-rotating orbit as a whole turns in the opposite direction */
.pet-orbit.orbit-b .pet-orbit-track {
  animation-direction: reverse;
}

/* Spirit beads: evenly distributed along the orbit, compensating for the flattening so the dots stay circular */
.pet-orbit-mote {
  position: absolute;
  left: 0;
  top: 0;
  width: 6px;
  height: 6px;
  margin: -3px 0 0 -3px;
  border-radius: 50%;
  background: radial-gradient(circle, #ffffff 0%, #9fe9ff 45%, transparent 75%);
  box-shadow: 0 0 8px rgba(126, 231, 255, 0.95);
  transform: translateY(-96px) scaleY(calc(1 / var(--orbit-squash, 1)));
}

.pet-orbit-mote:nth-child(1) { transform: rotate(0deg) translateY(-96px) scaleY(calc(1 / var(--orbit-squash, 1))); }
.pet-orbit-mote:nth-child(2) { transform: rotate(120deg) translateY(-96px) scaleY(calc(1 / var(--orbit-squash, 1))); }
.pet-orbit-mote:nth-child(3) { transform: rotate(240deg) translateY(-96px) scaleY(calc(1 / var(--orbit-squash, 1))); }

/* Runes: distributed along the orbit, self counter-rotating to stay upright */
.pet-orbit-rune {
  position: absolute;
  left: 0;
  top: 0;
  width: 14px;
  height: 14px;
  margin: -7px 0 0 -7px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  line-height: 1;
  color: #d8f6ff;
  text-shadow: 0 0 6px rgba(126, 231, 255, 0.95), 0 0 12px rgba(32, 200, 255, 0.7);
  transform: translateY(-104px) scaleY(calc(1 / var(--orbit-squash, 1)));
  animation: pet-orbit-rune-glow 2.6s ease-in-out infinite;
}

.pet-orbit-rune:nth-child(1) { transform: rotate(0deg) translateY(-104px) scaleY(calc(1 / var(--orbit-squash, 1))); }
.pet-orbit-rune:nth-child(2) { transform: rotate(120deg) translateY(-104px) scaleY(calc(1 / var(--orbit-squash, 1))); }
.pet-orbit-rune:nth-child(3) { transform: rotate(240deg) translateY(-104px) scaleY(calc(1 / var(--orbit-squash, 1))); }

@keyframes pet-orbit-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pet-orbit-rune-glow {
  0%, 100% { opacity: 0.4; filter: brightness(0.9); }
  50% { opacity: 1; filter: brightness(1.5); }
}

/* Running: the orbit turns fast, spirit light flourishes */
.pet-float.rune-running .pet-orbit {
  opacity: 1;
}
.pet-float.rune-running .pet-orbit.orbit-a { --orbit-dur: 8s; }
.pet-float.rune-running .pet-orbit.orbit-b { --orbit-dur: 11s; }

/* Dozing: the orbit nearly stalls, dim */
.pet-float.rune-sleep .pet-orbit {
  opacity: 0.22;
}
.pet-float.rune-sleep .pet-orbit.orbit-a { --orbit-dur: 120s; }
.pet-float.rune-sleep .pet-orbit.orbit-b { --orbit-dur: 150s; }

/* Moment of casting: the orbit suddenly speeds up */
.pet-float.is-casting .pet-orbit {
  opacity: 1;
}
.pet-float.is-casting .pet-orbit.orbit-a { --orbit-dur: 3s; }
.pet-float.is-casting .pet-orbit.orbit-b { --orbit-dur: 4.5s; }

/* —— State linkage (rotation speed uniformly controlled by --rune-spin-dur, orbit and character counter-rotation synchronized) —— */
/* Running: runes turn fast, cyan glow blazing */
.pet-float.rune-running {
  --rune-spin-dur: 9s;
}
.pet-float.rune-running .pet-rune-glyph {
  color: #d8fbff;
  text-shadow: 0 0 8px rgba(126, 231, 255, 1), 0 0 20px rgba(32, 200, 255, 0.95);
}
.pet-float.rune-running .pet-rune-core {
  border-color: rgba(126, 231, 255, 0.5);
  box-shadow: inset 0 0 30px rgba(32, 200, 255, 0.35), 0 0 26px rgba(32, 200, 255, 0.35);
}

/* Waiting for input: turns into a golden pulse, a sense of warning */
.pet-float.rune-waiting {
  --rune-spin-dur: 14s;
}
.pet-float.rune-waiting .pet-rune-glyph {
  color: #ffe6a8;
  text-shadow: 0 0 8px rgba(255, 209, 102, 1), 0 0 18px rgba(255, 152, 0, 0.85);
}
.pet-float.rune-waiting .pet-rune-core {
  border-color: rgba(255, 209, 102, 0.6);
  box-shadow: inset 0 0 30px rgba(255, 152, 0, 0.35), 0 0 28px rgba(255, 152, 0, 0.45);
  animation-duration: 1.4s;
}

/* Dozing: spirit light dim, nearly stalled */
.pet-float.rune-sleep {
  --rune-spin-dur: 90s;
}
.pet-float.rune-sleep .pet-rune-ring {
  opacity: 0.28;
  transition: opacity 0.6s ease;
}
.pet-float.rune-sleep .pet-rune-glyph {
  color: #7fa6b8;
  text-shadow: 0 0 6px rgba(126, 231, 255, 0.4);
}

.pet-hit {
  position: absolute;
  left: 50%;
  bottom: 44px;
  width: 150px;
  height: 130px;
  transform: translateX(-50%);
  cursor: grab;
  pointer-events: auto;
  z-index: 3;
}

.pet-float.is-drag .pet-hit {
  cursor: grabbing;
}

.pet-body {
  position: absolute;
  left: 50%;
  bottom: 52px;
  width: 126px;
  height: 110px;
  transform: translateX(-50%);
  pointer-events: none;
  animation: pet-bob 2.6s ease-in-out infinite;
}

.pet-head {
  position: absolute;
  left: 50%;
  top: 0;
  width: 95px;
  height: 83px;
  transform: translateX(-50%);
  background: linear-gradient(160deg, #2ee6ff 0%, #1a9fd6 55%, #0e6f9e 100%);
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 0 18px rgba(32, 200, 255, 0.45), inset 0 -6px 12px rgba(0, 0, 0, 0.25),
    inset 0 4px 8px rgba(255, 255, 255, 0.18);
  transition: transform 0.25s ease;
}

.pet-ear {
  position: absolute;
  top: -18px;
  width: 0;
  height: 0;
  border-left: 18px solid transparent;
  border-right: 18px solid transparent;
  border-bottom: 27px solid #23b9e8;
  filter: drop-shadow(0 0 6px rgba(32, 200, 255, 0.5));
  transition: transform 0.25s ease;
}

.pet-ear.l {
  left: 4px;
  transform: rotate(-18deg);
}

.pet-ear.r {
  right: 4px;
  transform: rotate(18deg);
}

.pet-eye {
  position: absolute;
  top: 31px;
  width: 16px;
  height: 19px;
  border-radius: 50%;
  background: #06131f;
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.75);
  animation: pet-blink 4.2s infinite;
}

.pet-eye.l {
  left: 22px;
}

.pet-eye.r {
  right: 22px;
}

.pet-pupil {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(234, 252, 255, 0.9);
  transform: translate(-50%, -50%);
  transition: transform 0.12s ease-out;
}

.pet-mouth {
  position: absolute;
  left: 50%;
  top: 60px;
  width: 23px;
  height: 12px;
  transform: translateX(-50%);
  border-bottom: 2px solid rgba(6, 19, 31, 0.75);
  border-radius: 0 0 8px 8px;
  transition: all 0.2s ease;
}

.pet-tail {
  position: absolute;
  right: -19px;
  bottom: 16px;
  width: 43px;
  height: 43px;
  border: 3px solid #23b9e8;
  border-color: #23b9e8 transparent transparent transparent;
  border-radius: 50%;
  transform-origin: 0% 100%;
  animation: pet-tail 1.6s ease-in-out infinite;
  filter: drop-shadow(0 0 6px rgba(32, 200, 255, 0.45));
}

.pet-shadow {
  position: absolute;
  left: 50%;
  bottom: 39px;
  width: 102px;
  height: 18px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.35);
  filter: blur(2px);
  pointer-events: none;
  animation: pet-shadow 2.6s ease-in-out infinite;
}

.pet-spark {
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #7ee7ff;
  box-shadow: 0 0 6px #7ee7ff;
  opacity: 0;
  pointer-events: none;
  animation: pet-spark 3.2s ease-in-out infinite;
}

.pet-spark.s1 {
  left: 22%;
  bottom: 102px;
  animation-delay: 0.2s;
}

.pet-spark.s2 {
  left: 74%;
  bottom: 137px;
  animation-delay: 1.1s;
}

.pet-spark.s3 {
  left: 50%;
  bottom: 166px;
  animation-delay: 2s;
}

.pet-label {
  position: absolute;
  left: 50%;
  bottom: 6px;
  transform: translateX(-50%);
  font-size: 13px;
  letter-spacing: 2px;
  color: rgba(126, 231, 255, 0.55);
  white-space: nowrap;
  pointer-events: none;
}

.pet-sfx-btn {
  position: absolute;
  right: 8px;
  bottom: 4px;
  width: 24px;
  height: 24px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  line-height: 1;
  border: none;
  border-radius: 50%;
  background: rgba(32, 200, 255, 0.12);
  cursor: pointer;
  pointer-events: auto;
  z-index: 5;
  opacity: 0.5;
  transition: opacity 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.pet-sfx-btn:hover {
  opacity: 1;
  background: rgba(32, 200, 255, 0.25);
  transform: scale(1.12);
}

.pet-sfx-btn.is-off {
  opacity: 0.35;
  filter: grayscale(1);
}

/* Fixed pet toggle (placed directly above the power-save button) */
.pet-pin-btn {
  position: absolute;
  right: 8px;
  bottom: 60px;
  width: 24px;
  height: 24px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  line-height: 1;
  border: none;
  border-radius: 50%;
  background: rgba(32, 200, 255, 0.12);
  cursor: pointer;
  pointer-events: auto;
  z-index: 5;
  opacity: 0.5;
  transition: opacity 0.2s ease, background 0.2s ease, transform 0.2s ease;
}
.pet-pin-btn:hover {
  opacity: 1;
  background: rgba(32, 200, 255, 0.25);
  transform: scale(1.12);
}
.pet-pin-btn.is-on {
  opacity: 1;
  background: rgba(255, 209, 102, 0.22);
}

/* Power-save mode toggle (shown on both move-end/desktop, placed directly above the sound button) */
.pet-power-btn {
  position: absolute;
  right: 8px;
  bottom: 32px;
  width: 24px;
  height: 24px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  line-height: 1;
  border: none;
  border-radius: 50%;
  background: rgba(32, 200, 255, 0.12);
  cursor: pointer;
  pointer-events: auto;
  z-index: 5;
  opacity: 0.5;
  transition: opacity 0.2s ease, background 0.2s ease, transform 0.2s ease;
}
.pet-power-btn:hover {
  opacity: 1;
  background: rgba(32, 200, 255, 0.25);
  transform: scale(1.12);
}
.pet-power-btn.is-on {
  opacity: 1;
  background: rgba(120, 255, 170, 0.22);
}

/* ==================== Power-save mode: turn off all decorative animations and effects ==================== */
.pet-float.power-save .pet-spark,
.pet-float.power-save .pet-orbit,
.pet-float.power-save .pet-zzz,
.pet-float.power-save .pet-rune,
.pet-float.power-save .pet-rune-ring,
.pet-float.power-save .pet-rune-glyph,
.pet-float.power-save .pet-rune-core,
.pet-float.power-save .pet-tail,
.pet-float.power-save .pet-eye,
.pet-float.power-save .pet-bubble,
.pet-float.power-save .pet-shadow {
  animation: none !important;
  transition: none !important;
}
/* Hide purely decorative elements to further reduce rendering overhead */
.pet-float.power-save .pet-spark,
.pet-float.power-save .pet-orbit,
.pet-float.power-save .pet-zzz,
.pet-float.power-save .pet-rune-ring,
.pet-float.power-save .pet-rune-glyph,
.pet-float.power-save .pet-rune-core {
  display: none !important;
}
/* The pet body's transitions and filters are also turned off */
.pet-float.power-save,
.pet-float.power-save * {
  animation: none !important;
}

/* Hover response */
.pet-float.is-hover .pet-tail {
  animation-duration: 0.7s;
}

.pet-float.is-hover .pet-eye {
  animation-duration: 1.8s;
}

.pet-float.is-hover .pet-head {
  transform: translateX(-50%) translateY(-6px) scale(1.04);
}

.pet-float.is-hover .pet-mouth {
  width: 28px;
  border-bottom-width: 3px;
}

/* DragFeedback */
.pet-float.is-drag .pet-body {
  animation-play-state: paused;
}

.pet-float.is-drag .pet-head {
  transform: translateX(-50%) scale(1.06);
}

.pet-float.is-drag .pet-shadow {
  transform: translateX(-50%) scale(0.6);
  opacity: 0.15;
}

.pet-float.is-drag .pet-tail {
  animation-duration: 0.5s;
}

/* ClickFeedback */
.pet-float.is-jump .pet-body {
  animation: pet-jump 0.55s cubic-bezier(0.3, -0.4, 0.4, 1.4);
}

/* Random wander: slight body bob and faster tail wag while walking */
.pet-float.is-walk .pet-body {
  animation: pet-walk 0.5s ease-in-out infinite;
}

.pet-float.is-walk .pet-tail {
  animation-duration: 0.45s;
}

.pet-float.is-walk .pet-shadow {
  animation: pet-walk-shadow 0.5s ease-in-out infinite;
}

/* Facing flip: flips only the body itself, does not affect the bubble/badge/text */
.pet-float.face-left .pet-body {
  --pet-flip: -1;
}

/* When facing flips, the overhead light ring mirrors as well (including the tilt direction) */
.pet-float.face-left .pet-rune-ring {
  --pet-flip: -1;
}

/* State linkage */
.pet-float.is-run .pet-body {
  animation-duration: 1.8s;
}

.pet-float.is-run .pet-tail {
  animation-duration: 1.1s;
}

.pet-float.is-idle .pet-body {
  animation-duration: 3.6s;
}

.pet-float.is-idle .pet-tail {
  animation-duration: 2.4s;
}

.pet-float.is-idle .pet-eye {
  animation-duration: 6.5s;
}

.pet-float.is-waiting .pet-body {
  animation-duration: 1.4s;
}

/* Waiting for inputTipBubble */
.pet-bubble {
  position: absolute;
  left: 50%;
  top: 6px;
  transform: translateX(-50%) scale(0.6);
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  color: #06131f;
  background: linear-gradient(135deg, #7ee7ff, #20c8ff);
  box-shadow: 0 0 14px rgba(32, 200, 255, 0.6);
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s ease, transform 0.25s ease;
}

/* Waiting for input no longer persistently shows the bubble (to avoid empty items); the bubble is shown only at is-speak (when there is temporary dialogue) */

/* Random small action */
.pet-float.act-look .pet-head {
  animation: pet-look 1.6s ease-in-out;
}

.pet-float.act-yawn .pet-mouth {
  animation: pet-yawn 1.6s ease-in-out;
}

.pet-float.act-spin .pet-body {
  animation: pet-spin 1.4s ease-in-out;
}

/* When soaring/flipping, the overhead light ring synchronously flips one full turn, echoing the pet action */
.pet-float.act-spin .pet-rune-ring {
  animation: pet-rune-flip 1.4s ease-in-out;
}

/* The overhead light ring is thrown out then flies back: both the flight and the spin are fast, using linear to keep the spin at constant speed */
.pet-float.act-throw .pet-rune-ring {
  animation: pet-rune-throw 2.4s linear;
}

.pet-float.act-hop .pet-body {
  animation: pet-jump 0.6s cubic-bezier(0.3, -0.4, 0.4, 1.4);
}

@keyframes pet-bob {
  0%,
  100% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(0);
  }
  50% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(calc(-13px * var(--pet-hop, 1)));
  }
}

/* Small shuffling bob and flattened shadow while wandering (--pet-flip carries the facing, default 1) */
@keyframes pet-walk {
  0%,
  100% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(0) rotate(-2deg);
  }
  50% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(-7px) rotate(2deg);
  }
}

@keyframes pet-walk-shadow {
  0%,
  100% {
    transform: translateX(-50%) scale(1);
    opacity: 0.35;
  }
  50% {
    transform: translateX(-50%) scale(0.82);
    opacity: 0.22;
  }
}

@keyframes pet-shadow {
  0%,
  100% {
    transform: translateX(-50%) scale(1);
    opacity: 0.35;
  }
  50% {
    transform: translateX(-50%) scale(0.82);
    opacity: 0.2;
  }
}

@keyframes pet-tail {
  0%,
  100% {
    transform: rotate(-8deg);
  }
  50% {
    transform: rotate(14deg);
  }
}

@keyframes pet-blink {
  0%,
  92%,
  100% {
    transform: scaleY(1);
  }
  96% {
    transform: scaleY(0.1);
  }
}

@keyframes pet-glow {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

@keyframes pet-spark {
  0%,
  100% {
    opacity: 0;
    transform: translateY(0) scale(0.6);
  }
  40% {
    opacity: 1;
    transform: translateY(-10px) scale(1);
  }
}

@keyframes pet-jump {
  0% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(0) scale(1, 1);
  }
  30% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(calc(-26px * var(--pet-hop, 1))) scale(0.94, 1.08);
  }
  60% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(0) scale(1.06, 0.94);
  }
  100% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(0) scale(1, 1);
  }
}

@keyframes pet-look {
  0%,
  100% {
    transform: translateX(-50%) rotate(0deg);
  }
  25% {
    transform: translateX(-50%) rotate(-7deg);
  }
  75% {
    transform: translateX(-50%) rotate(7deg);
  }
}

@keyframes pet-yawn {
  0%,
  100% {
    height: 12px;
    width: 23px;
  }
  50% {
    height: 22px;
    width: 30px;
    border-bottom-width: 4px;
  }
}

@keyframes pet-spin {
  0% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) rotate(0deg) scale(1);
  }
  50% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) rotate(180deg) scale(0.92);
  }
  100% {
    transform: translateX(-50%) scaleX(var(--pet-flip, 1)) rotate(360deg) scale(1);
  }
}

/* Overhead light ring soar/flip: on top of the original flatten/tilt/mirror, adds a full rotation */
@keyframes pet-rune-flip {
  0% {
    transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) rotate(0deg);
  }
  50% {
    transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) rotate(180deg);
  }
  100% {
    transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) rotate(360deg);
  }
}

/* Throw out: quickly flies to the screen edge and spins at constant speed, pauses for a moment, then quickly flies back to its original position */
@keyframes pet-rune-throw {
  0% {
    transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) translate(0, 0) rotate(0deg);
  }
  40% {
    transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) translate(calc(46vw * var(--pet-flip, 1)), -42vh) rotate(720deg);
  }
  52% {
    transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) translate(calc(50vw * var(--pet-flip, 1)), -45vh) rotate(936deg);
  }
  88% {
    transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) translate(calc(5vw * var(--pet-flip, 1)), -4vh) rotate(1584deg);
  }
  100% {
    transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) translate(0, 0) rotate(1800deg);
  }
}

@keyframes pet-bubble-bounce {
  0%,
  100% {
    transform: translateX(-50%) scale(1) translateY(0);
  }
  50% {
    transform: translateX(-50%) scale(1.06) translateY(-4px);
  }
}

/* ==================== Newly added interaction styles ==================== */
/* Pet overhead status badge (waiting/running) */
.pet-badge {
  position: absolute;
  left: 50%;
  top: 44px;
  transform: translateX(-50%);
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #06131f;
  background: linear-gradient(135deg, #7ee7ff, #20c8ff);
  border-radius: 11px;
  box-shadow: 0 0 12px rgba(32, 200, 255, 0.6);
  pointer-events: none;
  z-index: 4;
}

.pet-badge.is-alert {
  background: linear-gradient(135deg, #ffd166, #ff9800);
  box-shadow: 0 0 14px rgba(255, 152, 0, 0.7);
  animation: pet-badge-pulse 1.4s ease-in-out infinite;
}

/* When there is an agent waiting for input, the badge can be clicked to go */
.pet-badge.is-clickable {
  pointer-events: auto;
  cursor: pointer;
}

/* Move-end: enlarge the badge, convenient for finger tapping */
.pet-float.pet-compact .pet-badge {
  top: 22px;
  min-width: 34px;
  height: 34px;
  padding: 0 10px;
  font-size: 19px;
  border-radius: 17px;
}

/* Move-end: enlarge the badge's clickable hotspot (visually unchanged, hotspot expanded outward) */
.pet-float.pet-compact .pet-badge.is-clickable::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  width: 56px;
  height: 56px;
  transform: translate(-50%, -50%);
}

@keyframes pet-badge-pulse {
  0%, 100% { transform: translateX(-50%) scale(1); }
  50% { transform: translateX(-50%) scale(1.12); }
}

/* Restore button after hiding */
.pet-restore {
  position: fixed;
  z-index: 900;
  width: 40px;
  height: 40px;
  padding: 0;
  font-size: 18px;
  line-height: 1;
  border: 1px solid rgba(32, 200, 255, 0.4);
  border-radius: 50%;
  background: rgba(15, 30, 48, 0.9);
  cursor: grab;
  touch-action: none;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45), 0 0 12px rgba(32, 200, 255, 0.3);
  animation: pet-restore-in 0.25s ease-out;
  transition: background 0.18s ease;
}
.pet-restore:hover {
  transform: scale(1.1);
  background: rgba(32, 200, 255, 0.22);
}

@keyframes pet-restore-in {
  from { opacity: 0; transform: scale(0.6); }
  to { opacity: 1; transform: scale(1); }
}

/* ZZZ sleep badge ID */
.pet-zzz {
  position: absolute;
  color: rgba(126, 231, 255, 0.85);
  font-weight: 700;
  opacity: 0;
  pointer-events: none;
  text-shadow: 0 0 8px rgba(32, 200, 255, 0.6);
}

.pet-zzz.z1 { left: 58%; top: 42px; font-size: 13px; }
.pet-zzz.z2 { left: 68%; top: 26px; font-size: 15px; }
.pet-zzz.z3 { left: 78%; top: 8px; font-size: 18px; }

.pet-float.is-sleep .pet-zzz {
  animation: pet-zzz 2.4s ease-in-out infinite;
}

.pet-float.is-sleep .pet-zzz.z2 { animation-delay: 0.5s; }
.pet-float.is-sleep .pet-zzz.z3 { animation-delay: 1s; }

@keyframes pet-zzz {
  0% { opacity: 0; transform: translateY(6px) scale(0.8); }
  40% { opacity: 1; }
  100% { opacity: 0; transform: translateY(-14px) scale(1.1); }
}

/* Sleeping: closes eyes, body breathes slowly  */
.pet-float.is-sleep .pet-eye {
  animation: none;
  height: 4px;
  border-radius: 3px;
  margin-top: 8px;
}

.pet-float.is-sleep .pet-pupil {
  opacity: 0;
}

.pet-float.is-sleep .pet-body {
  animation-duration: 4.4s;
}

.pet-float.is-sleep .pet-tail {
  animation-duration: 3.6s;
}

.pet-float.is-sleep .pet-mouth {
  width: 14px;
  height: 8px;
}

/* Head pat */
.pet-float.is-petting .pet-head {
  animation: pet-pet-head 0.9s ease-in-out infinite;
}

.pet-float.is-petting .pet-eye {
  animation-duration: 1.6s;
}

.pet-float.is-petting .pet-tail {
  animation-duration: 0.6s;
}

@keyframes pet-pet-head {
  0%, 100% { transform: translateX(-50%) translateY(0) rotate(0deg); }
  50% { transform: translateX(-50%) translateY(-4px) rotate(2deg); }
}

/* Dialogue bubble: also shown when not waiting for input */
.pet-float.is-speak .pet-bubble {
  opacity: 1;
  transform: translateX(-50%) scale(1);
}

/* Double-click confetti (cheer) */
.pet-float.act-cheer .pet-body {
  animation: pet-jump 0.5s cubic-bezier(0.3, -0.4, 0.4, 1.4) 2;
}

/* Feeding chewing */
.pet-float.act-chomp .pet-mouth {
  animation: pet-chomp 0.36s ease-in-out 3;
}

@keyframes pet-chomp {
  0%, 100% { transform: translateX(-50%) scaleY(1); }
  50% { transform: translateX(-50%) scaleY(2.2); }
}

/* Chase ball */
.pet-float.act-chase .pet-body {
  animation: pet-chase 1.3s ease-in-out;
}

@keyframes pet-chase {
  0%, 100% { transform: translateX(-50%) translateY(0) rotate(0deg); }
  25% { transform: translateX(-50%) translateY(-8px) rotate(-7deg); }
  75% { transform: translateX(-50%) translateY(-8px) rotate(7deg); }
}

/* Singing sway */
.pet-float.act-sing .pet-body {
  animation: pet-sing 0.7s ease-in-out 2;
}

@keyframes pet-sing {
  0%, 100% { transform: translateX(-50%) rotate(-4deg); }
  50% { transform: translateX(-50%) rotate(4deg); }
}

/* Casting: body slightly levitates, overhead magic ring spins rapidly and glows brightly */
.pet-float.is-casting .pet-body {
  animation: pet-cast-float 1.5s ease-in-out;
}

.pet-float.is-casting .pet-rune-ring {
  --rune-spin-dur: 3.2s;
  animation: pet-cast-ring 1.5s ease-out;
}

.pet-float.is-casting .pet-rune-glyph {
  animation-duration: var(--rune-spin-dur, 26s), 0.5s;
}

.pet-float.is-casting .pet-rune-core {
  animation-duration: 0.5s;
  border-color: rgba(126, 231, 255, 0.85);
  box-shadow: inset 0 0 34px rgba(32, 200, 255, 0.55), 0 0 30px rgba(32, 200, 255, 0.5);
}

@keyframes pet-cast-float {
  0%, 100% { transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(0) scale(1); }
  30% { transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(-12px) scale(1.05); }
  60% { transform: translateX(-50%) scaleX(var(--pet-flip, 1)) translateY(-6px) scale(1.02); }
}

/* During casting the overhead light ring bursts larger then falls back */
@keyframes pet-cast-ring {
  0% { transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) scale(1); }
  35% { transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) scale(1.5); }
  100% { transform: translateX(-50%) rotate(-10deg) scaleY(0.42) scaleX(var(--pet-flip, 1)) scale(1); }
}
</style>

<!-- Dynamic effect elements (appended to body, need non-scoped styles) -->
<style>
.pet-fx,
.pet-confetti,
.pet-heart-fx,
.pet-food,
.pet-ball,
.pet-note,
.pet-spell-array {
  position: fixed;
  z-index: 3100;
  pointer-events: none;
  user-select: none;
}

/* ==================== Casting: foot spirit-light magic circle ==================== */
.pet-spell-array {
  width: 0;
  height: 0;
  /* Flattened into a ground-hugging ellipse, creating a top-down perspective */
  transform: translate(-50%, -50%) rotateX(62deg);
  transform-style: preserve-3d;
  animation: pet-array-in 1.9s ease-out forwards;
}

/*  Outer talisman ring: the whole ring slowly rotates */
.pet-array-glyphring {
  position: absolute;
  left: 0;
  top: 0;
  width: 0;
  height: 0;
  animation: pet-array-spin 6s linear infinite;
}

.pet-array-glyph {
  position: absolute;
  left: 0;
  top: 0;
  width: 20px;
  height: 20px;
  margin: -10px 0 0 -10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  color: var(--spell-color, #9fd8ff);
  text-shadow: 0 0 8px var(--spell-glow, #5db2ff), 0 0 16px var(--spell-glow, #5db2ff);
}

/*  Inner engraved-line ring: counter-rotating, dashed light edge */
.pet-array-linering {
  position: absolute;
  left: 0;
  top: 0;
  width: 92px;
  height: 92px;
  margin: -46px 0 0 -46px;
  border-radius: 50%;
  border: 1.5px dashed var(--spell-glow, #5db2ff);
  box-shadow: 0 0 14px var(--spell-glow, #5db2ff), inset 0 0 14px var(--spell-glow, #5db2ff);
  opacity: 0.85;
  animation: pet-array-spin-rev 4.5s linear infinite;
}

/*  Central geometric seal: two overlapping squares rotated 45° form an eight-pointed star */
.pet-array-seal {
  position: absolute;
  left: 0;
  top: 0;
  width: 0;
  height: 0;
  animation: pet-array-pulse 1.4s ease-in-out infinite;
}

.pet-array-seal i {
  position: absolute;
  left: 0;
  top: 0;
  width: 62px;
  height: 62px;
  margin: -31px 0 0 -31px;
  border: 1.5px solid var(--spell-color, #9fd8ff);
  box-shadow: 0 0 10px var(--spell-glow, #5db2ff), inset 0 0 10px var(--spell-glow, #5db2ff);
  opacity: 0.9;
}

.pet-array-seal i:nth-child(2) {
  transform: rotate(45deg);
}

/*  Central light core: a bit dazzling */
.pet-array-core {
  position: absolute;
  left: 0;
  top: 0;
  width: 26px;
  height: 26px;
  margin: -13px 0 0 -13px;
  border-radius: 50%;
  background: radial-gradient(circle, #ffffff 0%, var(--spell-color, #9fd8ff) 40%, transparent 72%);
  box-shadow: 0 0 22px var(--spell-glow, #5db2ff), 0 0 44px var(--spell-glow, #5db2ff);
  animation: pet-array-pulse 0.9s ease-in-out infinite;
}

@keyframes pet-array-in {
  0% { opacity: 0; scale: 0.4; }
  18% { opacity: 1; scale: 1.08; }
  30% { scale: 1; }
  78% { opacity: 1; scale: 1; }
  100% { opacity: 0; scale: 1.06; }
}

@keyframes pet-array-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pet-array-spin-rev {
  from { transform: rotate(0deg); }
  to { transform: rotate(-360deg); }
}

@keyframes pet-array-pulse {
  0%, 100% { opacity: 0.75; }
  50% { opacity: 1; }
}

.pet-fx {
  font-size: 15px;
  animation: pet-fx-float 1.3s ease-out forwards;
}

@keyframes pet-fx-float {
  0% { opacity: 0; transform: translateY(0) scale(0.6) rotate(0deg); }
  25% { opacity: 1; }
  100% { opacity: 0; transform: translateY(-46px) scale(1.15) rotate(var(--rot, 0deg)); }
}

.pet-confetti {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  animation: pet-confetti-fly 1.2s cubic-bezier(0.2, 0.7, 0.4, 1) forwards;
}

@keyframes pet-confetti-fly {
  0% { opacity: 1; transform: translate(0, 0) rotate(0deg) scale(1); }
  60% { opacity: 1; }
  100% { opacity: 0; transform: translate(var(--dx, 0), var(--dy, -60px)) rotate(var(--rot, 180deg)) scale(0.5); }
}

.pet-heart-fx {
  font-size: 16px;
  color: #ff8ad8;
  animation: pet-heart-float 1.2s ease-out forwards;
}

@keyframes pet-heart-float {
  0% { opacity: 0; transform: translate(0, 0) scale(0.6); }
  25% { opacity: 1; }
  100% { opacity: 0; transform: translate(var(--dx, 0), -52px) scale(1.2); }
}

.pet-food {
  font-size: 22px;
  animation: pet-food-drop 0.85s cubic-bezier(0.5, 0, 0.8, 1) forwards;
}

@keyframes pet-food-drop {
  0% { opacity: 0; transform: translate(-50%, -30px) scale(0.7); }
  30% { opacity: 1; }
  100% { opacity: 0; transform: translate(-50%, 46px) scale(1.05); }
}

.pet-ball {
  font-size: 20px;
  animation: pet-ball-fly 1.4s ease-in-out forwards;
}

@keyframes pet-ball-fly {
  0% { opacity: 0; transform: translate(0, 0) rotate(0deg); }
  15% { opacity: 1; }
  50% { transform: translate(calc(var(--fly, 200px) / 2), -34px) rotate(180deg); }
  100% { opacity: 0; transform: translate(var(--fly, 200px), 0) rotate(360deg); }
}

.pet-note {
  font-size: 17px;
  color: #7ee7ff;
  text-shadow: 0 0 8px rgba(32, 200, 255, 0.6);
  animation: pet-note-float 1.6s ease-out forwards;
}

@keyframes pet-note-float {
  0% { opacity: 0; transform: translate(0, 0) scale(0.7); }
  20% { opacity: 1; }
  100% { opacity: 0; transform: translate(var(--dx, 0), -70px) scale(1.1) rotate(12deg); }
}
/* ==================== Casting: Remote spirit light / area impact / Myriad Swords Return ==================== */
/* Remote light beam: energy trail shot out from the pet */
.pet-spell-beam {
  position: fixed;
  z-index: 3100;
  pointer-events: none;
  height: 3px;
  border-radius: 3px;
  transform-origin: 0 50%;
  background: linear-gradient(90deg,
    transparent 0%,
    var(--spell-glow, #5db2ff) 12%,
    var(--spell-color, #9fd8ff) 55%,
    #ffffff 100%);
  box-shadow: 0 0 10px var(--spell-glow, #5db2ff), 0 0 22px var(--spell-glow, #5db2ff);
  animation: pet-beam-fire var(--beam-dur, 0.7s) cubic-bezier(0.2, 0.8, 0.3, 1) forwards;
}

@keyframes pet-beam-fire {
  0% { opacity: 0; scale: 0 0.4; }
  25% { opacity: 1; scale: 1 1; }
  100% { opacity: 0; scale: 1 1; }
}

/* Flying rune: darts along the light beam direction */
.pet-spell-bolt {
  position: fixed;
  z-index: 3101;
  pointer-events: none;
  width: 0;
  height: 0;
  font-size: 24px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: pet-bolt-fly var(--beam-dur, 0.7s) cubic-bezier(0.3, 0.5, 0.2, 1) forwards;
}

@keyframes pet-bolt-fly {
  0% { opacity: 0; transform: translate(-50%, -50%) scale(0.5) rotate(0deg); }
  15% { opacity: 1; }
  85% { opacity: 1; }
  100% { opacity: 0; transform: translate(calc(-50% + var(--bx, 0px)), calc(-50% + var(--by, 0px))) scale(1.15) rotate(540deg); }
}

/* Impact center burst point: explodes after reaching the target position  */
.pet-spell-hit {
  position: fixed;
  z-index: 3101;
  pointer-events: none;
  width: 10px;
  height: 10px;
  margin: -5px 0 0 -5px;
  border-radius: 50%;
  border: 2px solid transparent;
  opacity: 0;
  animation: pet-hit-burst 0.5s ease-out forwards;
}

@keyframes pet-hit-burst {
  0% { opacity: 0; transform: scale(0.3); }
  30% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(7); }
}

/* ==================== Myriad Swords Return ==================== */
.pet-spell-sword {
  position: fixed;
  z-index: 3101;
  pointer-events: none;
  width: 0;
  height: 0;
  /* Flies along a JS-generated Bezier curve; the start point is the element's anchor point */
  offset-path: var(--sw-path);
  offset-rotate: auto;
  animation: pet-sword-swarm var(--sw-dur, 1.7s) cubic-bezier(0.32, 0.02, 0.5, 1) forwards;
}

/* Blade: slender light cone, pointing in the flight direction */
.pet-sword-blade {
  position: absolute;
  left: 0;
  top: 0;
  width: 26px;
  height: 2.5px;
  margin: -1.25px 0 0 -2px;
  border-radius: 2px 50% 50% 2px;
  background: linear-gradient(90deg, transparent 0%, var(--spell-glow, #6f9dff) 30%, #ffffff 100%);
  box-shadow: 0 0 8px var(--spell-glow, #6f9dff), 0 0 16px var(--spell-glow, #6f9dff);
}

/* Hilt: a shorter dark base */
.pet-sword-hilt {
  position: absolute;
  left: 0;
  top: 0;
  width: 8px;
  height: 3px;
  margin: -1.5px 0 0 -8px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--spell-glow, #6f9dff) 70%, #ffffff 30%);
  box-shadow: 0 0 6px var(--spell-glow, #6f9dff);
}

/* Stabs outward along the curve and returns home: both ends at the pet body (the curve closes), flying far in the middle */
@keyframes pet-sword-swarm {
  0% { opacity: 0; offset-distance: 0%; scale: 0.6; }
  12% { opacity: 1; }
  50% { offset-distance: 50%; scale: 1.15; }
  90% { opacity: 1; }
  100% { opacity: 0; offset-distance: 100%; scale: 0.5; }
}

/* Sword formation start: a sword-intent light ring at the feet */
.pet-spell-swarm-sigil {
  position: fixed;
  z-index: 3099;
  pointer-events: none;
  width: 0;
  height: 0;
  border-radius: 50%;
  border: 1.5px dashed transparent;
  animation: pet-swarm-sigil 1.6s ease-out forwards;
}

@keyframes pet-swarm-sigil {
  0% { opacity: 0; width: 0; height: 0; margin: 0; }
  20% { opacity: 1; width: 70px; height: 70px; margin: -35px 0 0 -35px; }
  100% { opacity: 0; width: 190px; height: 190px; margin: -95px 0 0 -95px; }
}

/* Central gathering light at the moment of returning */
.pet-spell-swarm-core {
  position: fixed;
  z-index: 3100;
  pointer-events: none;
  width: 90px;
  height: 90px;
  margin: -45px 0 0 -45px;
  border-radius: 50%;
  opacity: 0;
  animation: pet-swarm-core 0.9s ease-out forwards;
}

@keyframes pet-swarm-core {
  0% { opacity: 0; transform: scale(1.6); }
  35% { opacity: 1; transform: scale(0.9); }
  100% { opacity: 0; transform: scale(0.3); }
}
</style>
