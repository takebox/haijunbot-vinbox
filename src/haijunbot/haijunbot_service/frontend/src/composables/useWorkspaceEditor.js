// Workspace editor / file operations composable function.
//
// Extracted from App.vue <script setup> (Issue #118 Step 10 PR-3, originally lines 3180-5424),
// Keeping the behavior completely identical:
// - Editor panel: workspacePanelStyle / workspacePanelRect / workspacePanelInteraction /
//   startWorkspacePanelMove / startWorkspacePanelResize / toggleWorkspaceMaximize
// - Monaco editor: editorViews / workspaceViewPanes / diffEditorViews / workspacePaneTabs /
//   scheduleWorkspaceLayout / layoutMonacoEditor / remountMonacoEditor / activateWorkspaceTab /
//   openWorkspaceFile / saveWorkspaceTab / closeWorkspaceTab / tabContextMenu
// - Global search: runGlobalSearch / fetchGlobalSearchResults / fetchFileSearchResults
// - Virtual directory sessions: openWorkspaceDir / removeWorkspaceDir / restoreVirtualWorkspaceDirs
// - LSP: activateLspForModel / ensureModelForUri / releaseLspBinding
//
// Dependency injection (caller passes them in setup; they must be defined before calling):
// - Direct pass (Definition at this composable call site's Prev/Before): fetchWithAuth / getGatewayAddress / getHttpProtocol /
//   buildNodeHttpUrl / getWebSocketProtocol / buildWebSocketProtocols / getLanguageFromFilename /
//   getLanguageExtension / showToast / showConfirm / pushOverlayState / getNodeDisplayName /
//   getCurrentAgentOrNull / isStoppedAgent / refreshManageCapabilities / refreshManageTimers /
//   windowWidth / activeWindow / showWorkspacePanel / showTerminalPanel / showChatPanel /
//   workspaceSidebarWidth / workspaceSidebarResizeState / currentAgent / socket /
//   workspaceHostsChat / workspaceHostsTerminal / editorShortcutLocked /
//   effectiveGlobalSearchAgentId / normalizeWorkspaceSidebarWidth / saveWorkspaceSidebarWidth /
//   ACTIVE_Z_INDEX / BASE_Z_INDEX / manageInstalledScripts / manageGatewayScripts / getDefinition /
//   loadLspServers / getServerByLanguage / getServerByPath / ensureClient / disposeClient
// - Direct pass (useWorkspacePane Back, Definition at this call site's Prev/Before): activePaneId / workspaceSessions /
//   activeWorkspaceSessionId / workspaceTabs / activeWorkspaceTabPath / activeWorkspaceSession /
//   virtualWorkspaceSessions / editorModels / workspaceFileHeartbeatTimer / isWorkspaceEditable /
//   EDITOR_FILE_HEARTBEAT_INTERVAL / globalSearch* / fileSearchResults / showWorkspaceSidebar /
//   workspaceSidebarView / workspaceMainView / workspacePaneCount / workspacePanelInteraction /
//   workspacePanelRect / workspacePanelRectBeforeMaximize / isWorkspaceMaximized /
//   saveWorkspacePanelRect / splitWorkspaceContainerRefs / editorContainerRef /
//   EDITOR_PANEL_MIN_WIDTH / EDITOR_PANEL_MIN_HEIGHT / PANEL_DRAG_ACTIVATION_DISTANCE /
//   collapseWorkspacePanes / findWorkspacePaneByView / ensureEditorPaneForFileOpen /
//   ensurePaneForView / setMainViewOnLeaf / setActivePaneView / setActivePaneViewForPane
// - getter inject (Definition at call site's Next/After, Internal pass xxx() second compute Value): closePanel / agentList / panels /
//   workspaceSessionPanelId; from useFileTree: fileTreeState / initFileTree /
//   getVisibleFileTreeNodes / expandedAgents / fileTreeExpanded / fileTreeLoading /
//   fileTreeSelectedAgentId / fileTreeSelectedPath / selectedAgentId / revealTabInFileTree;
//   from useGitView: gitLogLoading / refreshGitView / layoutGitDiffEditor / renderDiffForPane /
//   scheduleDiffLayout; from useTopology: topologyDaemonSessions / topologyExtensionSessions
import { computed, nextTick, reactive, ref, triggerRef } from 'vue'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.main.js'

