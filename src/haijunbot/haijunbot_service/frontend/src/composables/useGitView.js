// Git view + diff pane composable for the editor sidebar.
//
// Extracted from App.vue's <script setup> (former Git view / diff pane multi-instance management domain, lines 6503-7202)
// while preserving identical behavior:
// - Git view state: gitLog / gitLogLoading / gitLogError / gitLogHasMore / gitLogTotal /
//   gitBranches / gitTags / gitCurrentBranch / gitSelectedCommit / gitRangeSelectMode /
//   gitSelectedCommits / gitPatchLoading / gitCommitFiles / gitCommitDetailLoading /
//   gitSelectedFile / gitDiffText / gitDiffLoading / gitDiffError / gitDiffTruncated /
//   gitDiffSideBySide / gitDiffShowFull / pluginSidebarWorkingDir / pluginActiveAgentInfo /
//   gitCommitContextMenu / gitCommitInfoModal / GIT_LOG_PAGE_SIZE
// - target Agent resolution: isNarrowGitDiffViewport / getGitTargetAgent / getGitTargetNodeId / getGitWorkingDir
// - backend calls: callGitApi / fetchGitLog / fetchGitBranches / refreshGitView / toggleGitCommitDetail
// - range selection: enterGitRangeSelect / exitGitRangeSelect / toggleGitRangeSelect / downloadGitPatch
// - diff opening: viewGitTargetDiff / onDiffTitleClick / onOpenDiffFileFromMessage / viewGitFileDiff
// - diff full text: gitDiffFullTextCache / ensureGitDiffFullText / gitDiffOldText / gitDiffNewText
// - diff pane multi-instance: layoutGitDiffEditor / disposeDiffEditorForPane / disposeAllDiffEditors /
//   ensureDiffEditorForPane / renderDiffForPane / loadDiffForPane / togglePaneDiffSideBySide /
//   togglePaneDiffShowFull / navigatePaneDiff / closePaneDiff / scheduleDiffLayout
// - display utilities: gitRefClass / gitFileStatus / formatGitRelativeTime / shortGitHash
// - commit context menu: closeGitCommitContextMenu / openGitCommitContextMenu / copyGitCommit /
//   copyGitCommitId / formatGitCommitInfo / formatGitCommitTooltip / showGitCommitInfoModal
//
// Dependency injection (the caller passes these in setup; must be called after their definition):
// - direct (defined before this composable's call site): EDITOR_FONT_FAMILY / buildNodeHttpUrl /
//   fetchWithAuth / getGatewayAddress / getLanguageExtension / getLanguageFromFilename /
//   windowWidth / activeWorkspaceSessionId / ensurePaneForView / findWorkspacePaneById /
//   gitCustomDir / persistWorkspacePaneLayout / resolveDiffContainer / scheduleWorkspaceLayout /
//   showWorkspacePanel / workspacePaneTree / workspaceSidebarView / diffContainerRefs /
//   diffEditorViews / openWorkspaceFile / activePane / getPanePanel
// - getter injection (defined after the call site, evaluated internally via () => xxx): effectiveGitAgentId /
//   agentList / showToast / viewDiff / copyTextToClipboard / getPanelAgent / getCurrentAgentOrNull
import { computed, nextTick, ref, triggerRef, watch } from 'vue'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.main.js'
import { parseUnifiedDiff, extractDiffContext } from '../gitDiffParser.js'

