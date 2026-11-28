// Workspace pane tree / free splitting / sidebar composable.
//
// Extracted from App.vue's <script setup> (Issue #118 Step 10 PR-2, originally lines 2948-4098),
// preserving behavior exactly:
// - Workspace panel state: workspacePanelRect / workspacePanelInteraction / workspacePanelRef /
//   isWorkspaceMaximized / workspacePanelRectBeforeMaximize / splitWorkspaceContainerRefs /
//   editorContainerRef / workspaceSessions / activeWorkspaceSessionId / workspaceTabs /
//   activeWorkspaceTabPath / activeWorkspaceSession / virtualWorkspaceSessions / editorModels /
//   workspaceFileHeartbeatTimer / isWorkspaceEditable / EDITOR_FILE_HEARTBEAT_INTERVAL /
//   globalSearch* / fileSearchResults / showWorkspaceSidebar / workspaceSidebarView / workspaceMainView
// - Pane tree core: workspacePaneTree / activePaneId / maximizedPaneId / workspacePaneCount /
//   canSplitWorkspacePane / activePane / findWorkspacePaneById / ... / restoreWorkspacePaneLayout /
//   restoreWorkspacePaneContents
// - Plugin frontend extensions: internally calls usePlugins (returns pluginExtensions etc. for templates/external use)
//
// Dependency injection (passed in by the caller within setup; must be called after they are defined):
// - Directly passed (defined before this composable's call site): fetchWithAuth / getGatewayAddress / getHttpProtocol /
//   hasAuthToken / windowWidth / clamp / focusWindow / getWorkspaceTabByPath / activeWorkspaceTab /
//   editorViews / workspaceViewPanes /
//   diffEditorViews / workspacePaneTabs / workspacePaneTabsVersion / remountMonacoEditor /
//   scheduleWorkspaceLayout / layoutMonacoEditor / activateWorkspaceTab / openWorkspaceFile /
//   layoutGitDiffEditor / disposeDiffEditorForPane / disposeAllDiffEditors / loadDiffForPane (getter-injected)
// - Getter-injected (defined after the call site, evaluated again internally via xxx()): panels / activePanelId /
//   closePanel / getPanelAgent / workspaceSessionPanelId / agentList / gitAgentId / switchAgent /
//   activeTerminalId / terminalSessions / restoreTerminalSessions / focusFirstIn
import { computed, nextTick, ref, triggerRef, watch } from 'vue'
import { usePlugins } from './usePlugins.js'
import { fetchPluginExtensions, loadExtensionComponent } from '../pluginExtensions.js'
export function useWorkspacePane({
  fetchWithAuth,
  getGatewayAddress,
  getHttpProtocol,
  hasAuthToken,
  windowWidth,
  // Symbols below are defined by useWorkspaceEditor (domain B); this composable's call site comes before them,
  // so they are getter-injected (evaluated again internally via xxx(); function types are safely wrapped so the call site is unchanged).
  clamp: clampGetter,
  focusWindow: focusWindowGetter,
  getWorkspaceTabByPath: getWorkspaceTabByPathGetter,
  activeWorkspaceTab: activeWorkspaceTabGetter,
  editorViews: editorViewsGetter,
  workspaceViewPanes: workspaceViewPanesGetter,
  diffEditorViews: diffEditorViewsGetter,
  workspacePaneTabs: workspacePaneTabsGetter,
  workspacePaneTabsVersion: workspacePaneTabsVersionGetter,
  remountMonacoEditor: remountMonacoEditorGetter,
  scheduleWorkspaceLayout: scheduleWorkspaceLayoutGetter,
  layoutMonacoEditor: layoutMonacoEditorGetter,
  activateWorkspaceTab: activateWorkspaceTabGetter,
  openWorkspaceFile: openWorkspaceFileGetter,
  layoutGitDiffEditor,
  disposeDiffEditorForPane,
  disposeAllDiffEditors,
  loadDiffForPane,
  panels,
  activePanelId,
  closePanel,
  getPanelAgent,
  workspaceSessionPanelId,
  agentList,
  gitAgentId,
  switchAgent,
  activeTerminalId,
  terminalSessions,
  restoreTerminalSessions,
  focusFirstIn,
}) {
  // —— Safe wrappers for getter-ized dependencies (function types: call site unchanged; Map/ref types: call site becomes xxx().get()/xxx().value) ——
  const clamp = (...args) => clampGetter()(...args)
  const focusWindow = (...args) => focusWindowGetter()(...args)
  const getWorkspaceTabByPath = (...args) => getWorkspaceTabByPathGetter()(...args)
  const editorViews = () => editorViewsGetter()
  const workspaceViewPanes = () => workspaceViewPanesGetter()
  const diffEditorViews = () => diffEditorViewsGetter()
  const workspacePaneTabs = () => workspacePaneTabsGetter()
  const workspacePaneTabsVersion = () => workspacePaneTabsVersionGetter()
  const remountMonacoEditor = () => { const fn = remountMonacoEditorGetter(); if (fn) fn() }
  const scheduleWorkspaceLayout = () => { const fn = scheduleWorkspaceLayoutGetter(); if (fn) fn() }
  const layoutMonacoEditor = () => { const fn = layoutMonacoEditorGetter(); if (fn) fn() }
  const activateWorkspaceTab = (...args) => { const fn = activateWorkspaceTabGetter(); if (fn) return fn(...args) }
  const openWorkspaceFile = (...args) => { const fn = openWorkspaceFileGetter(); if (fn) return fn(...args) }
  const activeWorkspaceTab = () => activeWorkspaceTabGetter()

const EDITOR_PANEL_MIN_WIDTH = 360
const EDITOR_PANEL_MIN_HEIGHT = 260
const EDITOR_PANEL_STORAGE_KEY = 'haijunbot_workspace_panel_rect'
const workspaceResizeDirections = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']
const PANEL_DRAG_ACTIVATION_DISTANCE = 4

// Window maximization state
const isWorkspaceMaximized = ref(false)
const workspacePanelRectBeforeMaximize = ref(null)

function getDefaultWorkspacePanelRect() {
  return {
    top: 88,
    left: Math.max(window.innerWidth - 824, 16),
    width: 800,
    height: 600,
  }
}

function loadWorkspacePanelRect() {
  const defaultWorkspacePanelRect = getDefaultWorkspacePanelRect()
  const savedValue = localStorage.getItem(EDITOR_PANEL_STORAGE_KEY)
  if (!savedValue) {
    return defaultWorkspacePanelRect
  }

  try {
    const parsedValue = JSON.parse(savedValue)
    if (
      typeof parsedValue.top !== 'number' ||
      typeof parsedValue.left !== 'number' ||
      typeof parsedValue.width !== 'number' ||
      typeof parsedValue.height !== 'number'
    ) {
      return defaultWorkspacePanelRect
    }

    return parsedValue
  } catch {
    return defaultWorkspacePanelRect
  }
}

function saveWorkspacePanelRect() {
  localStorage.setItem(EDITOR_PANEL_STORAGE_KEY, JSON.stringify(workspacePanelRect.value))
}

const workspacePanelRect = ref(loadWorkspacePanelRect())
const workspacePanelInteraction = ref({
  active: false,
  mode: null,
  direction: null,
  startX: 0,
  startY: 0,
  startTop: 0,
  startLeft: 0,
  startWidth: 0,
  startHeight: 0,
})
const workspacePanelRef = ref(null)
// Free splitting: each file pane has its own Monaco container (paneId -> hostEl).
// Note: the container's ref callback runs during Vue's render commit phase, which may be later than the
// nextTick in splitWorkspacePane, so we actively schedule an instance backfill after the container is mounted
// (scheduleWorkspaceLayout coalesces via rAF); relying only on the caller calling remountMonacoEditor in nextTick is not enough.
const splitWorkspaceContainerRefs = ref(new Map())
function setSplitWorkspaceContainerRef(paneId, el) {
  if (!paneId) return
  if (el) {
    if (splitWorkspaceContainerRefs.value.get(paneId) === el) return
    splitWorkspaceContainerRefs.value.set(paneId, el)
  } else {
    if (!splitWorkspaceContainerRefs.value.has(paneId)) return
    splitWorkspaceContainerRefs.value.delete(paneId)
  }
  triggerRef(splitWorkspaceContainerRefs)
  // Backfill instances after the container is mounted/unmounted. We do not check the pane count here
  // because the ref callback may run before the computed recomputation triggered by a workspacePaneTree
  // change, and a count check would miss the first "split" at that moment.
  scheduleWorkspaceLayout()
}
// Monaco container of the active pane; when the active pane is not a file pane, fall back to any file pane
// container so that operations like "open file" still have a usable container. Prefer elements that are
// actually mounted in the document (ref elements may be in an intermediate render state, detached from the document).
const splitWorkspaceContainerRef = computed(() => {
  const active = splitWorkspaceContainerRefs.value.get(activePaneId.value)
  if (active && active.isConnected) return active
  for (const paneId of splitWorkspaceContainerRefs.value.keys()) {
    const live = document.querySelector(`.workspace-monaco-container[data-pane-id="${paneId}"]`)
    if (live && live.isConnected) return live
  }
  if (active) return active
  for (const [, hostEl] of splitWorkspaceContainerRefs.value) return hostEl
  return null
})
// The workspace is always a pane tree: Monaco containers are always registered by each file pane's setSplitWorkspaceContainerRef.
const editorContainerRef = computed(() => splitWorkspaceContainerRef.value)
// Multi-instance editor management (similar to terminalSessions)
const workspaceSessions = ref([])  // [{ agent_id, agent_name, tabs: [], activeTabPath: null, editorModels: new Map() }]
const activeWorkspaceSessionId = ref(null)  // agent_id of the currently active editor session

// Backward-compatible computed properties
const workspaceTabs = computed(() => {
  const session = workspaceSessions.value.find(s => s.agent_id === activeWorkspaceSessionId.value)
  return session ? session.tabs : []
})
const activeWorkspaceTabPath = computed(() => {
  const session = workspaceSessions.value.find(s => s.agent_id === activeWorkspaceSessionId.value)
  return session ? session.activeTabPath : null
})
const activeWorkspaceSession = computed(() => {
  return workspaceSessions.value.find(s => s.agent_id === activeWorkspaceSessionId.value) || null
})
// Virtual-directory sessions (directories opened without creating an Agent), rendered extra by the directory tree
const virtualWorkspaceSessions = computed(() => {
  return workspaceSessions.value.filter(s => s.agent?.virtual === true)
})
const editorModels = new Map() // path -> { model: ITextModel, content: string, language: string }
const workspaceFileHeartbeatTimer = ref(null)
const isWorkspaceEditable = ref(false)  // Editor editable switch, read-only by default
const EDITOR_FILE_HEARTBEAT_INTERVAL = 3000
const globalSearchQuery = ref('')
const globalSearchFileGlob = ref('')
const globalSearchCaseSensitive = ref(false)
const globalSearchWholeWord = ref(false)
const globalSearchLoading = ref(false)
const globalSearchError = ref('')
const globalSearchResults = ref([])
const globalSearchTotalFiles = ref(0)
const globalSearchTotalMatches = ref(0)
const globalSearchExecuted = ref(false)
// Search modes: 'content' searches file contents, 'filename' does a fuzzy filename search
const globalSearchMode = ref('content')
const fileSearchResults = ref([])
const showWorkspaceSidebar = ref(true)
// Show the Agent list by default (instead of the file directory tree)
const workspaceSidebarView = ref('agents')
// Plugin frontend extensions (extracted from the usePlugins composable; see the usePlugins call below)
const {
  pluginExtensions,
  pluginAdminTabs,
  pluginSidebarViews,
  pluginToolPanels,
  pluginSidebarTitle,
  pluginToolPanelTitle,
  WORKSPACE_SIDEBAR_TITLES,
  workspaceSidebarTitle,
  loadPluginExtensionsForUi,
  resolvePluginExtensionComponent,
  isPluginSidebarView,
  isPluginToolView,
  pluginSidebarCompCache,
  activePluginSidebarComp,
  activePluginToolPanelComp,
} = usePlugins({
  workspaceSidebarView,
  fetchPluginExtensions,
  loadExtensionComponent,
  fetchWithAuth,
  getHttpProtocol,
  hasAuthToken,
  getGatewayAddress,
})
// Editor main-area view: 'file' shows the code editor/diff, 'chat' shows the chat room, 'terminal' shows the terminal.
// Unified to the pane tree model: the only leaf is the main area, so the main-area view = the only leaf's view (derived).
// When split, the main-area semantics are carried by each pane; here we return 'file' to stay compatible with legacy read sites.
const workspaceMainView = computed(() => {
  const root = workspacePaneTree.value
  if (root && root.type === 'leaf') return root.view
  return 'file'
})

// ===== Editor main workspace "free splitting" (same as VS Code split) =====
// Layout model: tree nodes
//   split: { type:'split', direction:'row'|'column', ratio:number, children:[node, node] }
//   leaf : { type:'leaf', id:string, view:'file'|'session'|'chat'|'terminal'|'diff', sessionPanelId:string|null, diff?:object }
// Since phase 3, chat / terminal can also be a leaf's view (host singleton: only one pane may host it at a time).
// diff as a leaf's view: each diff pane gets its own Monaco DiffEditor instance (multi-instance, no host-singleton constraint);
// diff data (commitHash/filePath etc.) is stored on leaf.diff and not persisted (degrades to file after refresh).
const EDITOR_PANE_MIN_RATIO = 0.15
const EDITOR_PANE_MAX_RATIO = 0.85
let workspacePaneSeq = 0
function createWorkspacePaneLeaf(view = 'file', sessionPanelId = null, agentId = null) {
  workspacePaneSeq += 1
  return { type: 'leaf', id: `pane-${workspacePaneSeq}`, view, sessionPanelId, agentId }
}
// Root default single leaf: when unsplit, behavior is exactly the same as before the change
const workspacePaneTree = ref(createWorkspacePaneLeaf('file'))
const activePaneId = ref(workspacePaneTree.value.id)
// The leaf id in "temporary maximization": that leaf is promoted via CSS to a fullscreen overlay (DOM is not moved,
// so Monaco/xterm instances are rebuilt zero times); clicking again just removes the class and embeds it back into the layout. null means no maximization.
const maximizedPaneId = ref(null)
// Whether splitting has occurred (>1 leaf). When unsplit, the template uses the original rendering path, guaranteeing zero regression.
const workspacePaneCount = computed(() => {
  let count = 0
  const walk = (node) => {
    if (!node) return
    if (node.type === 'leaf') {
      count += 1
      return
    }
    ;(node.children || []).forEach(walk)
  }
  walk(workspacePaneTree.value)
  return count
})
// Whether to show the "split" button: when unsplit, file view and session/chat/terminal views all allow splitting
// (splitting freezes the current main view into the original pane, the new pane is a file pane, see splitWorkspacePane;
//  chat/terminal are host singletons, so the new pane is always a file pane and two panes never fight over the same host).
const canSplitWorkspacePane = computed(() => {
  // Mobile does not support splitting (divider dragging and multi-pane layouts are unusable on narrow screens); hide the split button
  if (windowWidth.value <= 768) return false
  if (workspacePaneCount.value > 1) return false
  return ['file', 'session', 'chat', 'terminal'].includes(workspaceMainView.value)
})
const activePane = computed(() => findWorkspacePaneById(workspacePaneTree.value, activePaneId.value))
function findWorkspacePaneById(node, paneId) {
  if (!node) return null
  if (node.type === 'leaf') return node.id === paneId ? node : null
  for (const child of node.children || []) {
    const found = findWorkspacePaneById(child, paneId)
    if (found) return found
  }
  return null
}
// Find the parent split node of a given leaf
function findWorkspacePaneParent(node, paneId) {
  if (!node || node.type === 'leaf') return null
  for (const child of node.children || []) {
    if (child.type === 'leaf' && child.id === paneId) return node
    const found = findWorkspacePaneParent(child, paneId)
    if (found) return found
  }
  return null
}
function activateWorkspacePane(paneId, { moveFocus = false } = {}) {
  if (!findWorkspacePaneById(workspacePaneTree.value, paneId)) return
  if (activePaneId.value === paneId) return
  activePaneId.value = paneId
  // When activating a session pane, sync the current Agent so the sidebar Agent highlight follows the switch (same as activatePanel)
  const pane = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (pane && pane.view === 'session' && pane.sessionPanelId) {
    const panel = panels().value.find(p => p.id === pane.sessionPanelId)
    const agent = panel?.agentId ? agentList().value.find(a => a.agent_id === panel.agentId) : null
    if (agent) switchAgent()(agent)
  }
  // Activating a pane switches the Monaco container (only the active pane renders a real container), so the view needs to be rebuilt
  nextTick(() => {
    remountMonacoEditor()
    // When switching with arrow keys, also move keyboard focus into the new pane's content (otherwise focus stays on the old pane)
    if (moveFocus) focusWorkspacePane(paneId)
  })
}
// Temporarily maximize/restore a given leaf: while maximized, the leaf is promoted via CSS to a fullscreen overlay
// (DOM is not moved, Monaco/xterm instances are not rebuilt); restoring just removes the class and embeds it back into the layout.
function toggleMaximizeWorkspacePane(paneId) {
  if (!findWorkspacePaneById(workspacePaneTree.value, paneId)) return
  if (maximizedPaneId.value === paneId) {
    maximizedPaneId.value = null
  } else {
    // Before maximizing, activate the pane and raise the workspace panel to the top so it is not covered by other higher-level panels.
    activateWorkspacePane(paneId)
    focusWindow('workspace')
    maximizedPaneId.value = paneId
  }
  // Layout size changed, notify Monaco/diff to re-layout
  nextTick(() => {
    remountMonacoEditor()
    layoutGitDiffEditor()()
  })
}
// Move keyboard focus to a given pane's content (so focus follows after arrow-key activation switches)
// file/diff panes focus their Monaco editor instance; others (session/chat/terminal/empty) focus the first focusable element inside the pane
function focusWorkspacePane(paneId) {
  const pane = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (!pane) return
  if (pane.view === 'file') {
    const view = editorViews().get(paneId)
    if (view && typeof view.focus === 'function') {
      view.focus()
      return
    }
  }
  if (pane.view === 'diff') {
    const entry = diffEditorViews().get(paneId)
    if (entry && entry.editor && typeof entry.editor.focus === 'function') {
      entry.editor.focus()
      return
    }
  }
  const leafEl = document.querySelector(`.workspace-pane-leaf[data-pane-id="${paneId}"]`)
  if (leafEl) focusFirstIn()(leafEl)
}
// Find the path from the root to a given leaf in the pane tree (all nodes, root and leaf included)
function findWorkspacePanePath(node, paneId, path = []) {
  if (!node) return null
  if (node.type === 'leaf') {
    return node.id === paneId ? [...path, node] : null
  }
  for (const child of node.children || []) {
    const result = findWorkspacePanePath(child, paneId, [...path, node])
    if (result) return result
  }
  return null
}
// Return the leaf at the outermost edge of a node's subtree in the dir direction (for directional navigation to land on a specific pane within the target subtree)
function findWorkspacePaneEdgeLeaf(node, dir) {
  if (!node) return null
  if (node.type === 'leaf') return node
  const row = node.direction === 'row'
  const col = node.direction === 'column'
  let childIdx = 0
  if ((dir === 'left' && row) || (dir === 'up' && col)) childIdx = 0
  else if ((dir === 'right' && row) || (dir === 'down' && col)) childIdx = 1
  return findWorkspacePaneEdgeLeaf(node.children[childIdx], dir)
}
// Switch the active area among split panes using Ctrl+Alt+Arrow keys
// dir: 'left'|'right'|'up'|'down'; returns whether the switch happened (false when unsplit or no switchable pane)
function moveActivePaneInDirection(dir) {
  if (workspacePaneCount.value <= 1) return false
  const path = findWorkspacePanePath(workspacePaneTree.value, activePaneId.value)
  if (!path || path.length < 2) return false
  const leaf = path[path.length - 1]
  // Walk up from the leaf's parent split, looking for the first split satisfying the direction condition
  for (let i = path.length - 2; i >= 0; i--) {
    const node = path[i]
    if (node.type !== 'split') continue
    const childIdx = node.children.findIndex(c => !!findWorkspacePaneById(c, leaf.id))
    if (childIdx < 0) continue
    const row = node.direction === 'row'
    const col = node.direction === 'column'
    const match =
      (dir === 'left' && row && childIdx === 1) ||
      (dir === 'right' && row && childIdx === 0) ||
      (dir === 'up' && col && childIdx === 1) ||
      (dir === 'down' && col && childIdx === 0)
    if (!match) continue
    const targetChild = node.children[1 - childIdx]
    const targetLeaf = findWorkspacePaneEdgeLeaf(targetChild, dir)
    if (targetLeaf) {
      activateWorkspacePane(targetLeaf.id, { moveFocus: true })
      return true
    }
  }
  return false
}
// Find the "largest-area" pane (as the target for programmatic splits): walk all leaves and compute the area
// (width x height) of each via its DOM getBoundingClientRect, returning the id of the largest-area leaf.
// When no DOM is available (unsplit / not yet mounted), fall back to the currently active pane, preserving legacy behavior.
function findLargestWorkspacePaneId() {
  let largestId = activePaneId.value
  let largestArea = -1
  const walk = (node) => {
    if (!node) return
    if (node.type === 'leaf') {
      const el = document.querySelector(`.workspace-pane-leaf[data-pane-id="${node.id}"]`)
      if (el) {
        const rect = el.getBoundingClientRect()
        if (rect) {
          const area = rect.width * rect.height
          if (area > largestArea) {
            largestArea = area
            largestId = node.id
          }
        }
      }
      return
    }
    ;(node.children || []).forEach(walk)
  }
  walk(workspacePaneTree.value)
  return largestId
}
// Compute the "automatic split" direction: take the width/height of the "largest-area" pane; if height > width,
// split vertically (column), otherwise horizontally (row).
// Used for programmatic splits such as clicking a sidebar file / opening a panel (keyboard shortcuts where the user
// explicitly specifies a direction are unaffected).
// Falls back to 'row' when the pane's DOM is unavailable (unsplit / not yet mounted), preserving legacy behavior.
function computeSplitDirection() {
  const paneId = findLargestWorkspacePaneId()
  if (paneId) {
    const el = document.querySelector(`.workspace-pane-leaf[data-pane-id="${paneId}"]`)
    if (el) {
      const rect = el.getBoundingClientRect()
      if (rect && rect.height > rect.width) return 'column'
    }
  }
  return 'row'
}

// Split a given leaf in the dir direction: replace the leaf with a split, keeping the original leaf first,
// and make the new leaf the active pane.
// Note: session / chat / terminal leaves cannot have their hosted content copied to the new leaf (otherwise the same
// Panel or the same host singleton would be hosted by two panes, and xterm / chat state would fight each other),
// so the new leaf is always a file leaf.
function splitWorkspacePane(paneId, direction) {
  if (windowWidth.value <= 768) return
  const parent = findWorkspacePaneParent(workspacePaneTree.value, paneId)
  const target = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (!target) return
  // Unified to the pane tree model: when unsplit, the only leaf is the main area, and its view/content is hosted by that leaf.
  // When splitting, the target is that leaf, so the content is naturally preserved, no migration needed.
  // The new pane is always an "empty" leaf: without any file/session/chat/terminal attributes,
  // and the user must explicitly open a file/session before it has content (to avoid a new pane showing files or sessions out of nowhere).
  const newLeaf = createWorkspacePaneLeaf('empty')
  const splitNode = {
    type: 'split',
    direction: direction === 'column' ? 'column' : 'row',
    ratio: 0.5,
    children: [target, newLeaf],
  }
  if (!parent) {
    workspacePaneTree.value = splitNode
  } else {
    const index = parent.children.indexOf(target)
    parent.children.splice(index, 1, splitNode)
  }
  // First split: freeze the current global tab list into the "original pane", and the new pane starts empty.
  // This way the two panes each have an independent tab bar that do not affect each other.
  if (!workspacePaneTabs().has(target.id)) {
    workspacePaneTabs().set(target.id, workspaceTabs.value.map(t => t.path))
    workspacePaneTabsVersion().value += 1
  }
  // On first split, bind the currently open file to the original pane's workspaceViewPanes;
  // otherwise both panes' instances call setModel(null) -> neither sees a file.
  if (target.view === 'file' && !workspaceViewPanes().has(target.id)) {
    const currentPath = activeWorkspaceTabPath.value
    if (currentPath) workspaceViewPanes().set(target.id, currentPath)
  }
  activePaneId.value = newLeaf.id
  // Splitting changes the layout; if previously maximized, restore it first
  maximizedPaneId.value = null
  persistWorkspacePaneLayout()
  nextTick(() => {
    remountMonacoEditor()
    layoutGitDiffEditor()()
  })
}
// Close a given leaf: the sibling replaces it; closing is not allowed when only one leaf remains.
function closeWorkspacePane(paneId) {
  if (workspacePaneCount.value <= 1) return
  const parent = findWorkspacePaneParent(workspacePaneTree.value, paneId)
  if (!parent) return
  const index = parent.children.findIndex(child => child.type === 'leaf' && child.id === paneId)
  if (index < 0) return
  parent.children.splice(index, 1)
  // The pane's independent tab list is discarded too (files still referenced by other panes are kept)
  workspacePaneTabs().delete(paneId)
  workspacePaneTabsVersion().value += 1
  // If the pane hosted a diff, release its independent diff instance
  disposeDiffEditorForPane()(paneId)
  // When the parent node has only one child left, replace the parent with that child (collapse redundant levels)
  if (parent.children.length === 1) {
    const only = parent.children[0]
    if (parent === workspacePaneTree.value) {
      workspacePaneTree.value = only
    } else {
      // Locate parent in the tree and replace it with only
      const replaceNode = (node) => {
        if (!node || node.type === 'leaf') return false
        const idx = node.children.indexOf(parent)
        if (idx >= 0) {
          node.children.splice(idx, 1, only)
          return true
        }
        return (node.children || []).some(replaceNode)
      }
      replaceNode(workspacePaneTree.value)
    }
  }
  if (!findWorkspacePaneById(workspacePaneTree.value, activePaneId.value)) {
    activePaneId.value = findFirstWorkspacePaneId(workspacePaneTree.value)
  }
  // If the closed pane is currently maximized, clear the maximization state
  if (maximizedPaneId.value && !findWorkspacePaneById(workspacePaneTree.value, maximizedPaneId.value)) {
    maximizedPaneId.value = null
  }
  // Unified to the pane tree model: after closing, when back to unsplit (only one leaf remains), that leaf is the
  // main area, and its view/content is naturally preserved, so no migration back to workspaceMainView is needed.
  persistWorkspacePaneLayout()
  nextTick(() => {
    remountMonacoEditor()
    layoutGitDiffEditor()()
  })
}
function findFirstWorkspacePaneId(node) {
  if (!node) return null
  if (node.type === 'leaf') return node.id
  for (const child of node.children || []) {
    const found = findFirstWorkspacePaneId(child)
    if (found) return found
  }
  return null
}
// Collapse all splits back to a single file leaf (called when switching to chat/terminal or when a reset is needed)
function collapseWorkspacePanes() {
  const leaf = createWorkspacePaneLeaf('file')
  workspacePaneTree.value = leaf
  activePaneId.value = leaf.id
  maximizedPaneId.value = null
  // Collapse back to the global tab bar and clear each pane's independent list
  workspacePaneTabs().clear()
  workspacePaneTabsVersion().value += 1
  // Collapse: release all diff panes' independent instances
  disposeAllDiffEditors()()
}

// ===== Phase 2: left-side clicks route to the "active pane" =====
// Design: each leaf holds its own view ('file' | 'session') and sessionPanelId.
// Left-side clicks (file tree / Agent list / search results) rewrite the "active pane" view when split,
// and use the original workspaceMainView path when unsplit (guaranteeing zero regression).
// Constraint: the same sessionPanelId must not appear in two panes at once (terminal host singleton, they would fight),
// so routing to a session first clears the same sessionPanelId from other panes.

// Find the leaf (other than exceptPaneId) currently hosting a given sessionPanelId (used for dedup)
function findWorkspacePaneBySessionPanelId(sessionPanelId, exceptPaneId = null) {
  if (!sessionPanelId) return null
  let found = null
  const walk = (node) => {
    if (!node || found) return
    if (node.type === 'leaf') {
      if (node.id !== exceptPaneId && node.view === 'session' && node.sessionPanelId === sessionPanelId) {
        found = node
      }
      return
    }
    ;(node.children || []).forEach(walk)
  }
  walk(workspacePaneTree.value)
  return found
}

// Find the leaf (other than exceptPaneId) currently hosting a given view (chat / terminal).
// Host singleton: only one pane may host chat / terminal at a time; the old one must be unloaded before switching.
function findWorkspacePaneByView(view, exceptPaneId = null) {
  let found = null
  const walk = (node) => {
    if (!node || found) return
    if (node.type === 'leaf') {
      if (node.id !== exceptPaneId && node.view === view) found = node
      return
    }
    ;(node.children || []).forEach(walk)
  }
  walk(workspacePaneTree.value)
  return found
}
// Find the "file editor" pane hosting a given Agent (view==='file' and records that agent_id).
// Used for editor_open_file: when an Agent opens a file, it should reuse its existing editor panel instead of overwriting the current session area.
function findAgentFilePane(agentId) {
  if (!agentId) return null
  let found = null
  const walk = (node) => {
    if (!node || found) return
    if (node.type === 'leaf') {
      if (node.view === 'file' && node.agentId === agentId) found = node
      return
    }
    ;(node.children || []).forEach(walk)
  }
  walk(workspacePaneTree.value)
  return found
}

// Locate the target editor pane for editor_open_file, returning its paneId (also ensuring it is active and a file view):
// 1) The Agent already has a file editor panel -> reuse it (activate);
// 2) The current active pane is already a file view -> reuse it directly (record agentId);
// 3) Otherwise split the current panel and open in the new file panel (keeping the current session/chat/terminal from being overwritten).
function ensureAgentEditorPane(agentId) {
  const existing = findAgentFilePane(agentId)
  if (existing) {
    activateWorkspacePane(existing.id)
    return existing.id
  }
  // Unified to the pane tree: activePane is the currently active area (the only leaf when unsplit),
  // and only by reusing it when it really is a "file view"; otherwise (session/chat/terminal) split out a new panel to avoid overwriting.
  const isFileView = activePane.value && activePane.value.view === 'file'
  if (isFileView) {
    const cur = activePane.value
    if (cur) {
      cur.agentId = agentId
      return cur.id
    }
  }
  splitWorkspacePane(findLargestWorkspacePaneId(), computeSplitDirection())
  const newPane = activePane.value
  if (newPane) {
    newPane.view = 'file'
    newPane.agentId = agentId
    return newPane.id
  }
  return null
}

// Determine whether a pane can be treated as an "empty area" (when clicking a sidebar file, prefer creating an editor in place in the empty area):
// - view === 'empty': an explicitly empty pane;
// - view === 'file' but not bound to any file: a newly split empty file pane / a just-opened editor (title shows "Empty area").
function isPaneEmptyForFileOpen(pane) {
  if (!pane) return false
  if (pane.view === 'empty') return true
  if (pane.view === 'file') {
    return !workspaceViewPanes().has(pane.id) && !(pane.id === activePaneId.value && activeWorkspaceTabPath.value)
  }
  return false
}

// Find "an already-open editor panel": prefer the Agent's file pane, otherwise any file pane.
// Used to reuse an existing editor panel when clicking a sidebar file, rather than overwriting the current session/chat/terminal area.
function findAnyFilePane(agentId) {
  if (agentId) {
    const agentPane = findAgentFilePane(agentId)
    if (agentPane) return agentPane
  }
  let found = null
  const walk = (node) => {
    if (!node || found) return
    if (node.type === 'leaf') {
      if (node.view === 'file') found = node
      return
    }
    ;(node.children || []).forEach(walk)
  }
  walk(workspacePaneTree.value)
  return found
}

// Locate the target editor pane for "clicking a sidebar file to open" (returns paneId):
// 1) The current active area is empty -> create the editor in the current area (no split);
// 2) Otherwise find an already-open editor panel -> reuse it (without disturbing the current active area);
// 3) Otherwise split the current area and create the editor in the new pane.
// Unified to the pane tree: when unsplit, activePane is the only leaf, and the logic is the same as when split.
function ensureEditorPaneForFileOpen(agentId) {
  const active = activePane.value
  // 1. The current active area is empty -> create the editor in the current area
  if (isPaneEmptyForFileOpen(active)) {
    active.view = 'file'
    if (agentId) active.agentId = agentId
    activateWorkspacePane(active.id)
    return active.id
  }
  // 2. Find an already-open editor panel -> reuse it
  const filePane = findAnyFilePane(agentId)
  if (filePane) {
    activateWorkspacePane(filePane.id)
    return filePane.id
  }
  // 3. Split the current area to create the editor
  splitWorkspacePane(findLargestWorkspacePaneId(), computeSplitDirection())
  const newPane = activePane.value
  if (newPane) {
    newPane.view = 'file'
    if (agentId) newPane.agentId = agentId
    return newPane.id
  }
  return null
}
// workspaceMainView derives from leaf.view, so just rewrite the only leaf's view directly.
function setMainViewOnLeaf(view, sessionPanelId = null) {
  const root = workspacePaneTree.value
  if (root && root.type === 'leaf') {
    root.view = view
    root.sessionPanelId = view === 'session' ? sessionPanelId : null
  }
}

// Locate the target pane for "opening a panel view" (returns paneId; returns null when unsplit and opening in place):
// 1) The current active area is empty -> create directly in the current area (no split);
// 2) A pane hosting that view already exists (chat/terminal are host singletons, session is reused per panel) -> activate it;
// 3) Otherwise split the current area and host the target view in the new pane.
function ensurePaneForView(view, sessionPanelId) {
  // 2. A pane hosting that view already exists -> reuse (chat/terminal host singleton, session reused per panel)
  if (view === 'chat' || view === 'terminal') {
    const existing = findWorkspacePaneByView(view)
    if (existing) {
      activateWorkspacePane(existing.id)
      return existing.id
    }
  } else if (view === 'session' && sessionPanelId) {
    const existing = findWorkspacePaneBySessionPanelId(sessionPanelId)
    if (existing) {
      activateWorkspacePane(existing.id)
      return existing.id
    }
  } else if (view === 'diff') {
    // diff gets an independent instance per pane (no host-singleton constraint): if a diff pane already exists, reuse it to avoid overwriting the current area.
    const existing = findWorkspacePaneByView('diff')
    if (existing) {
      activateWorkspacePane(existing.id)
      return existing.id
    }
  }
  // Unified to the pane tree: when unsplit, activePane is the only leaf, and the logic is the same as when split.
  const active = activePane.value
  // 1. The current active area is empty -> create in the current area
  if (isPaneEmptyForFileOpen(active)) {
    setActivePaneViewForPane(active, view, sessionPanelId)
    activateWorkspacePane(active.id)
    return active.id
  }
  // 3. Split the current area to create it
  splitWorkspacePane(findLargestWorkspacePaneId(), computeSplitDirection())
  const newPane = activePane.value
  if (newPane) {
    setActivePaneViewForPane(newPane, view, sessionPanelId)
    return newPane.id
  }
  return null
}

// Switch the "active pane"'s view to view (file / session / chat / terminal / diff).
// Unified to the pane tree: activePane is the currently active area (the only leaf when unsplit).
function setActivePaneView(view, sessionPanelId = null) {
  const pane = activePane.value
  if (!pane) return false
  return setActivePaneViewForPane(pane, view, sessionPanelId)
}

// Switch a "given pane"'s view to view (file / session / chat / terminal / diff / empty).
// Difference from setActivePaneView: operates on the passed pane rather than the currently active pane (used to locate the pane hosting a host when "collapsing").
function setActivePaneViewForPane(pane, view, sessionPanelId = null) {
  if (!pane) return false
  if (view === 'session') {
    if (!sessionPanelId) return false
    // The same panel must not be hosted by two panes at once: clear the same panel from other panes
    const duplicated = findWorkspacePaneBySessionPanelId(sessionPanelId, pane.id)
    if (duplicated) {
      duplicated.view = 'empty'
      duplicated.sessionPanelId = null
    }
    // Requirement: Panels always land in the "active pane" (no longer redirected to other free file panes).
    // If the active pane already hosts another session panel, close the old panel so the new panel covers it.
    if (pane.view === 'session' && pane.sessionPanelId && pane.sessionPanelId !== sessionPanelId) {
      const oldPanelId = pane.sessionPanelId
      const oldPanel = panels().value.find(p => p.id === oldPanelId)
      if (oldPanel) closePanel()(oldPanelId)
    }
  } else if (view === 'chat' || view === 'terminal') {
    // Host singleton: unload the same type hosted by other panes first, then hand it to the active pane
    const duplicated = findWorkspacePaneByView(view, pane.id)
    if (duplicated) {
      duplicated.view = 'empty'
      duplicated.sessionPanelId = null
    }
  }
  // When switching away from diff, release the pane's diff instance (diff data is cleared along with it)
  if (pane.view === 'diff' && view !== 'diff') {
    disposeDiffEditorForPane()(pane.id)
    pane.diff = null
  }
  pane.view = view
  pane.sessionPanelId = view === 'session' ? sessionPanelId : null
  persistWorkspacePaneLayout()
  // After switching the active pane's content type, the Monaco container may be replaced/removed, so the view needs rebuilding
  nextTick(() => {
    remountMonacoEditor()
    layoutGitDiffEditor()()
  })
  return true
}

// Pane title: file shows the current filename (only the active pane, since the Monaco single instance only renders the active pane),
// session shows the Agent name (falls back to a generic label when not found)
function getWorkspacePaneTitle(pane) {
  if (!pane) return ''
  if (pane.view === 'empty') return 'Empty area'
  if (pane.view === 'chat') return 'Chat room'
  if (pane.view === 'terminal') return 'Terminal'
  if (pane.view === 'diff') {
    const path = pane.diff?.filePath
    return path ? `diff: ${path.split('/').pop() || path}` : 'diff'
  }
  if (pane.view === 'session') {
    const panel = panels().value.find(p => p.id === pane.sessionPanelId)
    const agent = panel ? getPanelAgent()(panel) : null
    return agent ? (agent.name || agent.agent_id) : 'Session'
  }
  // Each file pane has an independent editor instance; the title shows the file bound to that pane
  const panePath = workspaceViewPanes().get(pane.id) || (pane.id === activePaneId.value ? activeWorkspaceTabPath.value : null)
  if (panePath) return panePath.split('/').pop() || panePath
  // A file view not bound to any file yet (e.g. just-opened editor, or an empty pane from a split):
  // the content area is an empty placeholder, so the title should also show "Empty area", consistent with view='empty'.
  return 'Empty area'
}

// Pane status text (originally the status hint of the top toolbar, now shown alongside the pane title bar):
// only meaningful for file panes — take the tab status of the file bound to that pane.
function getWorkspacePaneStatus(pane) {
  if (!pane || pane.view !== 'file') return ''
  const path = workspaceViewPanes().get(pane.id) || (pane.id === activePaneId.value ? activeWorkspaceTabPath.value : null)
  if (!path) return ''
  const tab = getWorkspaceTabByPath(path)
  if (!tab) return ''
  if (tab.loading) return 'Loading...'
  if (tab.error) return tab.error
  return tab.isDirty ? 'Unsaved changes' : 'Saved'
}

// Read-only preview text of a non-active file pane: take the currently active file's content, truncated to a reasonable length,
// to avoid huge files bloating the DOM (the read-only snapshot is only meant to "let the user see the content is still there", not to be complete).
const EDITOR_PANE_PREVIEW_MAX_CHARS = 20000
function getWorkspacePreviewText() {
  const path = activeWorkspaceTabPath.value
  if (!path) return ''
  const modelData = editorModels.get(path)
  const content = modelData?.content ?? activeWorkspaceTab().value?.content ?? ''
  if (content.length <= EDITOR_PANE_PREVIEW_MAX_CHARS) return content
  return `${content.slice(0, EDITOR_PANE_PREVIEW_MAX_CHARS)}\n\n…(preview truncated; activate to view the full content)`
}

// The Panel object hosted by a pane (for session leaves)
function getPanePanel(pane) {
  if (!pane || pane.view !== 'session' || !pane.sessionPanelId) return null
  return panels().value.find(p => p.id === pane.sessionPanelId) || null
}

// Whether a pane should be considered "active" (for SessionPanel's active state)
function isPaneActive(pane) {
  return !!pane && pane.id === activePaneId.value
}
// Drag the divider to adjust the ratio (limited to 0.15~0.85)
// Note: a split node is a mutable object inside workspacePaneTree; while dragging, its ratio is changed directly,
// and Vue's deep reactivity drives re-rendering; layout() is not called during the drag and is re-run once at the end to avoid size oscillation.
let workspacePaneResizeContext = null
const workspacePaneResizing = ref(false)
function startWorkspacePaneResize(event, splitNode) {
  if (windowWidth.value <= 768) return
  const containerEl = event.currentTarget?.parentElement
  const rect = containerEl?.getBoundingClientRect?.() || { width: 0, height: 0 }
  const containerSize = splitNode.direction === 'row' ? rect.width : rect.height
  if (!containerSize) return
  workspacePaneResizeContext = {
    splitNode,
    direction: splitNode.direction,
    startPos: splitNode.direction === 'row' ? event.clientX : event.clientY,
    startRatio: splitNode.ratio,
    containerSize,
  }
  workspacePaneResizing.value = true
  document.addEventListener('mousemove', onWorkspacePaneResize)
  document.addEventListener('mouseup', stopWorkspacePaneResize)
  event.preventDefault()
  event.stopPropagation()
}
function onWorkspacePaneResize(event) {
  const ctx = workspacePaneResizeContext
  if (!ctx) return
  const current = ctx.direction === 'row' ? event.clientX : event.clientY
  const delta = current - ctx.startPos
  const nextRatio = ctx.startRatio + delta / ctx.containerSize
  ctx.splitNode.ratio = clamp(nextRatio, EDITOR_PANE_MIN_RATIO, EDITOR_PANE_MAX_RATIO)
}
function stopWorkspacePaneResize() {
  const wasActive = !!workspacePaneResizeContext
  workspacePaneResizeContext = null
  workspacePaneResizing.value = false
  document.removeEventListener('mousemove', onWorkspacePaneResize)
  document.removeEventListener('mouseup', stopWorkspacePaneResize)
  if (wasActive) {
    persistWorkspacePaneLayout()
    nextTick(() => {
      layoutMonacoEditor()
      layoutGitDiffEditor()()
    })
  }
}

// ===== Phase 4: layout persistence (localStorage) + validity checks =====
// Design: serialize workspacePaneTree to localStorage; restore after refresh.
// Any parse/validation failure falls back to the default single leaf, never a white screen from dirty data.
const EDITOR_PANE_LAYOUT_KEY = 'haijunbot_workspace_pane_layout'

// Recursively validate and normalize a node; returns null when invalid (the caller falls back accordingly).
// Note: a leaf may carry a content field (per-view content restoration info, see persistWorkspacePaneLayout);
// this field is only used to "restore content after refresh", it does not participate in rendering, and is removed
// by restoreWorkspacePaneContents after restoration completes.
function sanitizeWorkspacePaneNode(raw) {
  if (!raw || typeof raw !== 'object') return null
  if (raw.type === 'split') {
    if (raw.direction !== 'row' && raw.direction !== 'column') return null
    if (!Array.isArray(raw.children) || raw.children.length !== 2) return null
    const left = sanitizeWorkspacePaneNode(raw.children[0])
    const right = sanitizeWorkspacePaneNode(raw.children[1])
    if (!left || !right) return null
    let ratio = Number(raw.ratio)
    if (!Number.isFinite(ratio)) ratio = 0.5
    ratio = clamp(ratio, EDITOR_PANE_MIN_RATIO, EDITOR_PANE_MAX_RATIO)
    return { type: 'split', direction: raw.direction, ratio, children: [left, right] }
  }
  if (raw.type === 'leaf') {
    const validViews = ['file', 'session', 'chat', 'terminal', 'diff', 'empty']
    if (!validViews.includes(raw.view)) return null
    if (typeof raw.id !== 'string' || !raw.id) return null
    const content = raw.content && typeof raw.content === 'object' ? raw.content : null
    if (raw.view === 'diff') {
      // diff content restoration info: commitHash + filePath (minimal info, diff text is not persisted) + agentId (working-directory source).
      // Keep the diff view when valid, re-fetching on restore; when invalid (e.g. the commit has expired) degrade to an
      // empty pane rather than a file pane, to avoid misleading the user into thinking it is a file area.
      if (content && typeof content.commitHash === 'string' && content.commitHash
        && typeof content.filePath === 'string' && content.filePath) {
        const agentId = typeof content.agentId === 'string' && content.agentId ? content.agentId : null
        return { type: 'leaf', id: raw.id, view: 'diff', sessionPanelId: null, agentId, content: { commitHash: content.commitHash, filePath: content.filePath, agentId } }
      }
      return { type: 'leaf', id: raw.id, view: 'empty', sessionPanelId: null, agentId: null, content: null }
    }
    if (raw.view === 'session') {
      // Only validate the persisted agentId (used to rebuild the panel after refresh); sessionPanelId is the pre-refresh
      // panel id, which is necessarily invalid after refresh since the panels are rebuilt, so it is not validated here
      // (restoreWorkspacePaneContents rebuilds the panel by agentId and back-fills it). When there is no agentId, fall back to a file leaf (preserving legacy behavior).
      if (content && typeof content.agentId === 'string' && content.agentId) {
        return { type: 'leaf', id: raw.id, view: 'session', sessionPanelId: null, agentId: content.agentId, content: { agentId: content.agentId } }
      }
      return { type: 'leaf', id: raw.id, view: 'file', sessionPanelId: null, agentId: null, content: null }
    }
    if (raw.view === 'file') {
      // File editor pane: persist the open file list (tabs), currently bound file (activePath), and agentId (filesystem source).
      let tabs = Array.isArray(content?.tabs) ? content.tabs.filter(t => typeof t === 'string' && t) : []
      const activePath = typeof content?.activePath === 'string' && content.activePath ? content.activePath : null
      const agentId = typeof content?.agentId === 'string' && content.agentId ? content.agentId : null
      return { type: 'leaf', id: raw.id, view: 'file', sessionPanelId: null, agentId, content: { tabs, activePath, agentId } }
    }
    if (raw.view === 'terminal') {
      // Terminal pane: persist the terminal session id (matched from the session list restored by restoreTerminalSessions after refresh).
      const terminalId = typeof content?.terminalId === 'string' && content.terminalId ? content.terminalId : null
      return { type: 'leaf', id: raw.id, view: 'terminal', sessionPanelId: null, agentId: null, content: terminalId ? { terminalId } : null }
    }
    // chat / empty: no content restoration info
    return { type: 'leaf', id: raw.id, view: raw.view, sessionPanelId: null, agentId: null, content: null }
  }
  return null
}

// Validate the whole tree: it must be a valid node with leaf count >= 1; chat/terminal at most one each (host-singleton constraint)
function sanitizeWorkspacePaneTree(raw) {
  const node = sanitizeWorkspacePaneNode(raw)
  if (!node) return null
  const leafIds = new Set()
  const viewCount = { chat: 0, terminal: 0 }
  let valid = true
  const walk = (n) => {
    if (!valid || !n) return
    if (n.type === 'leaf') {
      if (leafIds.has(n.id)) { valid = false; return }
      leafIds.add(n.id)
      if (n.view === 'chat' || n.view === 'terminal') {
        viewCount[n.view] += 1
        if (viewCount[n.view] > 1) { valid = false; return }
      }
      return
    }
    ;(n.children || []).forEach(walk)
  }
  walk(node)
  if (!valid || leafIds.size < 1) return null
  return node
}

// Sync workspacePaneSeq so newly created leaf ids after restoration do not collide with existing ids
function syncWorkspacePaneSeq(tree) {
  let maxSeq = 0
  const walk = (n) => {
    if (!n) return
    if (n.type === 'leaf') {
      const m = /^pane-(\d+)$/.exec(n.id)
      if (m) maxSeq = Math.max(maxSeq, parseInt(m[1], 10))
      return
    }
    ;(n.children || []).forEach(walk)
  }
  walk(tree)
  workspacePaneSeq = Math.max(workspacePaneSeq, maxSeq)
}

// Write to localStorage (fails silently, does not affect functionality)
function persistWorkspacePaneLayout() {
  try {
    const tree = workspacePaneTree.value
    // Do not write when unsplit (equivalent to clearing), to avoid persisting the default state as the illusion of "split"
    if (!tree || workspacePaneCount.value <= 1) {
      localStorage.removeItem(EDITOR_PANE_LAYOUT_KEY)
      return
    }
    // version 2: besides the layout, each leaf additionally carries content (per-view content restoration info)
    const payload = { version: 2, activePaneId: activePaneId.value, tree: serializeWorkspacePaneTree(tree) }
    localStorage.setItem(EDITOR_PANE_LAYOUT_KEY, JSON.stringify(payload))
  } catch (e) {
    // Ignore: silently degrade when localStorage is unavailable (private mode / quota full)
  }
}

// Serialize the pane tree: attach a content field to each leaf (content restoration info) for restoration after refresh
function serializeWorkspacePaneTree(tree) {
  const clone = (node) => {
    if (!node) return node
    if (node.type === 'split') {
      return { type: 'split', direction: node.direction, ratio: node.ratio, children: node.children.map(clone) }
    }
    // leaf: extract content restoration info per view (do not serialize runtime state like diff text or Monaco instances)
    let content = null
    if (node.view === 'session') {
      content = { agentId: node.agentId || null }
    } else if (node.view === 'file') {
      content = {
        tabs: workspacePaneTabs().get(node.id) || [],
        activePath: workspaceViewPanes().get(node.id) || null,
        agentId: node.agentId || null,
      }
    } else if (node.view === 'diff') {
      content = node.diff ? { commitHash: node.diff.commitHash || null, filePath: node.diff.filePath || null, agentId: node.agentId || null } : null
    } else if (node.view === 'terminal') {
      content = { terminalId: activeTerminalId().value || null }
    }
    return { type: 'leaf', id: node.id, view: node.view, sessionPanelId: node.sessionPanelId, agentId: node.agentId, content }
  }
  return clone(tree)
}

// Restore from localStorage (called during setup); falls back to the default single leaf on failure
function restoreWorkspacePaneLayout() {
  let raw = null
  try {
    raw = localStorage.getItem(EDITOR_PANE_LAYOUT_KEY)
  } catch (e) {
    return
  }
  if (!raw) return
  let parsed = null
  try {
    parsed = JSON.parse(raw)
  } catch (e) {
    try { localStorage.removeItem(EDITOR_PANE_LAYOUT_KEY) } catch (e2) {}
    return
  }
  const tree = sanitizeWorkspacePaneTree(parsed && parsed.tree)
  if (!tree) {
    try { localStorage.removeItem(EDITOR_PANE_LAYOUT_KEY) } catch (e) {}
    return
  }
  workspacePaneTree.value = tree
  syncWorkspacePaneSeq(tree)
  const wantActive = parsed && parsed.activePaneId
  activePaneId.value = findWorkspacePaneById(tree, wantActive)
    ? wantActive
    : findFirstWorkspacePaneId(tree)
}

// ===== Phase B: restore each pane's content (session panels / files / diffs / terminals) =====
// Called after agentList is first ready (socket connected, agentList loaded, restoreTerminalSessions already run).
// Idempotent: runs only once; leaves that cannot be restored degrade to empty panes (consistent with Issue #82 supplementary notes).
let workspacePaneContentsRestored = false
async function restoreWorkspacePaneContents() {
  if (workspacePaneContentsRestored) return
  // Do not restore until the Agent list is ready: agentList is empty at that point, session panes would be wrongly
  // degraded to empty panes for "Agent not found", and the restoration info (leaf.content) would be cleared all at once
  // and workspacePaneContentsRestored set, with no retry afterwards. Hence the early return here — it will be triggered
  // again once fetchAgentList has the Agents (without consuming the one-shot flag).
  if (agentList().value.length === 0) return
  const tree = workspacePaneTree.value
  if (!tree) return
  workspacePaneContentsRestored = true
  const leaves = []
  const walk = (n) => {
    if (!n) return
    if (n.type === 'leaf') leaves.push(n)
    else (n.children || []).forEach(walk)
  }
  walk(tree)
  for (const leaf of leaves) {
    const content = leaf.content
    if (!content) continue
    try {
      if (leaf.view === 'session' && content.agentId) {
        const agent = agentList().value.find(a => a.agent_id === content.agentId)
        if (!agent) {
          // The Agent no longer exists: degrade to an empty pane
          leaf.view = 'empty'
          leaf.sessionPanelId = null
          leaf.agentId = null
        } else {
          // Reuse an existing Panel (only one Panel per Agent), otherwise create one
          let panel = panels().value.find(p => p.agentId === agent.agent_id)
          if (!panel) {
            panel = { id: `panel-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, agentId: agent.agent_id }
            panels().value.push(panel)
          }
          leaf.sessionPanelId = panel.id
          leaf.agentId = agent.agent_id
          activePanelId().value = panel.id
          workspaceSessionPanelId().value = panel.id
          await switchAgent()(agent)
        }
      } else if (leaf.view === 'file') {
        const tabs = content.tabs || []
        // Open them one by one into this pane (first activate the target pane; openWorkspaceFile registers into the active pane's tab list)
        for (const path of tabs) {
          activateWorkspacePane(leaf.id)
          await openWorkspaceFile(path, content.agentId)
        }
        // Restore the currently bound file (activate activePath when it is in tabs)
        if (content.activePath && tabs.includes(content.activePath)) {
          activateWorkspacePane(leaf.id)
          activateWorkspaceTab(content.activePath)
        }
      } else if (leaf.view === 'diff' && content.commitHash && content.filePath) {
        // Temporarily switch the Git target to that Agent (ensuring getGitWorkingDir hits its working directory), and restore afterwards
        const savedGitAgentId = gitAgentId().value
        if (content.agentId) gitAgentId().value = content.agentId
        try {
          await loadDiffForPane()(leaf.id, content.commitHash, content.filePath)
        } finally {
          gitAgentId().value = savedGitAgentId
        }
        const pane = findWorkspacePaneById(workspacePaneTree.value, leaf.id)
        if (pane && pane.view === 'diff' && pane.diff && pane.diff.error) {
          // diff fetch failed (e.g. commit has expired): degrade to an empty pane
          pane.view = 'empty'
          pane.diff = null
          pane.agentId = null
        }
      } else if (leaf.view === 'terminal' && content.terminalId) {
        // Terminal sessions are restored by restoreTerminalSessions; here we only match and activate
        let session = terminalSessions().value.find(t => t.terminal_id === content.terminalId)
        if (!session) {
          // Fallback: try fetching live terminals once more (restoreTerminalSessions may not have finished)
          await restoreTerminalSessions()()
          session = terminalSessions().value.find(t => t.terminal_id === content.terminalId)
        }
        if (session) {
          activeTerminalId().value = content.terminalId
        } else {
          // The terminal session no longer exists: degrade to an empty pane
          leaf.view = 'empty'
          leaf.agentId = null
        }
      }
    } catch (e) {
      console.warn('[workspace-pane] restore content failed for pane', leaf.id, e)
      // Restoration failed: degrade to an empty pane to avoid leaving a half-initialized state
      leaf.view = 'empty'
      leaf.sessionPanelId = null
      leaf.agentId = null
      leaf.diff = null
    } finally {
      // Content restoration info is consumed as soon as it is used, to avoid it lingering on the runtime leaf
      leaf.content = null
    }
  }
  // Ensure the current Agent matches the active pane (when the active pane is a session)
  const activeLeaf = findWorkspacePaneById(workspacePaneTree.value, activePaneId.value)
  if (activeLeaf && activeLeaf.view === 'session' && activeLeaf.sessionPanelId) {
    const panel = panels().value.find(p => p.id === activeLeaf.sessionPanelId)
    const agent = panel?.agentId ? agentList().value.find(a => a.agent_id === panel.agentId) : null
    if (agent) await switchAgent()(agent)
  }
  // Write back the normalized layout (content already cleared)
  persistWorkspacePaneLayout()
}

// After every DOM commit (active pane / split-tree change / tab change), backfill instances again:
// during patching Vue may clear Monaco DOM it "does not recognize" from the container, detaching the instance DOM from the document;
// here we detect and rebuild in the post-flush phase, ensuring every file pane always has a visible editor.
// Note: the immediate first trigger happens during the synchronous setup phase, when useWorkspaceEditor has not run yet,
// and scheduleWorkspaceLayout's getter evaluation would hit TDZ (Cannot access before initialization);
// so the first trigger is deferred via nextTick until setup finishes (useWorkspaceEditor has run), then scheduled.
let firstWorkspaceLayoutRun = true
watch(
  [activePaneId, workspacePaneTree, () => workspaceTabs.value.length, activeWorkspaceTabPath],
  () => {
    if (firstWorkspaceLayoutRun) {
      firstWorkspaceLayoutRun = false
      nextTick(() => scheduleWorkspaceLayout())
    } else {
      scheduleWorkspaceLayout()
    }
  },
  { flush: 'post', immediate: true },
)

  return {
    EDITOR_PANEL_MIN_WIDTH,
    EDITOR_PANEL_MIN_HEIGHT,
    workspaceResizeDirections,
    PANEL_DRAG_ACTIVATION_DISTANCE,
    isWorkspaceMaximized,
    workspacePanelRectBeforeMaximize,
    saveWorkspacePanelRect,
    workspacePanelRect,
    workspacePanelInteraction,
    workspacePanelRef,
    splitWorkspaceContainerRefs,
    setSplitWorkspaceContainerRef,
    editorContainerRef,
    workspaceSessions,
    activeWorkspaceSessionId,
    workspaceTabs,
    activeWorkspaceTabPath,
    activeWorkspaceSession,
    virtualWorkspaceSessions,
    editorModels,
    workspaceFileHeartbeatTimer,
    isWorkspaceEditable,
    EDITOR_FILE_HEARTBEAT_INTERVAL,
    globalSearchQuery,
    globalSearchFileGlob,
    globalSearchCaseSensitive,
    globalSearchWholeWord,
    globalSearchLoading,
    globalSearchError,
    globalSearchResults,
    globalSearchTotalFiles,
    globalSearchTotalMatches,
    globalSearchExecuted,
    globalSearchMode,
    fileSearchResults,
    showWorkspaceSidebar,
    workspaceSidebarView,
    workspaceMainView,
    workspacePaneTree,
    activePaneId,
    maximizedPaneId,
    workspacePaneCount,
    activePane,
    findWorkspacePaneById,
    activateWorkspacePane,
    toggleMaximizeWorkspacePane,
    moveActivePaneInDirection,
    splitWorkspacePane,
    closeWorkspacePane,
    collapseWorkspacePanes,
    findWorkspacePaneBySessionPanelId,
    findWorkspacePaneByView,
    ensureAgentEditorPane,
    ensureEditorPaneForFileOpen,
    setMainViewOnLeaf,
    ensurePaneForView,
    setActivePaneView,
    setActivePaneViewForPane,
    getWorkspacePaneTitle,
    getWorkspacePaneStatus,
    getPanePanel,
    isPaneActive,
    startWorkspacePaneResize,
    persistWorkspacePaneLayout,
    restoreWorkspacePaneLayout,
    restoreWorkspacePaneContents,
    pluginExtensions,
    pluginAdminTabs,
    pluginSidebarViews,
    pluginToolPanels,
    pluginSidebarTitle,
    pluginToolPanelTitle,
    WORKSPACE_SIDEBAR_TITLES,
    workspaceSidebarTitle,
    loadPluginExtensionsForUi,
    resolvePluginExtensionComponent,
    isPluginSidebarView,
    isPluginToolView,
    pluginSidebarCompCache,
    activePluginSidebarComp,
    activePluginToolPanelComp,
  }
}