export function useWorkspaceEditor({
  // Direct pass-in (defined before)
  fetchWithAuth,
  getGatewayAddress,
  getHttpProtocol,
  buildNodeHttpUrl,
  getWebSocketProtocol,
  buildWebSocketProtocols,
  getLanguageFromFilename,
  getLanguageExtension,
  showToast: showToastGetter,
  showConfirm: showConfirmGetter,
  pushOverlayState: pushOverlayStateGetter,
  getNodeDisplayName: getNodeDisplayNameGetter,
  getCurrentAgentOrNull: getCurrentAgentOrNullGetter,
  isStoppedAgent: isStoppedAgentGetter,
  closePanel: closePanelGetter,
  refreshManageCapabilities,
  refreshManageTimers,
  windowWidth,
  activeWindow,
  showWorkspacePanel,
  showTerminalPanel,
  showChatPanel,
  workspaceSidebarWidth,
  workspaceSidebarResizeState,
  agentList: agentListGetter,
  currentAgent: currentAgentGetter,
  socket,
  panels: panelsGetter,
  workspaceHostsChat: workspaceHostsChatGetter,
  workspaceHostsTerminal: workspaceHostsTerminalGetter,
  workspaceSessionPanelId: workspaceSessionPanelIdGetter,
  editorShortcutLocked: editorShortcutLockedGetter,
  effectiveGlobalSearchAgentId: effectiveGlobalSearchAgentIdGetter,
  normalizeWorkspaceSidebarWidth,
  saveWorkspaceSidebarWidth,
  ACTIVE_Z_INDEX,
  BASE_Z_INDEX,
  manageInstalledScripts,
  manageGatewayScripts,
  getDefinition,
  loadLspServers,
  getServerByLanguage,
  getServerByPath,
  ensureClient,
  disposeClient,
  // Direct pass-in (returned by useWorkspacePane, defined before)
  activePaneId,
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
  workspacePaneCount,
  workspacePanelInteraction,
  workspacePanelRect,
  workspacePanelRectBeforeMaximize,
  isWorkspaceMaximized,
  saveWorkspacePanelRect,
  splitWorkspaceContainerRefs,
  editorContainerRef,
  EDITOR_PANEL_MIN_WIDTH,
  EDITOR_PANEL_MIN_HEIGHT,
  PANEL_DRAG_ACTIVATION_DISTANCE,
  collapseWorkspacePanes,
  findWorkspacePaneByView,
  ensureEditorPaneForFileOpen,
  ensurePaneForView,
  setMainViewOnLeaf,
  setActivePaneView,
  setActivePaneViewForPane,
  // Getter injection (defined after)
  fileTreeState: fileTreeStateGetter,
  initFileTree: initFileTreeGetter,
  getVisibleFileTreeNodes: getVisibleFileTreeNodesGetter,
  expandedAgents: expandedAgentsGetter,
  fileTreeExpanded: fileTreeExpandedGetter,
  fileTreeLoading: fileTreeLoadingGetter,
  fileTreeSelectedAgentId: fileTreeSelectedAgentIdGetter,
  fileTreeSelectedPath: fileTreeSelectedPathGetter,
  selectedAgentId: selectedAgentIdGetter,
  revealTabInFileTree: revealTabInFileTreeGetter,
  gitLogLoading: gitLogLoadingGetter,
  refreshGitView: refreshGitViewGetter,
  layoutGitDiffEditor: layoutGitDiffEditorGetter,
  renderDiffForPane: renderDiffForPaneGetter,
  scheduleDiffLayout: scheduleDiffLayoutGetter,
  topologyDaemonSessions: topologyDaemonSessionsGetter,
  topologyExtensionSessions: topologyExtensionSessionsGetter,
  getWorkspaceTargetNodeId: getWorkspaceTargetNodeIdGetter,
}) {
  // —— Safe wrappers for getter-injected dependencies (re-evaluated via xxx() internally) ——
  const fileTreeState = () => fileTreeStateGetter()
  const initFileTree = (...args) => { const fn = initFileTreeGetter(); if (fn) return fn(...args) }
  const getVisibleFileTreeNodes = (...args) => { const fn = getVisibleFileTreeNodesGetter(); if (fn) return fn(...args) }
  const expandedAgents = () => expandedAgentsGetter()
  const fileTreeExpanded = () => fileTreeExpandedGetter()
  const fileTreeLoading = () => fileTreeLoadingGetter()
  const fileTreeSelectedAgentId = () => fileTreeSelectedAgentIdGetter()
  const fileTreeSelectedPath = () => fileTreeSelectedPathGetter()
  const selectedAgentId = () => selectedAgentIdGetter()
  const revealTabInFileTree = (...args) => { const fn = revealTabInFileTreeGetter(); if (fn) return fn(...args) }
  const gitLogLoading = () => gitLogLoadingGetter()
  const refreshGitView = (...args) => { const fn = refreshGitViewGetter(); if (fn) return fn(...args) }
  const layoutGitDiffEditor = (...args) => { const fn = layoutGitDiffEditorGetter(); if (fn) return fn(...args) }
  const renderDiffForPane = (...args) => { const fn = renderDiffForPaneGetter(); if (fn) return fn(...args) }
  const scheduleDiffLayout = (...args) => { const fn = scheduleDiffLayoutGetter(); if (fn) return fn(...args) }
  const topologyDaemonSessions = () => topologyDaemonSessionsGetter()
  const topologyExtensionSessions = () => topologyExtensionSessionsGetter()
  const getWorkspaceTargetNodeId = (...args) => { const fn = getWorkspaceTargetNodeIdGetter(); if (fn) return fn(...args) }
  // Functions defined after call point (passed as getters from App.vue, evaluated internally)
  const showToast = (...args) => { const fn = showToastGetter(); if (fn) return fn(...args) }
  const showConfirm = (...args) => { const fn = showConfirmGetter(); if (fn) return fn(...args) }
  const pushOverlayState = (...args) => { const fn = pushOverlayStateGetter(); if (fn) return fn(...args) }
  const getNodeDisplayName = (...args) => { const fn = getNodeDisplayNameGetter(); if (fn) return fn(...args) }
  const getCurrentAgentOrNull = (...args) => { const fn = getCurrentAgentOrNullGetter(); if (fn) return fn(...args) }
  const isStoppedAgent = (...args) => { const fn = isStoppedAgentGetter(); if (fn) return fn(...args) }
  // refs/computed defined after call point (passed as getters from App.vue, evaluated internally)
  const currentAgent = () => currentAgentGetter()
  const workspaceHostsChat = () => workspaceHostsChatGetter()
  const workspaceHostsTerminal = () => workspaceHostsTerminalGetter()
  const editorShortcutLocked = () => editorShortcutLockedGetter()
  const effectiveGlobalSearchAgentId = () => effectiveGlobalSearchAgentIdGetter()

const workspacePanelStyle = computed(() => {
  if (windowWidth.value <= 768) {
    return {
      top: '0',
      left: '0',
      width: '100vw',
      height: 'var(--app-height, 100vh)',
      zIndex: 2000,
    }
  }

  return {
    top: `${workspacePanelRect.value.top}px`,
    left: `${workspacePanelRect.value.left}px`,
    width: `${workspacePanelRect.value.width}px`,
    height: `${workspacePanelRect.value.height}px`,
    zIndex: activeWindow.value === 'workspace' ? ACTIVE_Z_INDEX : BASE_Z_INDEX,
  }
})

const activeWorkspaceTab = computed(() => {
  return workspaceTabs.value.find(tab => tab.path === activeWorkspaceTabPath.value) || null
})

function clamp(value, min, max) {
  if (max < min) return min
  return Math.min(Math.max(value, min), max)
}

function startWorkspaceSidebarResize(event) {
  if (windowWidth.value <= 768 || !showWorkspaceSidebar.value) return

  workspaceSidebarResizeState.value = {
    active: true,
    startX: event.clientX,
    startWidth: workspaceSidebarWidth.value,
  }

  document.addEventListener('mousemove', onWorkspaceSidebarResize)
  document.addEventListener('mouseup', stopWorkspaceSidebarResize)
  event.preventDefault()
  event.stopPropagation()
}

function onWorkspaceSidebarResize(event) {
  if (!workspaceSidebarResizeState.value.active) return

  const deltaX = event.clientX - workspaceSidebarResizeState.value.startX
  const nextWidth = workspaceSidebarResizeState.value.startWidth + deltaX
  workspaceSidebarWidth.value = normalizeWorkspaceSidebarWidth(nextWidth)
}

function stopWorkspaceSidebarResize() {
  if (!workspaceSidebarResizeState.value.active) {
    document.removeEventListener('mousemove', onWorkspaceSidebarResize)
    document.removeEventListener('mouseup', stopWorkspaceSidebarResize)
    return
  }

  workspaceSidebarResizeState.value = {
    active: false,
    startX: 0,
    startWidth: workspaceSidebarWidth.value,
  }

  document.removeEventListener('mousemove', onWorkspaceSidebarResize)
  document.removeEventListener('mouseup', stopWorkspaceSidebarResize)
  saveWorkspaceSidebarWidth()
}

// Set focus window
function focusWindow(windowType) {
  activeWindow.value = windowType
}

// Maximize/restore the editor window
function toggleWorkspaceMaximize() {
  if (isWorkspaceMaximized.value) {
    // Restore
    if (workspacePanelRectBeforeMaximize.value) {
      workspacePanelRect.value = { ...workspacePanelRectBeforeMaximize.value }
    }
    isWorkspaceMaximized.value = false
  } else {
    // Maximize
    workspacePanelRectBeforeMaximize.value = { ...workspacePanelRect.value }
    workspacePanelRect.value = {
      top: 0,
      left: 0,
      width: window.innerWidth,
      height: window.innerHeight,
    }
    isWorkspaceMaximized.value = true
  }
  nextTick(() => {
    layoutMonacoEditor()
  })
}


function getWorkspacePanelBounds() {
  const HEADER_HEIGHT = 32 // Header height
  const MIN_VISIBLE_WIDTH = 100 // Keep at least 100px of the panel visible
  return {
    minTop: 0, // Header cannot be dragged outside the top of the window
    minLeft: 0, // Header cannot be dragged outside the left of the window
    maxLeft: window.innerWidth - MIN_VISIBLE_WIDTH, // Keep at least 100px of the panel visible
    maxTop: window.innerHeight - HEADER_HEIGHT, // Keep the header height visible
    maxWidth: window.innerWidth,
    maxHeight: window.innerHeight,
  }
}

function ensureWorkspacePanelInViewport() {
  const HEADER_HEIGHT = 32 // Header height
  const MIN_VISIBLE_WIDTH = 100 // Keep at least 100px of the panel visible
  const maxWidth = Math.max(window.innerWidth, EDITOR_PANEL_MIN_WIDTH)
  const maxHeight = Math.max(window.innerHeight, EDITOR_PANEL_MIN_HEIGHT)

  workspacePanelRect.value.width = clamp(workspacePanelRect.value.width, EDITOR_PANEL_MIN_WIDTH, maxWidth)
  workspacePanelRect.value.height = clamp(workspacePanelRect.value.height, EDITOR_PANEL_MIN_HEIGHT, maxHeight)

  // Header cannot be moved out of the window
  workspacePanelRect.value.left = clamp(
    workspacePanelRect.value.left,
    0, // Header cannot be dragged outside the left of the window
    window.innerWidth - MIN_VISIBLE_WIDTH // Keep at least 100px of the panel visible
  )
  workspacePanelRect.value.top = clamp(
    workspacePanelRect.value.top,
    0, // Header cannot be dragged outside the top of the window
    window.innerHeight - HEADER_HEIGHT // Keep the header height visible
  )
}

function startWorkspacePanelMove(event) {
  if (windowWidth.value <= 768) return
  if (event.target.closest('.workspace-panel-actions')) return

  focusWindow('workspace')

  workspacePanelInteraction.value = {
    active: false,
    mode: 'move',
    direction: null,
    startX: event.clientX,
    startY: event.clientY,
    startTop: workspacePanelRect.value.top,
    startLeft: workspacePanelRect.value.left,
    startWidth: workspacePanelRect.value.width,
    startHeight: workspacePanelRect.value.height,
  }

  document.addEventListener('mousemove', onWorkspacePanelPointerMove)
  document.addEventListener('mouseup', stopWorkspacePanelInteraction)
}

function startWorkspacePanelResize(event, direction) {
  if (windowWidth.value <= 768) return

  workspacePanelInteraction.value = {
    active: true,
    mode: 'resize',
    direction,
    startX: event.clientX,
    startY: event.clientY,
    startTop: workspacePanelRect.value.top,
    startLeft: workspacePanelRect.value.left,
    startWidth: workspacePanelRect.value.width,
    startHeight: workspacePanelRect.value.height,
  }

  document.addEventListener('mousemove', onWorkspacePanelPointerMove)
  document.addEventListener('mouseup', stopWorkspacePanelInteraction)
  event.preventDefault()
  event.stopPropagation()
}

function onWorkspacePanelPointerMove(event) {
  const deltaX = event.clientX - workspacePanelInteraction.value.startX
  const deltaY = event.clientY - workspacePanelInteraction.value.startY

  if (workspacePanelInteraction.value.mode === 'move' && !workspacePanelInteraction.value.active) {
    const dragDistance = Math.hypot(deltaX, deltaY)
    if (dragDistance < PANEL_DRAG_ACTIVATION_DISTANCE) {
      return
    }

    workspacePanelInteraction.value = {
      ...workspacePanelInteraction.value,
      active: true,
    }
    event.preventDefault()
  }

  if (!workspacePanelInteraction.value.active) return

  if (workspacePanelInteraction.value.mode === 'move') {
    const bounds = getWorkspacePanelBounds()
    workspacePanelRect.value.left = clamp(workspacePanelInteraction.value.startLeft + deltaX, bounds.minLeft, bounds.maxLeft)
    workspacePanelRect.value.top = clamp(workspacePanelInteraction.value.startTop + deltaY, bounds.minTop, bounds.maxTop)
    return
  }

  const direction = workspacePanelInteraction.value.direction || ''
  const startLeft = workspacePanelInteraction.value.startLeft
  const startTop = workspacePanelInteraction.value.startTop
  const startWidth = workspacePanelInteraction.value.startWidth
  const startHeight = workspacePanelInteraction.value.startHeight

  let nextLeft = startLeft
  let nextTop = startTop
  let nextWidth = startWidth
  let nextHeight = startHeight

  if (direction.includes('e')) {
    nextWidth = clamp(startWidth + deltaX, EDITOR_PANEL_MIN_WIDTH, Math.max(window.innerWidth - startLeft, EDITOR_PANEL_MIN_WIDTH))
  }

  if (direction.includes('s')) {
    nextHeight = clamp(startHeight + deltaY, EDITOR_PANEL_MIN_HEIGHT, Math.max(window.innerHeight - startTop, EDITOR_PANEL_MIN_HEIGHT))
  }

  if (direction.includes('w')) {
    const desiredLeft = clamp(startLeft + deltaX, 0, startLeft + startWidth - EDITOR_PANEL_MIN_WIDTH)
    nextLeft = desiredLeft
    nextWidth = startWidth - (desiredLeft - startLeft)
  }

  if (direction.includes('n')) {
    const desiredTop = clamp(startTop + deltaY, 0, startTop + startHeight - EDITOR_PANEL_MIN_HEIGHT)
    nextTop = desiredTop
    nextHeight = startHeight - (desiredTop - startTop)
  }

  if (nextLeft + nextWidth > window.innerWidth) {
    nextWidth = Math.max(EDITOR_PANEL_MIN_WIDTH, window.innerWidth - nextLeft)
  }

  if (nextTop + nextHeight > window.innerHeight) {
    nextHeight = Math.max(EDITOR_PANEL_MIN_HEIGHT, window.innerHeight - nextTop)
  }

  workspacePanelRect.value.left = clamp(nextLeft, 0, Math.max(window.innerWidth - nextWidth, 0))
  workspacePanelRect.value.top = clamp(nextTop, 0, Math.max(window.innerHeight - nextHeight, 0))
  workspacePanelRect.value.width = clamp(nextWidth, EDITOR_PANEL_MIN_WIDTH, Math.max(window.innerWidth - workspacePanelRect.value.left, EDITOR_PANEL_MIN_WIDTH))
  workspacePanelRect.value.height = clamp(nextHeight, EDITOR_PANEL_MIN_HEIGHT, Math.max(window.innerHeight - workspacePanelRect.value.top, EDITOR_PANEL_MIN_HEIGHT))
}

function stopWorkspacePanelInteraction() {
  workspacePanelInteraction.value = {
    active: false,
    mode: null,
    direction: null,
    startX: 0,
    startY: 0,
    startTop: 0,
    startLeft: 0,
    startWidth: 0,
    startHeight: 0,
  }

  document.removeEventListener('mousemove', onWorkspacePanelPointerMove)
  document.removeEventListener('mouseup', stopWorkspacePanelInteraction)
  saveWorkspacePanelRect()
}

function getWorkspaceTabByPath(path) {
  return workspaceTabs.value.find(tab => tab.path === path) || null
}

function syncWorkspaceTabDirtyState(path, value) {
  const tab = getWorkspaceTabByPath(path)
  if (tab) {
    tab.isDirty = value
  }
}

function updateWorkspaceTabFileStat(tab, fileStat = {}) {
  if (!tab) return
  tab.mtimeNs = fileStat.mtime_ns ?? null
  tab.fileSize = fileStat.size ?? null
}

function markWorkspaceTabExternalModified(path, value) {
  const tab = getWorkspaceTabByPath(path)
  if (tab) {
    tab.externalModified = value
  }
}

// ===== Blue-themed Monaco theme (corresponds to original CodeMirror blueDark) =====
const EDITOR_FONT_FAMILY = "'Consolas', 'Microsoft YaHei', monospace"

monaco.editor.defineTheme('blueDark', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '5a7a9a' },
    { token: 'keyword', foreground: '7aa2f7' },
    { token: 'keyword.control', foreground: '7aa2f7' },
    { token: 'string', foreground: '9ece6a' },
    { token: 'string.escape', foreground: '56b6c2' },
    { token: 'number', foreground: 'e0af68' },
    { token: 'regexp', foreground: '56b6c2' },
    { token: 'operator', foreground: '56b6c2' },
    { token: 'delimiter', foreground: 'a8c8e8' },
    { token: 'type', foreground: 'e0af68' },
    { token: 'type.identifier', foreground: 'e0af68' },
    { token: 'namespace', foreground: 'e0af68' },
    { token: 'annotation', foreground: 'e0af68' },
    { token: 'modifier', foreground: 'e0af68' },
    { token: 'identifier', foreground: 'a8c8e8' },
    { token: 'variable', foreground: 'a8c8e8' },
    { token: 'variable.predefined', foreground: 'ff9e64' },
    { token: 'constant', foreground: 'ff9e64' },
    { token: 'tag', foreground: 'f7768e' },
    { token: 'attribute.name', foreground: 'f7768e' },
    { token: 'function', foreground: '82aaff' },
    { token: 'invalid', foreground: 'ffffff' },
    { token: 'strong', fontStyle: 'bold' },
    { token: 'emphasis', fontStyle: 'italic' },
    { token: 'strikethrough', fontStyle: 'strikethrough' },
  ],
  colors: {
    'editor.foreground': '#a8c8e8',
    'editor.background': '#0d1b2a',
    'editorCursor.foreground': '#528bff',
    'editor.lineHighlightBackground': '#1a2a3a55',
    'editor.selectionBackground': '#264f78',
    'editor.inactiveSelectionBackground': '#264f7855',
    'editor.selectionHighlightBackground': '#264f7855',
    'editor.findMatchBackground': '#72a1ff59',
    'editor.findMatchHighlightBackground': '#6199ff2f',
    'editorBracketMatch.background': '#264f78aa',
    'editorLineNumber.foreground': '#5a7a9a',
    'editorLineNumber.activeForeground': '#a8c8e8',
    'editorGutter.background': '#0d1b2a',
    'editorWidget.background': '#16263a',
    'editorWidget.border': '#1a2a3a',
    'editorSuggestWidget.background': '#16263a',
    'editorSuggestWidget.selectedBackground': '#1a2a3a',
    'editorHoverWidget.background': '#16263a',
    'editorHoverWidget.border': '#1a2a3a',
    'editorIndentGuide.background1': '#1a2a3a',
    'editorIndentGuide.activeBackground1': '#2a4a6a',
    'scrollbarSlider.background': '#1a2a3a88',
    'scrollbarSlider.hoverBackground': '#2a4a6aaa',
  },
})