export function useGitView({
  EDITOR_FONT_FAMILY,
  buildNodeHttpUrl,
  fetchWithAuth,
  getGatewayAddress,
  getLanguageExtension,
  getLanguageFromFilename,
  windowWidth,
  activeWorkspaceSessionId,
  ensurePaneForView,
  findWorkspacePaneById,
  gitCustomDir,
  persistWorkspacePaneLayout,
  resolveDiffContainer,
  scheduleWorkspaceLayout,
  showWorkspacePanel,
  workspacePaneTree,
  workspaceSidebarView,
  diffContainerRefs,
  diffEditorViews,
  openWorkspaceFile,
  activePane,
  getPanePanel,
  effectiveGitAgentId,
  agentList,
  showToast,
  viewDiff,
  copyTextToClipboard,
  getPanelAgent,
  getCurrentAgentOrNull,
}) {

// ===== Editor sidebar Git view (read-only: commit history / detail / diff / branches) =====
const gitLog = ref([])                 // commit list
const gitLogLoading = ref(false)
const gitLogError = ref('')
const gitLogHasMore = ref(false)
const gitLogTotal = ref(null)          // actual total commits in the repo (backend rev-list --count, returned on the first page)
const gitBranches = ref([])            // branch list
const gitTags = ref([])                // tag list
const gitCurrentBranch = ref('')       // current branch
const gitSelectedCommit = ref(null)    // hash of the commit whose detail is expanded
const gitRangeSelectMode = ref(false)  // whether range-selection mode is active
const gitSelectedCommits = ref(new Set()) // set of selected commit hashes in range-selection mode
const gitPatchLoading = ref(false)     // downloading a patch in progress
const gitCommitFiles = ref([])         // list of files changed in that commit
const gitCommitDetailLoading = ref(false)
const gitSelectedFile = ref(null)      // path of the file whose diff is currently being viewed
const gitDiffText = ref('')
const gitDiffLoading = ref(false)
const gitDiffError = ref('')
const gitDiffTruncated = ref(false)
// Monaco DiffEditor: side-by-side / inline toggle (desktop defaults to side-by-side; mobile screens are narrow, so default inline)
const gitDiffSideBySide = ref(window.innerWidth > 768)
// diff display scope: false=only changed context regions (default), true=full file text
const gitDiffShowFull = ref(false)

// Whether currently on a narrow screen (mobile): force inline diff to avoid the two side-by-side panes being cut off
function isNarrowGitDiffViewport() {
  return windowWidth.value <= 768
}
const GIT_LOG_PAGE_SIZE = 100

// Target Agent for the Git view: prefers the Agent selected in the Git sidebar itself (gitAgentId);
// when none is explicitly selected, falls back to the global current Agent. Independent of editor sessions and global search.
function getGitTargetAgent() {
  const agentId = effectiveGitAgentId().value
  return agentList().value.find(a => a.agent_id === agentId) || null
}

// Get the target Agent's node_id (custom Git directory first, otherwise the target Agent's node_id)
function getGitTargetNodeId() {
  if (gitCustomDir.value?.nodeId) return String(gitCustomDir.value.nodeId).trim()
  return String(getGitTargetAgent()?.node_id || '').trim()
}

// Get the Git working directory (custom Git directory first, otherwise the target Agent's working_dir)
function getGitWorkingDir() {
  if (gitCustomDir.value?.path) return String(gitCustomDir.value.path).trim()
  return String(getGitTargetAgent()?.working_dir || '').trim()
}

// Plugin sidebars (e.g. gh) follow the Git panel's target working directory to resolve the current repo
const pluginSidebarWorkingDir = computed(() => getGitWorkingDir())
// Active Agent info injected into plugin sidebars (same source as __haijunbotGetActiveAgentInfo: Git target Agent first)
const pluginActiveAgentInfo = computed(() => {
  const agentId = effectiveGitAgentId().value
  const agent = agentId ? (agentList().value.find(a => a.agent_id === agentId) || null) : null
  return agent
    ? {
        agentId: agent.agent_id,
        agentName: agent.name || agent.agent_id,
        workingDir: agent.working_dir || '',
      }
    : null
})

// Call a read-only backend Git API
async function callGitApi(apiPath, payload) {
  const { host, port } = getGatewayAddress()
  const targetNodeId = getGitTargetNodeId() || 'master'
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, apiPath), {
    method: 'POST',
    body: JSON.stringify({ ...payload, node_id: targetNodeId }),
  })
  const result = await response.json()
  if (!response.ok || !result.success || !result.data) {
    throw new Error(result.error?.message || 'Git request failed')
  }
  return result.data
}