// ===== Editor enhancements: VS Code-style editing capabilities =====
// Note: completion relies on Monaco's built-in language service workers (json/css/html/ts);
// other languages use lexical highlighting only; file I/O still goes through the gateway remote API.
const EDITOR_TAB_SIZE = 4

// ===== Free-splitting: one independent Monaco instance per file pane =====
// Design points (to avoid multiple instances triggering each other's layout causing main-thread stalls):
// 1) Instance creation/destruction only happens when the pane container set actually changes (ensureMonacoEditor diffs the set);
// 2) Container size changes are handled by Monaco's automaticLayout(ResizeObserver); no extra ResizeObserver attached here,
//    nor does the resize callback call layout() on each instance, avoiding the "layout → size change → layout" loop;
//    
// 3) All explicit layout() calls go through scheduleWorkspaceLayout() which coalesces via rAF, executing only once per frame.
const editorViews = new Map()  // paneId -> monaco editor instance
const workspaceViewPanes = new Map()  // paneId -> path of the file currently bound to that pane
// Free-splitting: one independent Monaco DiffEditor instance per diff pane (paneId -> { editor, originalModel, modifiedModel, oldText, newText }).
const diffEditorViews = new Map()
const diffContainerRefs = ref(new Map())  // paneId -> container element
function setDiffContainerRef(paneId, el) {
  if (!paneId) return
  if (el) {
    if (diffContainerRefs.value.get(paneId) === el) return
    diffContainerRefs.value.set(paneId, el)
  } else {
    if (!diffContainerRefs.value.has(paneId)) return
    diffContainerRefs.value.delete(paneId)
  }
  triggerRef(diffContainerRefs)
  nextTick(() => {
    renderDiffForPane(paneId)
    scheduleDiffLayout()
  })
}
// Parse the "currently mounted" container from the document by data-diff-pane-id (ref elements may be in a transient render state)
function resolveDiffContainer(paneId) {
  const live = document.querySelector(`.workspace-diff-monaco[data-diff-pane-id="${paneId}"]`)
  if (live && live.isConnected) return live
  const refEl = diffContainerRefs.value.get(paneId)
  return refEl && refEl.isConnected ? refEl : null
}
// When split, each pane has an independent tab list (paneId -> path[]). When not split, the map is empty;
// the tab bar is still driven by global workspaceTabs to ensure zero regression when not split.
// Purpose: after splitting, the two panes' tab bars do not interfere (closing a tab in one pane does not close tabs in the other).
const workspacePaneTabs = new Map()  // paneId -> path[]
const workspacePaneTabsVersion = ref(0)  // Trigger template/computed re-evaluation that depends on workspacePaneTabs

function getPaneTabs(paneId) {
  if (!paneId) return []
  const paths = workspacePaneTabs.get(paneId)
  if (!paths || paths.length === 0) return []
  const all = workspaceTabs.value
  return paths.map(p => all.find(t => t.path === p)).filter(Boolean)
}

// Whether the path is still referenced by any pane's tab list (used to determine if the model can be released when closing a tab)
function isPathReferencedByAnyPane(path) {
  for (const paths of workspacePaneTabs.values()) {
    if (paths.includes(path)) return true
  }
  return false
}

// When split, add the path to the specified pane's tab list (deduplicate)
function addPaneTab(paneId, path) {
  if (!paneId || !path) return
  const paths = workspacePaneTabs.get(paneId) || []
  if (!paths.includes(path)) {
    paths.push(path)
    workspacePaneTabs.set(paneId, paths)
    workspacePaneTabsVersion.value += 1
  }
}

// Remove the path from the specified pane's tab list
function removePaneTab(paneId, path) {
  const paths = workspacePaneTabs.get(paneId)
  if (!paths) return
  const index = paths.indexOf(path)
  if (index === -1) return
  paths.splice(index, 1)
  workspacePaneTabsVersion.value += 1
}

// Monaco instance of the currently active pane (fallback to any instance if the active pane is not a file pane)
function getActiveWorkspaceView() {
  const active = editorViews.get(activePaneId.value)
  if (active) return active
  for (const [, view] of editorViews) return view
  return null
}

function buildEditorOptions() {
  return {
    model: null,
    theme: 'blueDark',
    fontFamily: EDITOR_FONT_FAMILY,
    fontSize: 13,
    lineHeight: 20,
    tabSize: EDITOR_TAB_SIZE,
    insertSpaces: true,
    automaticLayout: true,
    minimap: { enabled: true },
    scrollBeyondLastLine: true,
    renderWhitespace: 'selection',
    smoothScrolling: true,
    cursorBlinking: 'smooth',
    mouseWheelZoom: true,
    bracketPairColorization: { enabled: true },
    guides: { bracketPairs: true, indentation: true },
    folding: true,
    showFoldingControls: 'mouseover',
    wordWrap: 'off',
    contextmenu: true,
    quickSuggestions: { other: true, comments: false, strings: true },
    suggestOnTriggerCharacters: true,
    tabCompletion: 'on',
    readOnly: !isWorkspaceEditable.value,
    readOnlyMessage: { value: 'EditDeviceCurrent for Readonly，ClickToolbarUnlockNext/AfterCan Edit' },
  }
}

// Content change → write back thisFile right should's tab (model Up recorded path, Multi pane Open same one File when natural Sync)
// ===== cursor history (Next/After back /Forward, Ctrl+Alt+←/→) =====
// VS Code navigateBack / navigateForward: records cursor "jumps", enabling back/forward navigation.
// Monaco standalone has no built-in support; we maintain a history stack ourselves.
// Elements: { path, line, column }; cursorHistoryIndex is the current pointer.
// Consecutive cursor moves (same file, short interval) are merged into one record to avoid redundancy from arrow-key moves;
// While navigating back/forward, set cursorNavGuard to prevent the jump itself from being written into history.
const cursorHistory = []
let cursorHistoryIndex = -1
let lastCursorTime = 0
let cursorNavGuard = false
const CURSOR_MERGE_MS = 300 // Consecutive cursor moves in the same file within this window are merged into one record

// Record a cursor position. Consecutive moves (same file, short interval) merge into the current record without adding a new one.
function recordCursorLocation(path, line, column) {
  if (!path || !line) return
  if (cursorNavGuard) return // During back/forward navigation, do not write the jump result back into history
  const now = Date.now()
  const current = cursorHistory[cursorHistoryIndex]
  // Exactly the same as the current pointer → ignore
  if (current && current.path === path && current.line === line && current.column === column) return
  // Consecutive moves in the same file within a short time → update the current record (cursor refreshed with movement)
  if (current && current.path === path && now - lastCursorTime < CURSOR_MERGE_MS) {
    cursorHistory[cursorHistoryIndex] = { path, line, column }
  } else {
    // New: truncate records after the pointer, append the new position, and move the pointer forward
    cursorHistory.splice(cursorHistoryIndex + 1, cursorHistory.length - cursorHistoryIndex - 1)
    cursorHistory.push({ path, line, column })
    cursorHistoryIndex = cursorHistory.length - 1
  }
  lastCursorTime = now
}

// Navigate back to the previous cursor position (move pointer back)
async function goToPreviousCursorLocation() {
  if (cursorHistoryIndex <= 0) return
  cursorHistoryIndex -= 1
  const loc = cursorHistory[cursorHistoryIndex]
  if (loc) {
    cursorNavGuard = true
    try {
      await revealInWorkspace(loc.path, loc.line, loc.column)
    } finally {
      cursorNavGuard = false
    }
  }
}

// Navigate forward to the next cursor position (move pointer forward)
async function goToNextCursorLocation() {
  if (cursorHistoryIndex >= cursorHistory.length - 1) return
  cursorHistoryIndex += 1
  const loc = cursorHistory[cursorHistoryIndex]
  if (loc) {
    cursorNavGuard = true
    try {
      await revealInWorkspace(loc.path, loc.line, loc.column)
    } finally {
      cursorNavGuard = false
    }
  }
}

function bindWorkspaceViewEvents(view) {
  // When refocusing the editor, restore native shortcut key control (revoke ESC "detach" state):
  // When the user re-enters the editor to edit, Ctrl+A should resume editing-selection behavior.
  view.onDidFocusEditorText(() => {
    editorShortcutLocked().value = false
  })
  view.onDidChangeModelContent((e) => {
    const model = view.getModel()
    if (!model) return
    const path = model.__haijunbotPath
    if (!path) return
    const tab = getWorkspaceTabByPath(path)
    if (!tab) return
    tab.content = model.getValue()
    tab.isDirty = tab.content !== tab.originalContent
  })
  // Record cursor position (for Ctrl+Alt+←/→ back/forward navigation):
  // Consecutive moves (same file, short interval) merge into one record; jumps (across files/intervals) add a new record.
  view.onDidChangeCursorPosition((e) => {
    const model = view.getModel()
    if (!model) return
    const path = model.__haijunbotPath
    if (!path) return
    const pos = e.position
    if (pos) recordCursorLocation(path, pos.lineNumber, pos.column)
  })
  // Jump to definition: use pure F12 (Monaco intercepts it when the editor is focused so the browser devtools don't open).
  // Do not use Monaco's built-in revealDefinition—it can only jump to already-loaded models and cannot auto-open unopened target files;
  // after getting the LSP definition result, if the target file is not opened, we open it ourselves
  // via openWorkspaceFile and then position it.
  view.addAction({
    id: 'haijunbot.goToDefinition',
    label: 'Go to Definition',
    keybindings: [monaco.KeyCode.F12],
    contextMenuGroupId: 'navigation',
    contextMenuOrder: 1.5,
    run: (ed) => {
      jumpToDefinition(ed)
    },
  })
  // Back/forward cursor position (Ctrl+Alt+←/→).
  // Bound via addAction: when the editor is focused, take precedence over global Ctrl+Alt+arrow handling (switching panes/lobby).
  view.addAction({
    id: 'haijunbot.goToPreviousCursorLocation',
    label: 'Go to Previous Cursor Location',
    keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyMod.Alt | monaco.KeyCode.LeftArrow],
    run: () => {
      goToPreviousCursorLocation()
    },
  })
  view.addAction({
    id: 'haijunbot.goToNextCursorLocation',
    label: 'Go to Next Cursor Location',
    keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyMod.Alt | monaco.KeyCode.RightArrow],
    run: () => {
      goToNextCursorLocation()
    },
  })
  // Ctrl+P opens Monaco's built-in command palette (editor.action.quickCommand; default is F1).
  // The global handler yields to Monaco when the editor is focused; Ctrl+P is handled here by addAction.
  view.addAction({
    id: 'haijunbot.openCommandPalette',
    label: 'Command Palette',
    keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyP],
    run: (ed) => {
      ed.trigger('keyboard', 'editor.action.quickCommand', null)
    },
  })
}

// LSP file:// URI → local absolute file path (e.g. file:///home/a.py → /home/a.py)
function lspUriToPath(uri) {
  if (!uri) return ''
  const raw = String(uri)
  if (!raw.startsWith('file://')) return raw
  return decodeURIComponent(raw.slice('file://'.length))
}

// Take the first target {path, line, column} from the LSP definition result (supports Location / LocationLink[])
function pickFirstDefinitionTarget(result) {
  if (!result) return null
  const items = Array.isArray(result) ? result : [result]
  for (const it of items) {
    if (!it) continue
    const uri = it.targetUri || it.uri
    const range = it.targetRange || it.range
    if (!uri || !range) continue
    return {
      path: lspUriToPath(uri),
      line: (range.start?.line ?? 0) + 1,
      column: (range.start?.character ?? 0) + 1,
    }
  }
  return null
}

// Ctrl+F12 custom jump-to-definition: after obtaining the target file, open it if not already open, then position to the target line/column
async function jumpToDefinition(ed) {
  const model = ed && ed.getModel && ed.getModel()
  const position = ed && ed.getPosition && ed.getPosition()
  if (!model || !position) return
  const result = await getDefinition(model, position)
  const target = pickFirstDefinitionTarget(result)
  if (!target || !target.path) return
  await revealInWorkspace(target.path, target.line, target.column)
}