// Fetch commit history
async function fetchGitLog(append = false) {
  const workingDir = getGitWorkingDir()
  if (!workingDir) {
    gitLogError.value = 'The current Agent has no working directory'
    gitLog.value = []
    gitLogTotal.value = null
    return
  }
  gitLogLoading.value = true
  gitLogError.value = ''
  try {
    const skip = append ? gitLog.value.length : 0
    const data = await callGitApi('git/log', {
      path: workingDir,
      limit: GIT_LOG_PAGE_SIZE,
      skip,
    })
    const commits = Array.isArray(data.commits) ? data.commits : []
    gitLog.value = append ? [...gitLog.value, ...commits] : commits
    gitLogHasMore.value = Boolean(data.has_more)
    if (typeof data.total === 'number') {
      gitLogTotal.value = data.total
    }
  } catch (error) {
    gitLogError.value = error.message || 'Failed to fetch commit history'
    if (!append) {
      gitLog.value = []
      gitLogTotal.value = null
    }
  } finally {
    gitLogLoading.value = false
  }
}

// Fetch branch / tag lists
async function fetchGitBranches() {
  const workingDir = getGitWorkingDir()
  if (!workingDir) return
  try {
    const data = await callGitApi('git/branches', { path: workingDir })
    gitBranches.value = Array.isArray(data.branches) ? data.branches : []
    gitTags.value = Array.isArray(data.tags) ? data.tags : []
    gitCurrentBranch.value = data.current || ''
  } catch (error) {
    // A branch info failure should not block the commit history display
    gitBranches.value = []
    gitTags.value = []
    gitCurrentBranch.value = ''
  }
}

// When the editor panel switches Agent, if still in the Git view, re-fetch based on the new Agent's working directory
watch(activeWorkspaceSessionId, () => {
  if (!showWorkspacePanel.value || workspaceSidebarView.value !== 'git') return
  nextTick(() => {
    refreshGitView()
  })
})

// Refresh the Git view (history + branches)
async function refreshGitView() {
  gitSelectedCommit.value = null
  gitCommitFiles.value = []
  gitSelectedFile.value = null
  gitDiffText.value = ''
  gitDiffError.value = ''
  await Promise.all([fetchGitLog(false), fetchGitBranches()])
}

// Expand a commit's detail (changed file list)
async function toggleGitCommitDetail(commit) {
  if (gitSelectedCommit.value === commit.hash) {
    gitSelectedCommit.value = null
    gitCommitFiles.value = []
    gitSelectedFile.value = null
    gitDiffText.value = ''
    return
  }
  gitSelectedCommit.value = commit.hash
  gitCommitFiles.value = []
  gitSelectedFile.value = null
  gitDiffText.value = ''
  gitDiffError.value = ''
  const workingDir = getGitWorkingDir()
  if (!workingDir) return
  gitCommitDetailLoading.value = true
  try {
    const data = await callGitApi('git/commit-detail', { path: workingDir, hash: commit.hash })
    gitCommitFiles.value = Array.isArray(data.files) ? data.files : []
  } catch (error) {
    gitDiffError.value = error.message || 'Failed to fetch commit detail'
  } finally {
    gitCommitDetailLoading.value = false
  }
}

// Enter range-selection mode: clear selections and exit detail expansion
function enterGitRangeSelect() {
  gitRangeSelectMode.value = true
  gitSelectedCommits.value = new Set()
  gitSelectedCommit.value = null
  gitCommitFiles.value = []
  gitSelectedFile.value = null
  gitDiffText.value = ''
}

// Exit range-selection mode
function exitGitRangeSelect() {
  gitRangeSelectMode.value = false
  gitSelectedCommits.value = new Set()
}

// Toggle a commit's selection state in range-selection mode
function toggleGitRangeSelect(commit) {
  const set = gitSelectedCommits.value
  if (set.has(commit.hash)) {
    set.delete(commit.hash)
  } else {
    set.add(commit.hash)
  }
  // Trigger a reactive update
  gitSelectedCommits.value = new Set(set)
}