// Open (or activate) the target file in the workspace and position it at the specified line and column.
// Reused for F12 jump-to-definition and peek double-click jump (registerEditorOpener).
async function revealInWorkspace(path, line, column) {
  if (!path) return
  // Determine whether it's already opened as a tab (not whether editorModels has a model—ensureModelForUri
  // may preload a cross-file model without creating a tab; judging by that alone would incorrectly go to activateWorkspaceTab,
  // causing the tab not to be created and only replacing the current buffer with the target file content).
  // If there is a tab, activate it; otherwise, openWorkspaceFile to create and activate a new tab.
  if (!getWorkspaceTabByPath(path)) {
    await openWorkspaceFile(path)
  } else {
    activateWorkspaceTab(path)
  }
  await nextTick()
  const view = getActiveWorkspaceView()
  if (!view) return
  view.revealLineInCenter(line)
  view.setPosition({ lineNumber: line, column })
  view.focus()
}

// Register a Monaco resource opener: when Monaco needs to open a resource outside the current model (e.g. peek
// definition WindowDouble-clickContentGo to, go-to-definition), callback here. DefaultLine for right NotLoad's
// model does nothing at all, so must self LineOpen target File Merge locate, Nothen peek Double-click No way Go to.
// Back true indicates Already handle, Monaco Not again walk Default logic.
monaco.editor.registerEditorOpener({
  openCodeEditor: async (source, resource, selectionOrPosition) => {
    const path = lspUriToPath(resource?.toString?.() || '')
    if (!path) return false
    const line = selectionOrPosition?.startLineNumber ?? selectionOrPosition?.lineNumber ?? 1
    const column = selectionOrPosition?.startColumn ?? selectionOrPosition?.column ?? 1
    await revealInWorkspace(path, line, column)
    return true
  },
})
function applyEditorViewModel(paneId, view) {
  const path = workspaceViewPanes.get(paneId)
  if (!path) {
    if (view.getModel()) view.setModel(null)
    view.updateOptions({ readOnly: !isWorkspaceEditable.value })
    return
  }
  const modelData = editorModels.get(path)
  if (!modelData) {
    workspaceViewPanes.delete(paneId)
    if (view.getModel()) view.setModel(null)
    return
  }
  let model = modelData.model
  if (!model || model.isDisposed()) {
    model = monaco.editor.createModel(modelData.content, modelData.language, monaco.Uri.file(path))
    model.__haijunbotPath = path
    modelData.model = model
  }
  if (view.getModel() !== model) view.setModel(model)
  view.updateOptions({ readOnly: !isWorkspaceEditable.value })
}

// NotSplitSplit when, Monaco ContainerDevice by WorkspacePanel Internal render (editorContainerRef), use Single instance Path.
//  for each file pane's ContainerDevice establish/Recover use instance; only create or destroy when ContainerDevice set Combine change.
//  close key: ref callback get to's element may Yes "Rendering...Between state" element (Vue follow Next/After will Replace drop It ), establish instance at 
// this kind detach Document's element Up will cause EditDevice DOM permanent hang Empty (ContainerDevice inside see Not to EditDevice). because This here Not directly connect
// use ref element, but Yes according to data-pane-id from Document Middle parse "Current true real mount" ContainerDevice.
function resolveSplitWorkspaceContainer(paneId) {
  const live = document.querySelector(`.workspace-monaco-container[data-pane-id="${paneId}"]`)
  if (live && live.isConnected) return live
  const refEl = splitWorkspaceContainerRefs.value.get(paneId)
  return refEl && refEl.isConnected ? refEl : null
}

function ensureSplitMonacoEditors() {
  for (const paneId of [...splitWorkspaceContainerRefs.value.keys()]) {
    const container = resolveSplitWorkspaceContainer(paneId)
    // ContainerDevice still Not true insert Document when Not want Create instance, wait Down one schedule (ref callback / rAF) fill.
    if (!container) continue
    let view = editorViews.get(paneId)
    // invalidation judge only see "host ContainerDevice element Yes No be Replace": Monaco's EditDevice DOM Yes Async mount,
    // getDomNode() at No model when Back null, Create Next/After immediately querySelector also get Not to root Node,
    //  because This any base in "instance DOM Yes No at ContainerDevice inside" judge all will misjudge Merge cause reverse Recover dispose/create.
    // ContainerDevice element itself be Vue Replace (pane rebuild) when, then need destroy old instance, at NewContainerDevice Up rebuild.
    if (view && view.__haijunbotContainer !== container) {
      view.dispose()
      editorViews.delete(paneId)
      view = null
    }
    if (!view) {
      view = monaco.editor.create(container, buildEditorOptions())
      view.__haijunbotContainer = container
      bindWorkspaceViewEvents(view)
      editorViews.set(paneId, view)
    }
    applyEditorViewModel(paneId, view)
  }
  // clean Already disappear pane's instance
  for (const [paneId, view] of [...editorViews]) {
    if (!splitWorkspaceContainerRefs.value.has(paneId)) {
      view.dispose()
      editorViews.delete(paneId)
      workspaceViewPanes.delete(paneId)
    }
  }
}

function ensureMonacoEditor() {
  ensureSplitMonacoEditors()
}




// Already SplitSplit when each pane's TagsList by "OpenFile / ClickTags" when explicit register (addPaneTab),
// New pane all from Empty open Initial; Not at here use global Tags fallback seed, Nothen New pane will with Empty out appear
// Other pane's Tags ( same one File same when out appear at two pane Top).

// explicit layout Combine Merge to Down one frame, avoid same one frame Inner right Multi items instance reverse Recover layout cause size oscillate.
// other Outer do Has limited Retry: ref callback trigger when ContainerDevice may still Not true insert Document (Vue may at Insert Insert Prev/Before call ref),
// This when build Not instance; wait Down one frame / Down one items tick ContainerDevice Insert Document Next/After again fill once, avoid "First time SplitSplit No instance".
let workspaceLayoutScheduled = false
let workspaceLayoutRetries = 0
const EDITOR_LAYOUT_MAX_RETRIES = 8
function scheduleWorkspaceLayout() {
  if (workspaceLayoutScheduled) return
  workspaceLayoutScheduled = true
  requestAnimationFrame(() => {
    workspaceLayoutScheduled = false
    layoutMonacoEditor()
    if (workspaceLayoutRetries < EDITOR_LAYOUT_MAX_RETRIES) {
      const pending = [...splitWorkspaceContainerRefs.value.keys()].some((paneId) => {
        const container = resolveSplitWorkspaceContainer(paneId)
        if (!container) return false
        const view = editorViews.get(paneId)
        return !view || view.__haijunbotContainer !== container
      })
      if (pending) {
        workspaceLayoutRetries += 1
        scheduleWorkspaceLayout()
        return
      }
    }
    workspaceLayoutRetries = 0
  })
}

function layoutMonacoEditor() {
  ensureSplitMonacoEditors()
  for (const [, view] of editorViews) {
    if (view.getContainerDomNode?.()?.isConnected) view.layout()
  }
}

// self by SplitSplit: Monaco ViewChart bind at specific DOM ContainerDevice Up, SplitSplit / activate / Close pane when ContainerDevice will be Replace,
//  old ContainerDevice with DOM Uninstall Next/After ViewChart then invalid. This place at ContainerDevice change Next/After rebuild ViewChart Merge restore Recover CurrentTags.
// explain: model (editorModels) and Content Not affected, only rebuild ViewChart layer.
function remountMonacoEditor() {
  // by ContainerDevice set Combine difference Split fill/Recover use instance (ContainerDevice Not change then Recover use, Not will rebuild)
  ensureSplitMonacoEditors()
}

// Save Current EditDevice (activate pane / Single instance) In progress Show's File's view state (cursor Position, scroll Position, selection, Fold).
// Monaco's setModel will Reset cursor and scroll, SwitchTagsPrev/Before must first Save, Nothen switch back come PositionMissing.
function saveCurrentEditorViewState() {
  const currentPath = activeWorkspaceTabPath.value
  if (!currentPath) return
  const modelData = editorModels.get(currentPath)
  if (!modelData) return
  const view = editorViews.get(activePaneId.value)
  // No model when saveViewState Back Empty Status, will Overwrite Already Save's viewState (such as remountMonacoEditor rebuild ViewChart Next/After)
  if (!view || !view.getModel()) return
  modelData.viewState = view.saveViewState()
}

// recover Recover specified pane Up target File's view state (Need at setModel's Next/After call).
function restoreEditorViewState(view, path) {
  if (!view) return
  const modelData = editorModels.get(path)
  if (!modelData?.viewState) return
  view.restoreViewState(modelData.viewState)
}

function activateWorkspaceTab(path) {
  // SwitchPrev/Before first Save CurrentFile's view state (cursor + scroll), Nothen setModel Reset Next/After PositionMissing
  saveCurrentEditorViewState()
  const session = activeWorkspaceSession.value
  if (session) session.activeTabPath = path
  const modelData = editorModels.get(path)
  if (!modelData) return
  let model = modelData.model
  if (!model || model.isDisposed()) {
    model = monaco.editor.createModel(modelData.content, modelData.language, monaco.Uri.file(path))
    model.__haijunbotPath = path
    modelData.model = model
  }
  // only bind "activate pane" to thisFile; Other pane keep each Content (New pane for Empty)
  ensureSplitMonacoEditors()
  const activeView = editorViews.get(activePaneId.value)
  if (activeView) {
    // thisFile register to activate pane's TagsList (ClickTags/OpenFile all walk here)
    addPaneTab(activePaneId.value, path)
    workspaceViewPanes.set(activePaneId.value, path)
    if (activeView.getModel() !== model) activeView.setModel(model)
    restoreEditorViewState(activeView, path)
    activeView.updateOptions({ readOnly: !isWorkspaceEditable.value })
    nextTick(() => {
      scheduleWorkspaceLayout()
      activeView.focus()
    })
  }
  // model ready Next/After try connectInsert LSP (Failed silent degrade, Not affect EditDevice)
  activateLspForModel(path, modelData)
}

// ---------------------------------------------------------------------------
// LSP connectInsert (thin layer: all Has logic at src/lsp/ Module Internal, This place only do timing orchestrate)
// ---------------------------------------------------------------------------

// language clean Single only Need pull once, Failed also Not block EditDevice
let lspRegistryReady = false
async function ensureLspRegistry() {
  if (lspRegistryReady) return
  try {
    await loadLspServers({
      fetchWithAuth,
      getGatewayAddress,
      getHttpProtocol,
    })
    lspRegistryReady = true
  } catch {
    // registry Internal Already degrade handle, here fallback
  }
}

// record path -> { serverId, root }, for CloseTags when precise release
const lspBindings = new Map()

/**
 *  for Current model connectInsert LSP.
 *
 * Already know limit: only Supports master Local (File read write walk /api/node/{id}/... when,
 * non master Node's FileSystem and Local LSP in process Not consistent, so Skip).
 */
async function activateLspForModel(path, modelData) {
  if (!path || !modelData || !modelData.model) return
  // ReadonlyPreview、non master Node：Not connectInsert
  if (getWorkspaceTargetNodeId() !== 'master') return

  await ensureLspRegistry()

  const language = modelData.model.getLanguageId?.() || modelData.language
  const spec = getServerByLanguage(language) || getServerByPath(path)
  if (!spec) return

  const workspaceRoot = resolveLspWorkspaceRoot(path)
  const client = await ensureClient({
    spec,
    workspaceRoot,
    model: modelData.model,
    deps: { fetchWithAuth, getGatewayAddress, getWebSocketProtocol, buildWebSocketProtocols, ensureModelForUri },
  })
  if (client) {
    lspBindings.set(path, { serverId: spec.id, root: workspaceRoot })
  }
}

/**
 * ensure file:// uri right should's Monaco model Already exists (cross File peek definition need).
 *
 * Monaco Internal set peek pass monaco.editor.getModel(uri) get target model render Content;
 * target File from NotOpen past when model Does not exist → peek only Show File name/LineColumn number, Content Empty blank.
 * here at definition provider Back Prev/Before AsyncLoad target File Merge Create model (Not activate Tags,
 * Not Create workspace tab), let peek can get to Content. AlreadyLoad then directly connect Recover use.
 *
 * @param {string} uri LSP file:// uri
 * @returns {Promise<void>}
 */