// Download a patch: a single commit as .patch, multiple as .tar.gz
async function downloadGitPatch() {
  const workingDir = getGitWorkingDir()
  if (!workingDir) return
  const commits = Array.from(gitSelectedCommits.value)
  if (!commits.length) {
    showToast()('Please select at least one commit first', 'error')
    return
  }
  gitPatchLoading.value = true
  try {
    const data = await callGitApi('git/patch', { path: workingDir, commits })
    if (!data || !data.format || !data.filename) {
      throw new Error('Invalid patch data')
    }
    let blob
    if (data.format === 'tar.gz') {
      // base64 → binary
      const binary = atob(data.content_base64)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
      blob = new Blob([bytes], { type: 'application/gzip' })
    } else {
      blob = new Blob([data.content], { type: 'text/plain;charset=utf-8' })
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = data.filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showToast()(`Downloaded ${data.filename}`, 'success')
  } catch (error) {
    showToast()(error.message || 'Failed to download patch', 'error')
  } finally {
    gitPatchLoading.value = false
  }
}

// View the current Git target Agent's changes in the Git sidebar (opens the diff floating window)
function viewGitTargetDiff() {
  const agent = getGitTargetAgent()
  if (!agent) {
    showToast()('Please select a Git target Agent first', 'error')
    return
  }
  viewDiff()(agent)
}

// Diff title file name: clicking it opens that file in the editor panel.
// The diff's filePath is relative to the Git working directory and must be joined into an absolute path first.
async function onDiffTitleClick(event, pane) {
  const filePath = pane?.diff?.filePath
  if (!filePath) return
  const workingDir = getGitWorkingDir()
  if (!workingDir) return
  const absPath = filePath.startsWith('/')
    ? filePath
    : `${workingDir.replace(/\/$/, '')}/${filePath.replace(/^\//, '')}`
  event.preventDefault()
  event.stopPropagation()
  await openWorkspaceFile(absPath, effectiveGitAgentId().value)
}

// Open an embedded diff file path from a chat message on click:
// the diff's file_path is usually relative, so join it with the Agent's working_dir into an absolute
// path and hand it to the editor. Falls back to the Git target working directory when none is found.
async function onOpenDiffFileFromMessage(filePath) {
  if (!filePath) return
  // Locate the panel hosting that session: prefer the session panel of the currently active pane
  const pane = activePane.value
  const panel = pane && pane.view === 'session' ? getPanePanel(pane) : null
  const agent = getPanelAgent()(panel) || getCurrentAgentOrNull()()
  const workingDir = String(agent?.working_dir || '').trim() || getGitWorkingDir()
  const absPath = filePath.startsWith('/')
    ? filePath
    : (workingDir ? `${workingDir.replace(/\/$/, '')}/${filePath.replace(/^\//, '')}` : filePath)
  await openWorkspaceFile(absPath, agent?.agent_id || effectiveGitAgentId().value)
}

// View a file's diff in a given commit.
// By default only the changed context regions are shown, so only the diff text is requested first (fast); the full text loads lazily on demand.
async function viewGitFileDiff(commitHash, filePath) {
  const workingDir = getGitWorkingDir()
  if (!workingDir) return
  gitSelectedFile.value = filePath
  gitDiffText.value = ''
  gitDiffError.value = ''
  gitDiffTruncated.value = false
  gitDiffLoading.value = true
  // Clear the previous file's full-text cache variables to avoid accidentally using stale full text in "context-only" mode
  gitDiffOldText = ''
  gitDiffNewText = ''
  // Diff opens as a "pane view" (same strategy as file/session/chat/terminal, regardless of splitting):
  // reuse an existing diff pane, create in place if the current area is empty, otherwise split the
  // largest pane, avoiding overwriting current area content. Each pane gets its own DiffEditor instance.
  const paneId = ensurePaneForView('diff')
  const pane = paneId ? findWorkspacePaneById(workspacePaneTree.value, paneId) : null
  if (pane) {
    // When switching from diff to diff (different file), dispose the old instance first to avoid reusing stale models
    disposeDiffEditorForPane(pane.id)
    pane.view = 'diff'
    pane.sessionPanelId = null
    persistWorkspacePaneLayout()
    gitDiffLoading.value = false
    await loadDiffForPane(pane.id, commitHash, filePath)
    return
  }
  // Unsplitted with in-place creation (ensurePaneForView returns null): the single leaf is the main
  // area, the diff is carried by that leaf, handled through the pane path uniformly.
  const root = workspacePaneTree.value
  if (root && root.type === 'leaf') {
    disposeDiffEditorForPane(root.id)
    root.view = 'diff'
    root.sessionPanelId = null
    persistWorkspacePaneLayout()
    gitDiffLoading.value = false
    await loadDiffForPane(root.id, commitHash, filePath)
    return
  }
}

// Lazily load both sides' full text for a file in a commit (parent / current version), with cache
const gitDiffFullTextCache = new Map() // key: `${commitHash}|${filePath}` -> { oldText, newText, truncated }
async function ensureGitDiffFullText(commitHash, filePath) {
  const key = `${commitHash}|${filePath}`
  const cached = gitDiffFullTextCache.get(key)
  if (cached) {
    gitDiffOldText = cached.oldText
    gitDiffNewText = cached.newText
    return cached
  }
  const workingDir = getGitWorkingDir()
  if (!workingDir) return null
  const [newData, oldData] = await Promise.all([
    callGitApi('git/file-content', { path: workingDir, ref: commitHash, file: filePath }),
    // Parent version: on newly added files the parent does not exist; the backend returns NOT_FOUND, so treat as an empty file
    callGitApi('git/file-content', { path: workingDir, ref: `${commitHash}^`, file: filePath })
      .catch(() => ({ content: '', truncated: false })),
  ])
  const entry = {
    oldText: oldData.content || '',
    newText: newData.content || '',
    truncated: Boolean(newData.truncated || oldData.truncated),
  }
  gitDiffFullTextCache.set(key, entry)
  gitDiffOldText = entry.oldText
  gitDiffNewText = entry.newText
  return entry
}

// Full text of both sides (provided by git/file-content)
let gitDiffOldText = ''
let gitDiffNewText = ''

// Re-layout when the sidebar size/view changes (reusing the main editor's layout timing)
function layoutGitDiffEditor() {
  for (const [, entry] of diffEditorViews) {
    if (entry.editor && entry.editor.getContainerDomNode?.()?.isConnected) entry.editor.layout()
  }
}

// ===== Free splitting: multi-instance management of diff panes =====
// Each diff pane gets its own Monaco DiffEditor; diff data hangs on leaf.diff (commitHash/filePath/loading/error/truncated/sideBySide/showFull).

// Dispose a diff pane's editor instance and models
function disposeDiffEditorForPane(paneId) {
  const entry = diffEditorViews.get(paneId)
  if (!entry) return
  if (entry.originalModel && !entry.originalModel.isDisposed()) entry.originalModel.dispose()
  if (entry.modifiedModel && !entry.modifiedModel.isDisposed()) entry.modifiedModel.dispose()
  if (entry.editor) entry.editor.dispose()
  diffEditorViews.delete(paneId)
}

// Dispose all diff pane instances (called when collapsing the split / closing the editor)
function disposeAllDiffEditors() {
  for (const paneId of [...diffEditorViews.keys()]) disposeDiffEditorForPane(paneId)
  diffContainerRefs.value.clear()
  triggerRef(diffContainerRefs)
}

// Ensure a diff pane's editor instance exists (destroy and recreate when the container is replaced)
function ensureDiffEditorForPane(paneId) {
  const container = resolveDiffContainer(paneId)
  if (!container) return null
  let entry = diffEditorViews.get(paneId)
  if (entry && entry.editor && entry.editor.getContainerDomNode() !== container) {
    disposeDiffEditorForPane(paneId)
    entry = null
  }
  if (entry) return entry
  const editor = monaco.editor.createDiffEditor(container, {
    theme: 'blueDark',
    fontFamily: EDITOR_FONT_FAMILY,
    fontSize: 12,
    lineHeight: 18,
    readOnly: true,
    originalEditable: false,
    automaticLayout: true,
    renderSideBySide: gitDiffSideBySide.value && !isNarrowGitDiffViewport(),
    useInlineViewWhenSpaceIsLimited: isNarrowGitDiffViewport(),
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    renderOverviewRuler: false,
    renderWhitespace: 'selection',
    smoothScrolling: true,
    folding: false,
    lineNumbersMinChars: 3,
    wordWrap: isNarrowGitDiffViewport() ? 'on' : 'off',
  })
  entry = { editor, originalModel: null, modifiedModel: null, oldText: '', newText: '' }
  diffEditorViews.set(paneId, entry)
  return entry
}

// Render Monaco with the pane's diff data (poll-wait when the container is not ready)
async function renderDiffForPane(paneId) {
  const pane = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (!pane || pane.view !== 'diff' || !pane.diff) return
  let container = resolveDiffContainer(paneId)
  for (let i = 0; !container && i < 10; i++) {
    await new Promise(resolve => setTimeout(resolve, 50))
    container = resolveDiffContainer(paneId)
  }
  if (!container) return
  // The pane may have been switched away or closed while waiting
  const current = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (!current || current.view !== 'diff' || !current.diff) return
  const diff = current.diff
  try {
    const entry = ensureDiffEditorForPane(paneId)
    if (!entry) return
    const language = getLanguageExtension(getLanguageFromFilename(diff.filePath))
    let oldText = entry.oldText
    let newText = entry.newText
    if (!oldText && !newText) {
      const parsed = parseUnifiedDiff(diff.diffText || '', { absoluteLineNumbers: true })
      oldText = parsed.oldText
      newText = parsed.newText
    }
    // By default, only show the changed context regions
    if (!diff.showFull && diff.diffText) {
      const context = extractDiffContext(diff.diffText)
      if (context.oldText || context.newText) {
        oldText = context.oldText
        newText = context.newText
      }
    }
    if (entry.originalModel && !entry.originalModel.isDisposed()) entry.originalModel.dispose()
    if (entry.modifiedModel && !entry.modifiedModel.isDisposed()) entry.modifiedModel.dispose()
    entry.originalModel = monaco.editor.createModel(oldText, language)
    entry.modifiedModel = monaco.editor.createModel(newText, language)
    entry.editor.setModel({ original: entry.originalModel, modified: entry.modifiedModel })
    entry.editor.updateOptions({ renderSideBySide: diff.sideBySide && !isNarrowGitDiffViewport() })
    entry.editor.layout()
  } catch (error) {
    console.warn('[GIT] render pane diff with monaco failed:', error)
    diff.error = `Failed to render diff: ${error?.message || error}`
  }
}

// Load and render a diff for a pane (called after writing leaf.diff)
async function loadDiffForPane(paneId, commitHash, filePath) {
  const pane = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (!pane || pane.view !== 'diff') return
  const workingDir = getGitWorkingDir()
  if (!workingDir) return
  pane.diff = {
    commitHash,
    filePath,
    diffText: '',
    loading: true,
    error: '',
    truncated: false,
    sideBySide: gitDiffSideBySide.value,
    showFull: gitDiffShowFull.value,
  }
  try {
    const diffData = await callGitApi('git/diff', { path: workingDir, hash: commitHash, file: filePath })
// While waiting, the pane may have been switched away or closed
    const current = findWorkspacePaneById(workspacePaneTree.value, paneId)
    if (!current || current.view !== 'diff' || !current.diff) return
    current.diff.diffText = diffData.diff || ''
    current.diff.truncated = Boolean(diffData.truncated)
    if (current.diff.showFull) {
      const entry = await ensureGitDiffFullText(commitHash, filePath)
      if (entry) current.diff.truncated = Boolean(current.diff.truncated || entry.truncated)
      const e = diffEditorViews.get(paneId)
      if (e) { e.oldText = gitDiffOldText; e.newText = gitDiffNewText }
    }
    current.diff.loading = false
    await nextTick()
    await renderDiffForPane(paneId)
  } catch (error) {
    const current = findWorkspacePaneById(workspacePaneTree.value, paneId)
    if (current && current.diff) {
      current.diff.loading = false
      current.diff.error = error.message || 'Failed to fetch diff'
    }
  }
}

// Toggle "side-by-side / inline" within a diff pane
function togglePaneDiffSideBySide(paneId) {
  const pane = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (!pane || !pane.diff) return
  pane.diff.sideBySide = !pane.diff.sideBySide
  const entry = diffEditorViews.get(paneId)
  if (entry) entry.editor.updateOptions({ renderSideBySide: pane.diff.sideBySide && !isNarrowGitDiffViewport() })
}

// Toggle "full text / context-only" within a diff pane
async function togglePaneDiffShowFull(paneId) {
  const pane = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (!pane || !pane.diff) return
  pane.diff.showFull = !pane.diff.showFull
  const entry = diffEditorViews.get(paneId)
  if (pane.diff.showFull) {
    const { commitHash, filePath } = pane.diff
    const key = `${commitHash}|${filePath}`
    if (!gitDiffFullTextCache.has(key)) {
      pane.diff.loading = true
      try {
        const full = await ensureGitDiffFullText(commitHash, filePath)
        if (full) pane.diff.truncated = Boolean(pane.diff.truncated || full.truncated)
      } catch (error) {
        pane.diff.error = error.message || 'Failed to fetch file full text'
        pane.diff.loading = false
        return
      } finally {
        pane.diff.loading = false
      }
    } else {
      await ensureGitDiffFullText(commitHash, filePath)
    }
    if (entry) { entry.oldText = gitDiffOldText; entry.newText = gitDiffNewText }
    await nextTick()
  } else if (entry) {
    // Switching back to "context-only": clear the full-text cache variables to avoid stale full text
    entry.oldText = ''
    entry.newText = ''
  }
  await renderDiffForPane(paneId)
}

// Jump to the previous / next difference within a diff pane
function navigatePaneDiff(paneId, direction) {
  const entry = diffEditorViews.get(paneId)
  if (!entry || !entry.editor) return
  const target = direction === 'prev' ? 'previous' : 'next'
  if (typeof entry.editor.goToDiff === 'function') entry.editor.goToDiff(target)
}

// Close a diff pane's diff (back to an empty pane)
function closePaneDiff(paneId) {
  const pane = findWorkspacePaneById(workspacePaneTree.value, paneId)
  if (!pane) return
  disposeDiffEditorForPane(paneId)
  pane.diff = null
  pane.view = 'empty'
  persistWorkspacePaneLayout()
  nextTick(() => scheduleWorkspaceLayout())
}

// Coalesce explicit layouts into the next frame to avoid repeated layout of many diff instances in one frame causing size oscillation
let diffLayoutScheduled = false
function scheduleDiffLayout() {
  if (diffLayoutScheduled) return
  diffLayoutScheduled = true
  requestAnimationFrame(() => {
    diffLayoutScheduled = false
    for (const [, entry] of diffEditorViews) {
      if (entry.editor && entry.editor.getContainerDomNode?.()?.isConnected) entry.editor.layout()
    }
  })
}

// refs label in commit info: distinguish HEAD / branch / tag styles
function gitRefClass(refName) {
  if (refName.startsWith('HEAD')) return 'git-ref-head'
  if (refName.startsWith('tag:')) return 'git-ref-tag'
  return 'git-ref-branch'
}

// Infer the file change status from added/deleted line counts (the backend only returns add/delete stats, no status)
function gitFileStatus(file) {
  const additions = Number(file?.additions) || 0
  const deletions = Number(file?.deletions) || 0
  if (additions > 0 && deletions === 0) return 'A'
  if (deletions > 0 && additions === 0) return 'D'
  return 'M'
}

// Relative commit time (e.g. 3 minutes ago)
function formatGitRelativeTime(isoDate) {
  const time = Date.parse(isoDate)
  if (!time) return ''
  const diffSeconds = Math.floor((Date.now() - time) / 1000)
  if (diffSeconds < 60) return 'just now'
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)} minutes ago`
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)} hours ago`
  if (diffSeconds < 2592000) return `${Math.floor(diffSeconds / 86400)} days ago`
  if (diffSeconds < 31536000) return `${Math.floor(diffSeconds / 2592000)} months ago`
  return `${Math.floor(diffSeconds / 31536000)} years ago`
}