async function ensureModelForUri(uri) {
  if (!uri) return
  const raw = String(uri)
  const path = raw.startsWith('file://') ? decodeURIComponent(raw.slice('file://'.length)) : raw
  if (!path) return
  const existing = editorModels.get(path)
  if (existing && existing.model && !existing.model.isDisposed()) return
  // ReadonlyPreview, non master Node: No way read remote File Content, Skip (keep Original Has degrade)
  if (getWorkspaceTargetNodeId() !== 'master') return
  const content = await fetchFileContent(path)
  const spec = getServerByPath(path)
  const language = spec?.monacoLanguage || 'plaintext'
  let model = existing?.model
  if (!model || model.isDisposed()) {
    model = monaco.editor.createModel(content, language, monaco.Uri.file(path))
    model.__haijunbotPath = path
  } else {
    model.setValue(content)
  }
  editorModels.set(path, { model, content, language })
}

/**  by FilePath derive workspace root Directory (get at Directory, Next/After end will verify its exist at). */
function resolveLspWorkspaceRoot(path) {
  const normalized = String(path || '')
  const idx = normalized.lastIndexOf('/')
  return idx > 0 ? normalized.slice(0, idx) : ''
}

/**
 * release certain items File bind's LSP Connect.
 * only when same one (serverId, root) Already No Other File at use then true Close Connect,
 * avoid frequent SwitchTags cause reverse Recover Restart language Service Device.
 */
function releaseLspBinding(path) {
  const binding = lspBindings.get(path)
  if (!binding) return
  lspBindings.delete(path)

  for (const other of lspBindings.values()) {
    if (other.serverId === binding.serverId && other.root === binding.root) {
      return // still Has Other File at use same one Connect
    }
  }
  disposeClient(binding.serverId, binding.root)
}

function resolveAgentRelativePath(relativePath, agentId = null) {
  if (!relativePath) return ''
  const raw = String(relativePath)
  // never directly connect back absolute Path, Not do working_dir concatenate (Nothen will treat absolute Path as relative Path concatenate out duplicate Recover Prev/Before suffix)
  if (raw.startsWith('/')) return raw
  // prefer use specified Agent's work Directory parse (CommandPanel/Search scene should use its right should's Agent,
  // but non currentAgent — both may Not consistent, cause concatenate out relative Path trigger Monaco "path must be absolute").
  let workingDir = ''
  if (agentId) {
    const agent = agentListGetter().value.find(a => a.agent_id === agentId)
    workingDir = agent?.working_dir || ''
  }
  if (!workingDir) workingDir = currentAgent().value?.working_dir || ''
  if (!workingDir) return raw
  return `${workingDir.replace(/\/$/, '')}/${raw.replace(/^\//, '')}`
}

async function fetchGlobalSearchResults(agentId, payload) {
  const { host, port } = getGatewayAddress()
  // use pass Insert's agentId right should's node_id
  const agent = agentListGetter().value.find(a => a.agent_id === agentId)
  if (!agent) {
    throw new Error(`Not foundAgent: ${agentId}`)
  }
  if (!agent.node_id) {
    throw new Error(`AgentNonode_id: ${agentId}`)
  }
  const targetNodeId = String(agent.node_id).trim()
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `global-search/${agentId}`), {
    method: 'POST',
    body: JSON.stringify({
      ...payload,
      node_id: targetNodeId,
    })
  })
  const result = await response.json()
  if (!response.ok || !result.success || !result.data) {
    throw new Error(result.error?.message || 'Global SearchFailed')
  }
  return result.data
}

async function fetchFileSearchResults(agentId, payload) {
  const { host, port } = getGatewayAddress()
  const agent = agentListGetter().value.find(a => a.agent_id === agentId)
  if (!agent) {
    throw new Error(`Not foundAgent: ${agentId}`)
  }
  if (!agent.node_id) {
    throw new Error(`AgentNonode_id: ${agentId}`)
  }
  const targetNodeId = String(agent.node_id).trim()
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `file-search/${agentId}`), {
    method: 'POST',
    body: JSON.stringify({
      ...payload,
      node_id: targetNodeId,
    })
  })
  const result = await response.json()
  if (!response.ok || !result.success || !result.data) {
    throw new Error(result.error?.message || 'File name SearchFailed')
  }
  return result.data
}

const hasWorkspaceSidebarFileTree = computed(() => {
  const agentId = activeWorkspaceSessionId.value
  if (!agentId) return false
  return getVisibleFileTreeNodes(agentId).length > 0
})

async function ensureWorkspaceSidebarFileTree(agent = activeWorkspaceSession.value?.agent) {
  if (!agent?.agent_id || !agent.working_dir) return
  const treeNodes = fileTreeState.value.get(agent.agent_id) || []
  if (treeNodes.length === 0) {
    await initFileTree(agent.agent_id, agent.working_dir)
  }
}

function setWorkspaceSidebarView(view) {
  workspaceSidebarView.value = view
  showWorkspaceSidebar.value = true
  if (view === 'files') {
    nextTick(() => {
      ensureWorkspaceSidebarFileTree()
      layoutMonacoEditor()
    })
    return
  }
  if (view === 'git') {
    // switch to Git ViewChart when AutoRefresh Submit history and Split branch (each Switch all Pull most New, avoid stop leave at old Data)
    nextTick(() => {
      layoutMonacoEditor()
      layoutGitDiffEditor()
      if (!gitLogLoading.value) {
        refreshGitView()
      }
    })
    return
  }
  if (view === 'manage') {
    // switch to ability clean Single ViewChart: Data cache, avoid frequent request; only First time Open (four items Data source all for Empty) when Load,
    // after Next/After rely on Sidebar Internal "Refresh" Button Manual Refresh.
    // note: Not can use topologyDaemonSessions/topologyExtensionSessions Yes No for Empty come judge ——
    // these two items ref and network topology Chart Total share, may Already be topology Chart poll fill, cause installedScripts/
    // gatewayScripts forever Not Load (GatewayScript library block Not Show).
    if (
      !topologyDaemonSessions.value.length &&
      !topologyExtensionSessions.value.length &&
      !manageInstalledScripts.value.length &&
      !manageGatewayScripts.value.length
    ) {
      refreshManageCapabilities()
    }
    nextTick(() => {
      layoutMonacoEditor()
    })
    return
  }
  if (view === 'timers') {
    // switch to ScheduledTasksViewChart: Tasks will change, Pull most New List (Readonly display)
    refreshManageTimers()
    nextTick(() => {
      layoutMonacoEditor()
    })
    return
  }
  if (view === 'plugins') {
    // switch to ExtensionViewChart: Extension List may change, Pull most New (Component Internal pass watch self Line Load)
    nextTick(() => {
      layoutMonacoEditor()
    })
    return
  }
  nextTick(() => {
    layoutMonacoEditor()
  })
}

// activity bar ButtonClick: Already Open this Sidebar ViewChart when again Click then Collapse, Nothen Switch to this ViewChart.
function toggleWorkspaceSidebarView(view) {
  if (showWorkspaceSidebar.value && workspaceSidebarView.value === view) {
    closeWorkspaceSidebar()
    return
  }
  setWorkspaceSidebarView(view)
}

// activity bar ButtonClick (Chat room/Terminal): Already Open this main ViewChart when again Click then return to FileViewChart.
// Already unify for pane tree: host by certain items pane carry (NotSplitSplit when only leaf then carry pane).
function toggleWorkspaceMainView(view) {
  const hostedByPane = !!findWorkspacePaneByView(view)
  if (workspaceMainView.value === view || hostedByPane) {
    setWorkspaceMainView('file')
    return
  }
  setWorkspaceMainView(view)
}

// SwitchEditDevice main area ViewChart (file / chat / terminal)
function setWorkspaceMainView(view) {
  // Already unify for pane tree: pane tree itself carry file/session Content, main area ViewChart constant for file,
  //  because This here Not Modify workspaceMainView, also Not CollapseSplitSplit (Session Show at each own pane Middle).
  // "Collapse" semantics (switch back file) must at This raise Prev/Before handle, Nothen will be Down side workspaceMainView === view early back swallow.
  if (view === 'file') {
    // Collapse: treat carry chat / terminal's pane clear into Middle empty (host Single case, at most Multi one items)
    const hostPane = findWorkspacePaneByView('chat') || findWorkspacePaneByView('terminal')
    if (hostPane) setActivePaneViewForPane(hostPane, 'empty')
    // NotSplitSplit (only leaf) when if main area Not Yes File ViewChart, Original place switch back File Merge rearrange Monaco
    if (workspacePaneCount.value === 1 && workspaceMainView.value !== 'file') {
      setMainViewOnLeaf('file')
      nextTick(() => {
        layoutMonacoEditor()
        layoutGitDiffEditor()
      })
    }
    return
  }
  if (view === 'session') {
    // session by pane carry: give ensurePaneForView locate carry pane (NotSplitSplit when only leaf Original place carry)
    ensurePaneForView('session', workspaceSessionPanelIdGetter().value)
    return
  }
  // chat / terminal: Empty then Original place, Already Has then Recover use, Nothen SplitSplit (Not Overwrite Current area)
  ensurePaneForView(view)
  return
}

//  at Workspace Middle Show chat / terminal (host Single case): ensure WorkspacePanel Already Open, then give main area or activate pane carry.
// Panel Split off can ability remove Next/After, chat/terminal only can at Workspace Internal render,  because This any "Open terminal/Chat room"'s Insert mouth
// all must walk here, but Not Yes go Modify Already abandon's showTerminalPanel / showChatPanel flag.
function showWorkspaceHostView(view) {
  if (!showWorkspacePanel.value) {
    showWorkspacePanel.value = true
    if (windowWidth.value <= 768) pushOverlayState()
  }
  setWorkspaceMainView(view)
}

//  let main area return to "FileViewChart" (OpenFile when call).
// main area's file/chat/terminal/session four kinds Content Yes mutually exclusive, OpenFile Class Content must first switch back FileViewChart,
// Nothen will be chat/terminal/session Content block.
function showWorkspaceFileView() {
  if (workspaceMainView.value !== 'file') {
    setMainViewOnLeaf('file')
  }
  // switch back Next/After ContainerDevice size may change, rearrange Monaco (include diff), ensure Content correct render
  nextTick(() => {
    layoutMonacoEditor()
    layoutGitDiffEditor()
  })
}

function toggleWorkspaceSearchSidebar() {
  if (showWorkspaceSidebar.value && workspaceSidebarView.value === 'search') {
    closeWorkspaceSidebar()
    return
  }
  setWorkspaceSidebarView('search')
}

function closeWorkspaceSidebar() {
  showWorkspaceSidebar.value = false
  // sidebar Collapse Not affect main area diff, only rearrange main EditDevice
  nextTick(() => {
    layoutMonacoEditor()
  })
}

function clearGlobalSearch() {
  globalSearchQuery.value = ''
  globalSearchFileGlob.value = ''
  globalSearchCaseSensitive.value = false
  globalSearchWholeWord.value = false
  globalSearchError.value = ''
  globalSearchResults.value = []
  fileSearchResults.value = []
  globalSearchTotalFiles.value = 0
  globalSearchTotalMatches.value = 0
  globalSearchExecuted.value = false
}

async function runGlobalSearch() {
  const searchAgentId = effectiveGlobalSearchAgentId().value
  if (!searchAgentId) {
    showToast('Please first Select Agent', 'error')
    return
  }

  const query = globalSearchQuery.value.trim()
  if (!query) {
    globalSearchError.value = 'Please enter Search keyword'
    globalSearchExecuted.value = false
    globalSearchResults.value = []
    fileSearchResults.value = []
    setWorkspaceSidebarView('search')
    return
  }

  setWorkspaceSidebarView('search')
  globalSearchLoading.value = true
  globalSearchError.value = ''
  globalSearchExecuted.value = false

  try {
    if (globalSearchMode.value === 'filename') {
      const data = await fetchFileSearchResults(searchAgentId, {
        query,
        case_sensitive: globalSearchCaseSensitive.value,
        max_results: 200,
        file_glob: globalSearchFileGlob.value.trim(),
      })
      fileSearchResults.value = Array.isArray(data.results) ? data.results : []
      globalSearchTotalFiles.value = Number(data.total_files || 0)
      globalSearchTotalMatches.value = 0
      globalSearchExecuted.value = true
      return
    }
    const data = await fetchGlobalSearchResults(searchAgentId, {
      query,
      case_sensitive: globalSearchCaseSensitive.value,
      whole_word: globalSearchWholeWord.value,
      max_results: 100,
      file_glob: globalSearchFileGlob.value.trim(),
    })
    globalSearchResults.value = Array.isArray(data.results) ? data.results : []
    globalSearchTotalFiles.value = Number(data.total_files || 0)
    globalSearchTotalMatches.value = Number(data.total_matches || 0)
    globalSearchExecuted.value = true
  } catch (error) {
    globalSearchError.value = error.message || 'Global SearchFailed'
    globalSearchResults.value = []
    fileSearchResults.value = []
    globalSearchTotalFiles.value = 0
    globalSearchTotalMatches.value = 0
    globalSearchExecuted.value = true
    showToast(globalSearchError.value, 'error')
  } finally {
    globalSearchLoading.value = false
  }
}