// Short hash (first 7 characters)
function shortGitHash(hash) {
  return String(hash || '').slice(0, 7)
}


// ===== Editor directory tree context menu =====

// ===== Git commit context menu =====
const gitCommitContextMenu = ref({ visible: false, x: 0, y: 0, commit: null })

function closeGitCommitContextMenu() {
  if (gitCommitContextMenu.value.visible) {
    gitCommitContextMenu.value = { ...gitCommitContextMenu.value, visible: false }
  }
}

// Right-click on a Git commit item: pop up the menu in place (viewport coordinates + edge clamping)
function openGitCommitContextMenu(commit, event) {
  if (!commit || !event) return
  const MENU_W = 220
  const MENU_H = 120
  let x = event.clientX
  let y = event.clientY
  if (x + MENU_W > window.innerWidth) x = Math.max(window.innerWidth - MENU_W, 0)
  if (y + MENU_H > window.innerHeight) y = Math.max(window.innerHeight - MENU_H, 0)
  gitCommitContextMenu.value = { visible: true, x, y, commit }
  // Close when clicking outside the menu (one-time listener)
  nextTick(() => {
    document.addEventListener('pointerdown', closeGitCommitContextMenu, { once: true })
  })
}

// Copy the full commit info to the clipboard
async function copyGitCommit(commit) {
  if (!commit) return
  closeGitCommitContextMenu()
  try {
    await copyTextToClipboard()(formatGitCommitInfo(commit))
    showToast()('Commit info copied')
  } catch (e) {
    showToast()('Copy failed', 'error')
  }
}