function setGlobalSearchMode(mode) {
  if (globalSearchMode.value === mode) return
  globalSearchMode.value = mode
  globalSearchError.value = ''
  globalSearchExecuted.value = false
  globalSearchResults.value = []
  fileSearchResults.value = []
  globalSearchTotalFiles.value = 0
  globalSearchTotalMatches.value = 0
}

function openFileSearchResult(filePath) {
  openWorkspaceFile(resolveAgentRelativePath(filePath, effectiveGlobalSearchAgentId().value), effectiveGlobalSearchAgentId().value)
}

async function openGlobalSearchResult(filePath, lineNumber, matchStart = 0, matchEnd = matchStart) {
  const absolutePath = resolveAgentRelativePath(filePath, effectiveGlobalSearchAgentId().value)
  // use global Search Sidebar Selected's Agent
  await openWorkspaceFile(absolutePath, effectiveGlobalSearchAgentId().value)
  await nextTick()
  const modelData = editorModels.get(absolutePath)
  const view = getActiveWorkspaceView()
  if (!view || !modelData) {
    return
  }

  // Monaco: pass setPosition / setSelection + revealLineInCenter locate
  const line = Number(lineNumber || 1)
  const col = Number(matchStart || 0) + 1
  const endCol = Math.max(col, Number(matchEnd || matchStart || 0) + 1)

  view.revealLineInCenter(line)
  view.setSelection(new monaco.Selection(line, col, line, endCol))
  view.setPosition({ lineNumber: line, column: col })
  view.focus()
}

async function fetchFileContent(path, agentId = null) {
  const { host, port } = getGatewayAddress()
  // If agentId is provided, use its node_id; otherwise use the node_id of the currently active editor session
  let targetNodeId
  if (agentId) {
    const agent = agentListGetter().value.find(a => a.agent_id === agentId) || getVirtualWorkspaceAgent(agentId)
    if (!agent) {
      throw new Error(`Not foundAgent: ${agentId}`)
    }
    if (!agent.node_id) {
      throw new Error(`AgentNonode_id: ${agentId}`)
    }
    targetNodeId = String(agent.node_id).trim()
  } else {
    targetNodeId = getWorkspaceTargetNodeId()
  }
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-content'), {
    method: 'POST',
    body: JSON.stringify({ path, node_id: targetNodeId })
  })

  const result = await response.json()
  if (!response.ok || !result.success || !result.data) {
    throw new Error(result.error?.message || 'read File Failed')
  }
  return result.data.content || ''
}

async function fetchFileStat(path, agentId = null) {
  const { host, port } = getGatewayAddress()
  // If agentId is provided, use its node_id; otherwise use the node_id of the currently active editor session
  let targetNodeId
  if (agentId) {
    const agent = agentListGetter().value.find(a => a.agent_id === agentId) || getVirtualWorkspaceAgent(agentId)
    if (!agent) {
      throw new Error(`Not foundAgent: ${agentId}`)
    }
    if (!agent.node_id) {
      throw new Error(`AgentNonode_id: ${agentId}`)
    }
    targetNodeId = String(agent.node_id).trim()
  } else {
    targetNodeId = getWorkspaceTargetNodeId()
  }
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-stat'), {
    method: 'POST',
    body: JSON.stringify({ path, node_id: targetNodeId })
  })

  const result = await response.json()
  if (!response.ok || !result.success || !result.data) {
    throw new Error(result.error?.message || 'read File Status Failed')
  }
  return result.data
}

async function refreshWorkspaceTabFromRemote(path, showAutoRefreshToast = false) {
  const tab = getWorkspaceTabByPath(path)
  if (!tab) return

  const [content, fileStat] = await Promise.all([
    fetchFileContent(path),
    fetchFileStat(path),
  ])

  tab.content = content
  tab.originalContent = content
  tab.isDirty = false
  tab.error = ''
  tab.externalModified = false
  updateWorkspaceTabFileStat(tab, fileStat)

  const modelData = editorModels.get(path)
  if (modelData && modelData.content !== content) {
    modelData.content = content
    // The model is shared: updating the model content directly synchronizes it across all panes that have the file open
    const model = modelData.model
    if (model && !model.isDisposed()) {
      model.setValue(content)
    }
  }

  if (showAutoRefreshToast) {
    showToast('DetectedFileAlreadyUpdate，AlreadyAutoRefresh', 'info')
  }
}

async function checkActiveWorkspaceFileHeartbeat() {
  if (!showWorkspacePanel.value) return

  const tab = activeWorkspaceTab.value
  if (!tab || tab.loading || !tab.path) return

  try {
    const remoteFileStat = await fetchFileStat(tab.path)
    const remoteMtimeNs = remoteFileStat.mtime_ns ?? null
    const remoteFileSize = remoteFileStat.size ?? null
    const localMtimeNs = tab.mtimeNs ?? null
    const localFileSize = tab.fileSize ?? null
    const hasRemoteChange =
      remoteMtimeNs !== localMtimeNs || remoteFileSize !== localFileSize

    if (!hasRemoteChange) {
      if (!tab.isDirty && tab.externalModified) {
        tab.externalModified = false
      }
      return
    }

    if (tab.isDirty) {
      if (!tab.externalModified) {
        tab.externalModified = true
        tab.error = 'File Already modified externally, Please handle conflict first then Save'
        showToast('Detected File external change, Current Tags have unsaved changes', 'error')
      }
      return
    }

    await refreshWorkspaceTabFromRemote(tab.path, true)
  } catch (error) {
    console.error('[EDITOR] File heartbeat check failed:', error)
  }
}

function stopWorkspaceFileHeartbeat() {
  if (workspaceFileHeartbeatTimer.value) {
    clearInterval(workspaceFileHeartbeatTimer.value)
    workspaceFileHeartbeatTimer.value = null
  }
}

function startWorkspaceFileHeartbeat() {
  stopWorkspaceFileHeartbeat()

  if (!showWorkspacePanel.value || !activeWorkspaceTab.value) {
    return
  }

  workspaceFileHeartbeatTimer.value = setInterval(() => {
    checkActiveWorkspaceFileHeartbeat()
  }, EDITOR_FILE_HEARTBEAT_INTERVAL)
}

async function openWorkspaceFile(path, agentId = null) {
  if (!path) return

  showWorkspacePanel.value = true
  // Intelligent placement when opening (clicking a file in the sidebar):
  //  1) Current active area is empty → create an editor in the current area;
  //  2) Otherwise, reuse an already-open editor panel (do not overwrite the current session/chat/terminal);
  //  3) Otherwise, split the current area to create a new editor.
  // Returns paneId if placed in a split pane; returns null to follow the non-split in-place path.
  const targetPaneId = ensureEditorPaneForFileOpen(agentId)
  // Opening a file belongs to the "File" view: if not split and opened in-place, and the main area is on chat/terminal/session,
  // switch back to the File view first, otherwise the file (and diffs) will be obscured by those contents.
  // (When split, ensureEditorPaneForFileOpen handles placing into a file pane, so no need to switch.)
  if (!targetPaneId) {
    showWorkspaceFileView()
  }

  const existingTab = getWorkspaceTabByPath(path)
  if (existingTab) {
    // Unified to a pane tree: register this file in the tab list of the "active pane" (the same file may appear in multiple panes simultaneously)
    addPaneTab(activePaneId.value, path)
    activateWorkspaceTab(path)
    return
  }

  const tab = reactive({
    path,
    name: path.split('/').pop() || path,
    content: '',
    originalContent: '',
    language: getLanguageFromFilename(path),
    isDirty: false,
    loading: true,
    error: '',
    externalModified: false,
    mtimeNs: null,
    fileSize: null,
  })
  const session = activeWorkspaceSession.value
  if (!session) {
    // The editor panel may be opened via Ctrl+E / the command palette (only sets showWorkspacePanel, no session created).
    // In this case, create a session based on the provided agentId or the current Agent to avoid silent failure when clicking a file.
    // Note: virtual directory sessions (directories opened without creating an Agent) are not in agentList; after refresh,
    // activeWorkspaceSession is empty (restoreVirtualWorkspaceDirs only restores sessions, does not activate them),
    // so we must prioritize matching an existing virtual session by agentId and activate it; otherwise clicking a file silently does nothing.
    const virtualSession = agentId
      ? workspaceSessions.value.find(s => s.agent_id === agentId && s.agent?.virtual === true)
      : null
    if (virtualSession) {
      activeWorkspaceSessionId.value = agentId
    } else {
      const targetAgent = (agentId && agentListGetter().value.find(a => a.agent_id === agentId))
        || getCurrentAgentOrNull()
      if (!targetAgent) return
      createWorkspaceForAgent(targetAgent)
      if (!activeWorkspaceSession.value) return
    }
  }
  const activeSession = activeWorkspaceSession.value
  activeSession.tabs.push(tab)
  activeSession.activeTabPath = path
  // Unified to a pane tree: register the new file in the tab list of the "active pane"
  addPaneTab(activePaneId.value, path)

  try {
    const [content, fileStat] = await Promise.all([
      fetchFileContent(path, agentId),
      fetchFileStat(path, agentId),
    ])
    tab.content = content
    tab.originalContent = content
    tab.externalModified = false
    updateWorkspaceTabFileStat(tab, fileStat)
    tab.loading = false

    let modelData = editorModels.get(path)
    if (!modelData) {
      modelData = { model: null, content, language: getLanguageExtension(tab.language) }
      editorModels.set(path, modelData)
    }
    modelData.content = content

    await nextTick()
    // Ensure the editor container exists (when opening from a no-tabs state, wait for DOM update)
    let retryCount = 0
    while (!editorContainerRef.value && retryCount < 10) {
      await new Promise(resolve => setTimeout(resolve, 50))
      retryCount++
    }
    ensureMonacoEditor()
    activateWorkspaceTab(path)
  } catch (error) {
    tab.loading = false
    tab.error = error.message || 'read File Failed'
  }
}

async function saveWorkspaceTab(path) {
  const tab = getWorkspaceTabByPath(path)
  if (!tab) return

  const modelData = editorModels.get(path)
  const content = modelData ? modelData.content : tab.content

  const { host, port } = getGatewayAddress()
  const targetNodeId = getWorkspaceTargetNodeId()
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-write'), {
    method: 'POST',
    body: JSON.stringify({ path, content, node_id: targetNodeId })
  })
  const result = await response.json()

  if (!response.ok || !result.success) {
    const message = result.error?.message || 'SaveFileFailed'
    tab.error = message
    showToast(message, 'error')
    return
  }

  tab.originalContent = content
  tab.content = content
  tab.isDirty = false
  tab.error = ''
  tab.externalModified = false

  try {
    const fileStat = await fetchFileStat(path)
    updateWorkspaceTabFileStat(tab, fileStat)
  } catch (error) {
    console.error('[EDITOR] Failed to refresh file stat after save:', error)
  }

  showToast(`${getNodeDisplayName(targetNodeId)}Node's${path}AlreadySave`, 'success')
}

async function saveActiveWorkspaceTab() {
  if (!activeWorkspaceTab.value) return
  await saveWorkspaceTab(activeWorkspaceTab.value.path)
}

// Save the file currently bound to the specified pane (called by the Save button in each pane)
async function savePaneWorkspaceFile(paneId) {
  const path = workspaceViewPanes.get(paneId)
  if (!path) return
  await saveWorkspaceTab(path)
}

function toggleWorkspaceEditable() {
  isWorkspaceEditable.value = !isWorkspaceEditable.value
  for (const [, view] of editorViews) {
    view.updateOptions({ readOnly: !isWorkspaceEditable.value })
  }
}

function hasDirtyWorkspaceTabs() {
  return workspaceTabs.value.some(tab => tab.isDirty)
}

function confirmCloseWorkspacePanel() {
  return new Promise((resolve) => {
    showConfirm(
      'NotSave Tags exist, Confirm Close EditDevice?',
      () => resolve(true),
      () => resolve(false),
      false
    )
  })
}

// When the editor main area is hosting terminal/chat, the display state of the corresponding standalone panels is stale (replaced by embedded hosting);
// Reset before closing the editor, otherwise standalone panels may reappear out of nowhere (e.g. create a terminal inside the editor, then close the editor).
// Also reset the main area view to avoid opening the editor next time and landing directly on terminal/chat view.
function resetWorkspaceHostedPanelState() {
  if (workspaceHostsTerminal().value) showTerminalPanel.value = false
  if (workspaceHostsChat().value) showChatPanel.value = false
  setMainViewOnLeaf('file')
  // When closing the editor, also collapse free-splitting to avoid leftover multi-pane layout next time
  if (workspacePaneCount.value > 1) collapseWorkspacePanes()
  // Inline session panels are only rendered inside the editor: when the editor closes, they lose their host,
  // and if left in panels, they are invisible but keep hasNoPanel false (the pet lobby will not show).
  // Therefore, close all session panels together when closing the editor.
  for (const panel of [...panelsGetter().value]) {
    closePanelGetter()(panel.id)
  }
  workspaceSessionPanelIdGetter().value = null
}

// "Close editor" is just hiding: keep the main area view, free-split layout, session panels, and diff data
// so reopening restores the pre-close state. Here we only do the necessary cleanup to avoid standalone terminal/chat panels reappearing
// (when hosted inline, the standalone panel display state is a stale value that needs resetting after closing the editor).
// Note: must call before setting showWorkspacePanel to false, otherwise workspaceHosts* is already false
// and standalone panels will not be collapsed.
function hideWorkspaceHostedPanelState() {
  if (workspaceHostsTerminal().value) showTerminalPanel.value = false
  if (workspaceHostsChat().value) showChatPanel.value = false
}

async function closeWorkspacePanel() {
  if (hasDirtyWorkspaceTabs()) {
    const confirmed = await confirmCloseWorkspacePanel()
    if (!confirmed) return
  }

  hideWorkspaceHostedPanelState()
  showWorkspacePanel.value = false
}

// Create/open an editor session for an Agent
function createWorkspaceForAgent(agent) {
  if (!socket.value) {
    console.warn('[workspace-session] No socket connection')
    return
  }

  const agentId = agent.agent_id
  const agentName = agent.name || agent.agent_type

  // Check if an editor session for this Agent already exists
  let session = workspaceSessions.value.find(s => s.agent_id === agentId)
  if (!session) {
    // Create a new editor session
    session = {
      agent_id: agentId,
      agent_name: agentName,
      agent: agent,
      tabs: [],
      activeTabPath: null,
      editorModels: new Map(),
      isEditable: false,
      showSidebar: true,
      sidebarView: 'files'
    }
    workspaceSessions.value.push(session)
  }

  // Switch to that session
  activeWorkspaceSessionId.value = agentId
  showWorkspacePanel.value = true

}

// Agent ID prefix for virtual directory sessions: open a directory on some node without creating an Agent
const VIRTUAL_WORKSPACE_PREFIX = '__node__:'

// Persistence key for opened directories: auto-restored after refresh, no need to re-add.
// Only store node_id + working_dir (agent_id derived from them) to avoid persisting the entire session object.
const VIRTUAL_DIRS_STORAGE_KEY = 'haijunbot_virtual_workspace_dirs'

// Restore pseudo-agent info (including node_id/working_dir) from a virtual session's agent_id for reuse in file tree and file I/O
function getVirtualWorkspaceAgent(agentId) {
  const key = String(agentId || '')
  if (!key.startsWith(VIRTUAL_WORKSPACE_PREFIX)) return null
  const session = workspaceSessions.value.find(s => s.agent_id === key)
  return session?.agent || null
}

// For file tree/file operations, unify agent resolution: prefer real Agent, else virtual directory session
function resolveFileTreeAgent(agentId) {
  return agentListGetter().value.find(a => a.agent_id === agentId) || getVirtualWorkspaceAgent(agentId)
}

// Look up the directory-tree Agent (real Agent or virtual directory session) owning a file by its absolute path:
// Match by working_dir prefix, taking the one with the longest prefix (avoid matching a parent directory's Agent under a nested directory);
// If prefix lengths tie, prefer an active Agent to avoid hitting an old stopped Agent in the same directory.
// Returns { agentId, agent } or null.
function resolveAgentForPath(path) {
  const raw = String(path || '')
  if (!raw) return null
  const candidates = []
  // Real Agent: include whether it is stopped (virtual directory sessions have no "stopped" concept; treat as active)
  for (const agent of agentListGetter().value) {
    if (agent?.agent_id && agent.working_dir) {
      candidates.push({ agent, stopped: isStoppedAgent(agent) })
    }
  }
  for (const session of virtualWorkspaceSessions.value) {
    if (session?.agent?.agent_id && session.agent.working_dir) {
      candidates.push({ agent: session.agent, stopped: false })
    }
  }
  let best = null
  let bestLen = -1
  let bestStopped = true
  for (const { agent, stopped } of candidates) {
    const dir = String(agent.working_dir).replace(/\/+$/, '')
    if (!dir) continue
    if (raw === dir || raw.startsWith(`${dir}/`)) {
      // Longer prefix takes precedence; if tie in length, active Agent takes precedence over stopped Agent
      if (dir.length > bestLen || (dir.length === bestLen && bestStopped && !stopped)) {
        best = agent
        bestLen = dir.length
        bestStopped = stopped
      }
    }
  }
  return best ? { agentId: best.agent_id, agent: best } : null
}