// Copy the commit ID (full hash) to the clipboard
async function copyGitCommitId(commit) {
  if (!commit) return
  closeGitCommitContextMenu()
  try {
    await copyTextToClipboard()(commit.hash)
    showToast()('Commit ID copied')
  } catch (e) {
    showToast()('Copy failed', 'error')
  }
}

// Assemble full commit info (hash + subject + body + author + email + date + refs)
function formatGitCommitInfo(commit) {
  const lines = []
  lines.push(`commit ${commit.hash}`)
  if (commit.refs && commit.refs.length) lines.push(`refs: ${commit.refs.join(', ')}`)
  lines.push(`Author: ${commit.author} <${commit.email}>`)
  lines.push(`Date:   ${commit.date}`)
  lines.push('')
  lines.push(commit.subject)
  if (commit.body) {
    lines.push('')
    lines.push(commit.body)
  }
  return lines.join('\n')
}

// Hover / long-press tooltip: full commit info (fills in body and metadata beyond the single-line subject)
function formatGitCommitTooltip(commit) {
  if (!commit) return ''
  return formatGitCommitInfo(commit)
}

// Mobile "detail" modal: currently displayed commit (null means closed)
const gitCommitInfoModal = ref(null)

function showGitCommitInfoModal(commit) {
  if (!commit) return
  gitCommitInfoModal.value = commit
}


  return {
    // refs
    gitLog,
    gitLogLoading,
    gitLogError,
    gitLogHasMore,
    gitLogTotal,
    gitBranches,
    gitTags,
    gitCurrentBranch,
    gitSelectedCommit,
    gitRangeSelectMode,
    gitSelectedCommits,
    gitPatchLoading,
    gitCommitFiles,
    gitCommitDetailLoading,
    gitSelectedFile,
    gitDiffText,
    gitDiffLoading,
    gitDiffError,
    gitDiffTruncated,
    gitDiffSideBySide,
    gitDiffShowFull,
    pluginSidebarWorkingDir,
    pluginActiveAgentInfo,
    gitCommitContextMenu,
    gitCommitInfoModal,
    // Constants
    GIT_LOG_PAGE_SIZE,
    // Functions
    isNarrowGitDiffViewport,
    getGitTargetAgent,
    getGitTargetNodeId,
    getGitWorkingDir,
    callGitApi,
    fetchGitLog,
    fetchGitBranches,
    refreshGitView,
    toggleGitCommitDetail,
    enterGitRangeSelect,
    exitGitRangeSelect,
    toggleGitRangeSelect,
    downloadGitPatch,
    viewGitTargetDiff,
    onDiffTitleClick,
    onOpenDiffFileFromMessage,
    viewGitFileDiff,
    ensureGitDiffFullText,
    layoutGitDiffEditor,
    disposeDiffEditorForPane,
    disposeAllDiffEditors,
    ensureDiffEditorForPane,
    renderDiffForPane,
    loadDiffForPane,
    togglePaneDiffSideBySide,
    togglePaneDiffShowFull,
    navigatePaneDiff,
    closePaneDiff,
    scheduleDiffLayout,
    gitRefClass,
    gitFileStatus,
    formatGitRelativeTime,
    shortGitHash,
    closeGitCommitContextMenu,
    openGitCommitContextMenu,
    copyGitCommit,
    copyGitCommitId,
    formatGitCommitInfo,
    formatGitCommitTooltip,
    showGitCommitInfoModal,
  }
}