// Read persisted "opened directories" records
function loadVirtualWorkspaceDirs() {
  try {
    const raw = localStorage.getItem(VIRTUAL_DIRS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(item => item && item.node_id && item.working_dir)
      .map(item => ({ node_id: String(item.node_id), working_dir: String(item.working_dir) }))
  } catch (e) {
    return []
  }
}

// Write current virtual directory sessions back to localStorage (based on actual sessions; removed ones naturally disappear)
function saveVirtualWorkspaceDirs() {
  try {
    const dirs = virtualWorkspaceSessions.value
      .map(s => ({
        node_id: String(s.agent?.node_id || '').trim(),
        working_dir: String(s.agent?.working_dir || '').trim(),
      }))
      .filter(item => item.node_id && item.working_dir)
    localStorage.setItem(VIRTUAL_DIRS_STORAGE_KEY, JSON.stringify(dirs))
  } catch (e) {
    // Silently degrade if localStorage is unavailable (private mode / quota exceeded)
  }
}

// Create or reuse a virtual directory session for a node, returns { agentId, agent }
// Note: agent_id is determined by both "node + directory" (the same node may have multiple directories open simultaneously),
// so we cannot generate the ID by node alone; otherwise opening a different directory on the same node would reuse and overwrite the previous session.
function ensureVirtualWorkspaceSession(nodeId, dirPath) {
  const targetNodeId = String(nodeId || 'master').trim() || 'master'
  const targetDir = String(dirPath || '').trim()
  if (!targetDir) return null

  const agentId = `${VIRTUAL_WORKSPACE_PREFIX}${targetNodeId}:${targetDir}`
  // Node name + directory name, to distinguish multiple directories under the same node in the file tree
  const dirLabel = targetDir.replace(/\/+$/, '').split('/').pop() || targetDir
  const virtualAgent = {
    agent_id: agentId,
    name: `${getNodeDisplayName(targetNodeId)} · ${dirLabel}`,
    node_id: targetNodeId,
    working_dir: targetDir,
    agent_type: 'virtual_dir',
    virtual: true
  }

  let session = workspaceSessions.value.find(s => s.agent_id === agentId)
  if (!session) {
    session = {
      agent_id: agentId,
      agent_name: virtualAgent.name,
      agent: virtualAgent,
      tabs: [],
      activeTabPath: null,
      editorModels: new Map(),
      isEditable: false,
      showSidebar: true,
      sidebarView: 'files'
    }
    workspaceSessions.value.push(session)
  } else {
    // When reusing an existing virtual session, refresh the node and working directory
    session.agent = virtualAgent
    session.agent_name = virtualAgent.name
  }
  return { agentId, agent: virtualAgent }
}

// Open "a certain directory on a certain node" as the editor workspace (no need to create an Agent first)
async function openWorkspaceDir(nodeId, dirPath) {
  const created = ensureVirtualWorkspaceSession(nodeId, dirPath)
  if (!created) return
  const { agentId, agent: virtualAgent } = created

  activeWorkspaceSessionId.value = agentId
  showWorkspacePanel.value = true
  setActivePaneView('file')
  showWorkspaceFileView()
  workspaceSidebarView.value = 'files'

  // Initialize the file tree for that directory
  await initFileTree(agentId, virtualAgent.working_dir)
  // Persist the record so it auto-restores after refresh
  saveVirtualWorkspaceDirs()
  showToast(`AlreadyOpenDirectory：${virtualAgent.working_dir}`, 'success')
}

// Remove an opened directory (close its virtual session and clean up file tree state), and sync the persisted records
function removeWorkspaceDir(agentId) {
  const index = workspaceSessions.value.findIndex(s => s.agent_id === agentId)
  if (index === -1) return
  const session = workspaceSessions.value[index]
  if (session.agent?.virtual !== true) return

  // Clean up the file tree / expanded state / loading state for that session
  fileTreeState.value.delete(agentId)
  fileTreeExpanded.value.delete(agentId)
  fileTreeLoading.value.delete(agentId)
  expandedAgents.value.delete(agentId)
  if (fileTreeSelectedAgentId.value === agentId) {
    fileTreeSelectedAgentId.value = null
    fileTreeSelectedPath.value = null
  }
  if (selectedAgentId.value === agentId) selectedAgentId.value = null

  // Release editor models
  session.editorModels?.clear()

  workspaceSessions.value.splice(index, 1)
  // If the removed session is the currently active one, switch to the first remaining session; otherwise clear the active state.
  // Note: only remove this directory entry here; the workspace panel itself remains open (the panel is the container holding the file tree),
  // do not collapse the entire panel as when closing an editor session, otherwise users may think "removing a directory = closing the workspace".
  if (activeWorkspaceSessionId.value === agentId) {
    activeWorkspaceSessionId.value = workspaceSessions.value.length > 0
      ? workspaceSessions.value[0].agent_id
      : null
    if (!activeWorkspaceSessionId.value) {
      // When no sessions remain, only reset the main area view/split/inline session panels; keep the panel open and show the placeholder
      resetWorkspaceHostedPanelState()
    }
  }
  triggerRef(expandedAgents)
  saveVirtualWorkspaceDirs()
  showToast('Already remove Directory', 'success')
}

// Restore last opened directory records after refresh (call after successful connection and auth available)
async function restoreVirtualWorkspaceDirs() {
  const dirs = loadVirtualWorkspaceDirs()
  if (!dirs.length) return
  for (const dir of dirs) {
    const created = ensureVirtualWorkspaceSession(dir.node_id, dir.working_dir)
    if (!created) continue
    // Only restore sessions and file tree; do not preempt the currently active session and do not show a toast
    await initFileTree(created.agentId, created.agent.working_dir)
  }
}


// Close an editor session
async function closeWorkspaceSession(agentId) {
  const sessionIndex = workspaceSessions.value.findIndex(s => s.agent_id === agentId)
  if (sessionIndex === -1) return

  const session = workspaceSessions.value[sessionIndex]

  // check Yes No Has NotSave's Tags
  const hasDirty = session.tabs.some(tab => tab.isDirty)
  if (hasDirty) {
    const confirmed = await new Promise((resolve) => {
      showConfirm(
        `${session.agent_name} 's EditDevice exist at NotSaveModifyModify, Confirm Close?`,
        () => resolve(true),
        () => resolve(false),
        false
      )
    })
    if (!confirmed) return
  }

  // Clean up editor models
  session.editorModels.clear()

  // Remove from the array
  workspaceSessions.value.splice(sessionIndex, 1)

  // If the closed session was the currently active one, switch to another
  if (activeWorkspaceSessionId.value === agentId) {
    activeWorkspaceSessionId.value = workspaceSessions.value.length > 0 ? workspaceSessions.value[0].agent_id : null
    if (!activeWorkspaceSessionId.value) {
      // Consistent with closeWorkspacePanel: when the editor hosts terminal/chat, closing the editor must also collapse its standalone panel states
      resetWorkspaceHostedPanelState()
      showWorkspacePanel.value = false
    }
  }

}

// Switch editor session
function switchWorkspaceSession(agentId) {
  const session = workspaceSessions.value.find(s => s.agent_id === agentId)
  if (!session) return

  activeWorkspaceSessionId.value = agentId
  showWorkspacePanel.value = true
}

function confirmCloseDirtyWorkspaceTab(path) {
  return new Promise((resolve) => {
    showConfirm(
      'thisTags exist at NotSaveModifyModify, Confirm Close?',
      () => resolve(true),
      () => resolve(false),
      false
    )
  })
}

// skipDirtyConfirm: when closing in batch (tab bar context menu), the caller has already confirmed once globally,
// to avoid showing a confirmation dialog per dirty tab.
async function closeWorkspaceTab(path, paneId = null, skipDirtyConfirm = false) {
  const tab = getWorkspaceTabByPath(path)
  if (!tab) return

  if (tab.isDirty && !skipDirtyConfirm) {
    const confirmed = await confirmCloseDirtyWorkspaceTab(path)
    if (!confirmed) return
  }

  // Unified to a pane tree: when pane is specified, remove only from that pane's tab list.
  // If the file is still referenced by other panes, do not destroy the model and do not remove it from global tabs;
  // other panes' editors remain unchanged (this is the key to "closing a tab in one pane does not affect others").
  let closedFromPane = false
  if (paneId) {
    closedFromPane = true
    removePaneTab(paneId, path)
    const panePaths = workspacePaneTabs.get(paneId) || []
    if (workspaceViewPanes.get(paneId) === path) {
      const nextPath = panePaths[panePaths.length - 1] || null
      if (nextPath) {
        activateWorkspaceTab(nextPath)
      } else {
        workspaceViewPanes.delete(paneId)
        const view = editorViews.get(paneId)
        if (view) view.setModel(null)
      }
    }
    if (isPathReferencedByAnyPane(path)) return
    // If no other pane references the file, proceed to global cleanup below (release model / LSP / global tabs)
  }

  const session = activeWorkspaceSession.value
  if (!session) return
  const index = session.tabs.findIndex(item => item.path === path)
  if (index === -1) return

  const wasActive = session.activeTabPath === path
  session.tabs.splice(index, 1)

  const modelData = editorModels.get(path)
  if (modelData) {
    if (modelData.model && !modelData.model.isDisposed()) {
      modelData.model.dispose()
    }
    editorModels.delete(path)
  }

  // Release the LSP client bound to this file (close the connection if no other files are using that server)
  releaseLspBinding(path)

  if (wasActive) {
    const nextTab = session.tabs[index] || session.tabs[index - 1] || null
    // When closing a tab from a pane, that pane's "next tab / clear" has already been handled above;
    // activating the global next tab here would incorrectly bind another pane's file to this pane.
    if (closedFromPane) {
      // The pane's view has been handled above; here we only correct the global "active file" to a still-existing tab,
      // to prevent it from pointing to a deleted path.
      session.activeTabPath = nextTab ? nextTab.path : null
    } else if (nextTab) {
      activateWorkspaceTab(nextTab.path)
    } else {
      session.activeTabPath = null
      // Do not destroy the editor instance; keep the editor and container DOM,
      // otherwise v-if/v-else toggling will make editorContainerRef disappear,
      // and subsequent file opens cannot recreate the editor.
      // Just clear the model (all pane instances will be cleared together).
      for (const [pid, view] of editorViews) {
        view.setModel(null)
        workspaceViewPanes.delete(pid)
      }
    }
  }
}

// ===== Editor tab bar context menu: Close to the right / Close all / Keep current only =====
// paneId is null for the non-split state (tab bar is driven by global workspaceTabs and rendered in WorkspacePanel.vue);
// otherwise it is the independent tab list of that pane (getPaneTabs).
const tabContextMenu = ref({ visible: false, x: 0, y: 0, paneId: null, path: '' })

function closeTabContextMenu() {
  if (tabContextMenu.value.visible) {
    tabContextMenu.value = { ...tabContextMenu.value, visible: false }
  }
}

function openTabContextMenu(paneId, path, event) {
  if (!path) return
  tabContextMenu.value = {
    visible: true,
    x: event?.clientX || 0,
    y: event?.clientY || 0,
    paneId: paneId || null,
    path,
  }
  // Close when clicking blank area (same as file tree context menu: unbind on pointerdown once)
  document.addEventListener('pointerdown', closeTabContextMenu, { once: true })
}

// Tab path list corresponding to the current context menu (in display order)
function getTabContextPaths() {
  const menu = tabContextMenu.value
  if (menu.paneId) return getPaneTabs(menu.paneId).map(t => t.path)
  return workspaceTabs.value.map(t => t.path)
}

const tabContextActions = computed(() => {
  const paths = getTabContextPaths()
  const index = paths.indexOf(tabContextMenu.value.path)
  const hasRight = index >= 0 && index < paths.length - 1
  const hasOthers = paths.length > 1
  const canReveal = !!resolveAgentForPath(tabContextMenu.value.path)
  return [
    { id: 'reveal-in-tree', icon: '⌖', label: ' at File tree Middle Show', enabled: canReveal },
    { id: 'close-right', icon: '⇥', label: 'Close Right side all Has', enabled: hasRight },
    { id: 'close-all', icon: '✕', label: 'Close all Has', enabled: hasOthers },
    { id: 'keep-current', icon: '◎', label: 'only keep Current', enabled: hasOthers },
  ]
})

async function runTabContextAction(act) {
  if (!act || act.enabled === false) return
  const menu = { ...tabContextMenu.value }
  const paneId = menu.paneId
  const paths = getTabContextPaths()
  const index = paths.indexOf(menu.path)
  if (index === -1) {
    closeTabContextMenu()
    return
  }

  let targets = []
  if (act.id === 'reveal-in-tree') {
    closeTabContextMenu()
    await revealTabInFileTree(menu.path)
    return
  }
  if (act.id === 'close-right') {
    targets = paths.slice(index + 1)
  } else if (act.id === 'close-all') {
    targets = paths.slice()
  } else if (act.id === 'keep-current') {
    targets = paths.filter(p => p !== menu.path)
  }
  closeTabContextMenu()
  if (!targets.length) return

  // Batch close: if any tab is unsaved, confirm once globally (to avoid per-tab dialogs)
  const dirtyCount = targets.filter(p => getWorkspaceTabByPath(p)?.isDirty).length
  if (dirtyCount > 0) {
    const confirmed = await new Promise((resolve) => {
      showConfirm(
        `Has ${dirtyCount} items Tags exist at NotSave Modify Modify, Confirm Close?`,
        () => resolve(true),
        () => resolve(false),
        false
      )
    })
    if (!confirmed) return
  }

  // Close one by one (closeWorkspaceTab already handles model/LSP/pane binding cleanup);
  // Dirty tabs were confirmed globally above; skip per-tab confirmation here.
  for (const path of targets) {
    await closeWorkspaceTab(path, paneId, true)
  }
}

// Locate and highlight an opened file in the left file tree (similar to VS Code's Reveal in Explorer):
// 1) Find the Agent/virtual directory session that owns the file; 2) Open the sidebar and switch to the "Files" view;
// 3) Expand the Agent node; 4) Expand directories level by level along the path (load child nodes on demand if needed);
// 5) Select and scroll to that file node.

// Common UI icons (self-drawn stroke linear SVGs, currentColor inherits theme color)
const UI_ICONS = {
  folder: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 4.5v7a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H8.2L6.7 4.5H2.5a1 1 0 0 0-1 1z"/></svg>',
  monitor: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2.5" width="12" height="8.5" rx="1.5"/><path d="M6 13.5h4M8 11v2.5"/></svg>',
  search: '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3.5 3.5"/></svg>',
  save: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 2.5h9l1.5 1.5v9.5a1 1 0 0 1-1 1h-10a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1z"/><path d="M5 2.5v4h5v-4M5 13.5v-5h6v5"/></svg>',
  lock: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/></svg>',
  unlock: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 4.9-.8"/></svg>',
  receipt: '<svg viewBox="0 0 16 16" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 1.5h8v13l-1.5-1-1.5 1-1.5-1-1.5 1-1.5-1z"/><path d="M6 5.5h4M6 8h4M6 10.5h2.5"/></svg>',
  folderStack: '<svg viewBox="0 0 16 16" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 4.5v7a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H8.2L6.7 4.5H3.5a1 1 0 0 0-1 1z"/><path d="M5 13v.5a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V7.5"/></svg>',
  eye: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/></svg>',
  eyeOff: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><path d="M4 4 12 12M8 6.5a1.5 1.5 0 0 1 1.5 1.5"/></svg>',
}
// Fine-grained extension → icon file mapping (icons from material-icon-theme in public/file-icons/)

// Get currently selected text to prefill the global search input when opening search.
// Prefer the Monaco editor selection (when the editor is focused), otherwise fall back to the page DOM selection
// (e.g. text selected in session output/chat content). Returns a single-line text with collapsed whitespace; empty string if nothing selected.
function getSelectedTextForSearch() {
  let raw = ''
  const view = getActiveWorkspaceView()
  if (view && typeof view.getSelection === 'function') {
    const selection = view.getSelection()
    const model = view.getModel()
    if (selection && model && !selection.isEmpty()) {
      raw = model.getValueInRange(selection)
    }
  }
  if (!raw) {
    const domSelection = window.getSelection && window.getSelection()
    if (domSelection) raw = domSelection.toString()
  }
  // The search input is single-line: collapse newlines and consecutive whitespace in the selection to a single space to avoid multi-line content breaking the query
  return raw.replace(/\s+/g, ' ').trim()
}

// Switch to global search in the editor sidebar and focus the input box (mode: 'content' for content search, 'filename' for filename search).
// if Current Has Selected text, then prefill to Search box (Selected Content priority in Original Has Query query).
function openWorkspaceGlobalSearch(mode = 'content') {
  if (!showWorkspacePanel.value) return
  setWorkspaceSidebarView('search')
  setGlobalSearchMode(mode)
  const selectedText = getSelectedTextForSearch()
  if (selectedText) globalSearchQuery.value = selectedText
  nextTick(() => {
    const input = document.querySelector('.workspace-global-search-input')
    if (input) input.focus()
  })
}
  return {
    EDITOR_FONT_FAMILY,
    UI_ICONS,
    activateWorkspaceTab,
    activeWorkspaceTab,
    bindWorkspaceViewEvents,
    clamp,
    clearGlobalSearch,
    closeWorkspacePanel,
    closeWorkspaceSidebar,
    closeWorkspaceTab,
    createWorkspaceForAgent,
    diffContainerRefs,
    diffEditorViews,
    editorViews,
    ensureMonacoEditor,
    ensureWorkspacePanelInViewport,
    ensureWorkspaceSidebarFileTree,
    fetchFileContent,
    fetchFileSearchResults,
    focusWindow,
    getActiveWorkspaceView,
    getPaneTabs,
    getVirtualWorkspaceAgent,
    getWorkspaceTabByPath,
    hideWorkspaceHostedPanelState,
    layoutMonacoEditor,
    lspBindings,
    openFileSearchResult,
    openGlobalSearchResult,
    openTabContextMenu,
    openWorkspaceDir,
    openWorkspaceFile,
    openWorkspaceGlobalSearch,
    remountMonacoEditor,
    removeWorkspaceDir,
    resolveAgentForPath,
    resolveAgentRelativePath,
    resolveDiffContainer,
    resolveFileTreeAgent,
    restoreVirtualWorkspaceDirs,
    runGlobalSearch,
    runTabContextAction,
    saveActiveWorkspaceTab,
    savePaneWorkspaceFile,
    scheduleWorkspaceLayout,
    setDiffContainerRef,
    setGlobalSearchMode,
    setWorkspaceMainView,
    setWorkspaceSidebarView,
    showWorkspaceHostView,
    startWorkspaceFileHeartbeat,
    startWorkspacePanelMove,
    startWorkspacePanelResize,
    startWorkspaceSidebarResize,
    stopWorkspaceFileHeartbeat,
    stopWorkspacePanelInteraction,
    tabContextActions,
    tabContextMenu,
    toggleWorkspaceEditable,
    toggleWorkspaceMainView,
    toggleWorkspaceMaximize,
    toggleWorkspaceSidebarView,
    workspacePaneTabs,
    workspacePaneTabsVersion,
    workspacePanelStyle,
    workspaceViewPanes,
  }
}
