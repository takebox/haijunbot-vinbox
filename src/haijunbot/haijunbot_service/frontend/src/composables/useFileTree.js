// File tree composable.
//
// Extracted from App.vue's <script setup> (the original file tree domain of 14 blocks, ~1163 lines), keeping behavior identical:
// - Core state: fileTreeState / fileTreeExpanded / fileTreeLoading / expandedAgents / selectedAgentId /
//   fileTreeSelectedPath / fileTreeSelectedAgentId / showStoppedAgents / stoppedNodeCollapseState /
//   fileTreeContextMenu / fileTreeClipboard / fileTreeUploadInput / fileTreeUploadContext / inputPrompt /
//   fileTreeDragState / fileTreeDropTargetPath
// - Icon constants: FILE_TREE_FOLDER_SVG / FILE_TREE_CTX_ICONS / FILE_TYPE_ICON_MAP / FILE_TYPE_ICON_BY_NAME
// - Node interaction: getFileTypeIcon / handleFileTreeNodeClick / selectFileTreeNode / scrollFileTreeNodeIntoView /
//   focusFileTreeContainer / revealTabInFileTree / toggleAgentExpanded / toggleStoppedNodeCollapse / isStoppedNodeCollapsed
// - Keyboard navigation: moveFileTreeSelection / handleFileTreeKeydown
// - Context menu: closeFileTreeContextMenu / getFileTreeContextDirPath / getFileTreeContextTargetPath /
//   getFileTreeContextDirNode / toWorkingDirRelativePath / copyTextToClipboard / openFileTreeContextMenu /
//   openInputPrompt / cancelInputPrompt / confirmInputPrompt / fileTreeContextActions / buildDirSearchGlob /
//   runFileTreeContextAction
// - Upload/download: uploadFileToDir / readFileAsDataUrl / onFileTreeUploadInputChange / downloadFileFromNode / refreshFileTreeDir
// - File CRUD: createFileOrDirectory / deleteFileOrDirectory / renameFileOrDirectory
// - Copy/paste: listDirectoryEntries / collectDirectorySnapshot / writeClipboardNode / resolvePasteName /
//   setFileTreeClipboard / pasteFileTreeClipboard
// - Drag and drop: handleFileTreeDragStart / handleFileTreeDragEnd / isValidFileTreeDropTarget / handleFileTreeDragOver /
//   handleFileTreeDragLeave / handleFileTreeDrop
// - Path utilities: resolveFileTreeDirNodeByPath / writeFileContent
// - Core loading: initFileTreeState / loadFileTreeNode / initFileTree / flattenVisibleFileTreeNodes /
//   getVisibleFileTreeNodes / findNode / toggleNodeExpand
//
// Dependency injection (passed in by the caller in setup, must be called after their definition):
// - agentList: ref(Array) (Agent list)
// - getVirtualWorkspaceAgent: function (get the virtual workspace Agent by agentId)
// - resolveFileTreeAgent: function (resolve the file tree Agent by agentId)
// - resolveAgentForPath: function (resolve the Agent by path)
// - openWorkspaceFile: function (open a workspace file)
// - setWorkspaceSidebarView: function (set the workspace sidebar view)
// - removeWorkspaceDir: function (remove a workspace directory)
// - fetchFileContent: function (read file content)
// - fetchWithAuth: function (authenticated fetch)
// - buildNodeHttpUrl: function (build a node HTTP URL)
// - getGatewayAddress: function (returns { host, port })
// - showToast: function (toast message)
// - showConfirm: function (confirmation dialog)
// - globalSearchFileGlob: ref(string) (global search file glob)
// - ensureWorkspaceSidebarFileTree: function (ensure the sidebar file tree is visible)
import { computed, nextTick, ref, triggerRef } from 'vue'

export function useFileTree({
  agentList,
  getVirtualWorkspaceAgent,
  resolveFileTreeAgent,
  resolveAgentForPath,
  openWorkspaceFile,
  setWorkspaceSidebarView,
  removeWorkspaceDir,
  fetchFileContent,
  fetchWithAuth,
  buildNodeHttpUrl,
  getGatewayAddress,
  showToast,
  showConfirm,
  globalSearchFileGlob,
  ensureWorkspaceSidebarFileTree,
}) {
// File tree state management
const fileTreeState = ref(new Map())        // file tree data per Agent: agent_id -> treeData
const fileTreeExpanded = ref(new Map())     // expansion state per Agent: agent_id -> Set(expandedPaths)
const fileTreeLoading = ref(new Map())      // loading state per Agent: agent_id -> Set(loadingPaths)
const expandedAgents = ref(new Set())       // set of Agents expanded in the editor directory tree
const selectedAgentId = ref(null)         // ID of the Agent selected in the editor directory tree
// Editor directory tree keyboard operation: the node (absolute path) currently selected by the cursor and the Agent it belongs to
const fileTreeSelectedPath = ref(null)
const fileTreeSelectedAgentId = ref(null)
const showStoppedAgents = ref(false)      // whether to show stopped Agents
const stoppedNodeCollapseState = ref(new Map()) // collapse state of stopped Agent node groups: nodeId -> boolean (true means collapsed)

// Toggle the expansion state of an Agent in the directory tree
function toggleAgentExpanded(agentId) {
  // Set the selected Agent
  selectedAgentId.value = agentId
  
  if (expandedAgents.value.has(agentId)) {
    expandedAgents.value.delete(agentId)
  } else {
    expandedAgents.value.add(agentId)
    // When expanding, ensure that Agent's file tree is initialized
    const agent = agentList.value.find(a => a.agent_id === agentId) || getVirtualWorkspaceAgent(agentId)
    if (agent && !fileTreeState.value.has(agentId)) {
      initFileTree(agentId, agent.working_dir)
    }
  }
  // Manually trigger a reactive update
  triggerRef(expandedAgents)
}

// Toggle the collapse state of a stopped Agent node group
function toggleStoppedNodeCollapse(nodeId) {
  const currentState = stoppedNodeCollapseState.value.get(nodeId) || false
  stoppedNodeCollapseState.value.set(nodeId, !currentState)
  triggerRef(stoppedNodeCollapseState)
}

// Check whether a stopped Agent node group is collapsed
function isStoppedNodeCollapsed(nodeId) {
  return stoppedNodeCollapseState.value.get(nodeId) || false
}

async function revealTabInFileTree(path) {
  const resolved = resolveAgentForPath(path)
  if (!resolved) return
  const { agentId, agent } = resolved
  const rootDir = String(agent.working_dir).replace(/\/+$/, '')
  const raw = String(path)
  const rel = raw === rootDir ? '' : raw.slice(rootDir.length + 1)
  const segments = rel ? rel.split('/').filter(Boolean) : []

  // Open the sidebar and switch to the files view
  setWorkspaceSidebarView('files')
  // Expand that Agent's node
  if (!expandedAgents.value.has(agentId)) {
    expandedAgents.value.add(agentId)
  }
  fileTreeSelectedAgentId.value = agentId
  await nextTick()
  // Ensure the file tree is initialized (setWorkspaceSidebarView also triggers this internally; this is a fallback)
  await ensureWorkspaceSidebarFileTree(agent)
  await nextTick()

  // Expand directories level by level: first expand the root node (path=working_dir), then walk down path segments to find and load each level.
  // The root node is collapsed by default; if not expanded, its children are not rendered in the visible list, so later selection/scrolling would fail.
  let nodes = fileTreeState.value.get(agentId) || []
  const rootNode = nodes.find(n => n.path === rootDir)
  if (rootNode && !rootNode.expanded) {
    await toggleNodeExpand(agentId, rootNode)
    await nextTick()
  }
  let currentPath = rootDir
  for (const seg of segments) {
    currentPath = `${currentPath}/${seg}`
    let node = findNode(nodes, currentPath)
    if (!node) break
    if (!node.expanded) {
      await toggleNodeExpand(agentId, node)
      await nextTick()
    }
    nodes = node.children || []
  }

  // Select and scroll to the target file node
  fileTreeSelectedAgentId.value = agentId
  fileTreeSelectedPath.value = path
  await nextTick()
  scrollFileTreeNodeIntoView(path)
}

// ===== File tree node icons: distinguished by file type (hand-drawn 16x16 stroke line SVGs, matching the agent icon style) =====
// Directory/file icons use currentColor to inherit the color of .folder-icon/.file-icon.
const FILE_TREE_FOLDER_SVG = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 4.5v7.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H8.2L6.7 4.5h-4.2a1 1 0 0 0-1 1z"/></svg>'
// File tree context menu icons (hand-drawn 14x14 stroke line SVGs, currentColor inherits the theme color)
const FILE_TREE_CTX_ICONS = {
  newFile: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 1.5h5l3 3v10H4z"/><path d="M9 1.5v3h3"/></svg>',
  newFolder: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 4.5v7a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H8.2L6.7 4.5H2.5a1 1 0 0 0-1 1z"/><path d="M8 7v3M6.5 8.5h3"/></svg>',
  find: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3.5 3.5"/></svg>',
  refresh: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9"/><path d="M13.5 2.5v3h-3"/></svg>',
  upload: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 11V3.5M4.5 6 8 2.5 11.5 6"/><path d="M2.5 13.5h11"/></svg>',
  download: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3.5V11M4.5 7.5 8 11l3.5-3.5"/><path d="M2.5 13.5h11"/></svg>',
  copy: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1"/><path d="M10.5 5.5v-1a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h1"/></svg>',
  cut: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="4.5" cy="12" r="2"/><circle cx="11.5" cy="12" r="2"/><path d="M6 11 13 3.5M10 11 3 3.5"/></svg>',
  paste: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="10" height="11" rx="1"/><path d="M6 3V2a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1"/><path d="M6 8h4M6 11h4"/></svg>',
  copyPath: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="9" height="9" rx="1.5"/><path d="M5 12v.5A1.5 1.5 0 0 0 6.5 14h6a1.5 1.5 0 0 0 1.5-1.5v-6A1.5 1.5 0 0 0 12.5 5H12"/></svg>',
  link: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6.5 9.5 9.5 6.5"/><path d="M7 11 5.5 12.5a2.1 2.1 0 0 1-3-3L4 8.2"/><path d="M9 5l1.5-1.5a2.1 2.1 0 0 1 3 3L12 8.2"/></svg>',
  rename: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 13l.8-2.6 7.2-7.2a1.4 1.4 0 0 1 2 2l-7.2 7.2z"/><path d="M3 13h3.5"/></svg>',
  trash: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4.5h10M6.5 4.5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1.5"/><path d="M4.5 4.5l.7 8.3a1 1 0 0 0 1 .9h3.6a1 1 0 0 0 1-.9l.7-8.3"/><path d="M6.5 7.5v4M9.5 7.5v4"/></svg>',
  removeDir: '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4.5h10M6.5 4.5V3a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1.5"/><path d="M4.5 4.5l.7 8.3a1 1 0 0 0 1 .9h3.6a1 1 0 0 0 1-.9l.7-8.3"/><path d="M6 7.5l4 4M10 7.5l-4 4"/></svg>',
}

const FILE_TYPE_ICON_MAP = {
  // Programming languages
  py: 'python', pyw: 'python',
  cpp: 'cpp', cc: 'cpp', cxx: 'cpp', hpp: 'cpp', hxx: 'cpp',
  c: 'c', h: 'c',
  cs: 'csharp',
  js: 'javascript', jsx: 'javascript', mjs: 'javascript', cjs: 'javascript',
  ts: 'typescript', tsx: 'typescript',
  json: 'json',
  java: 'java',
  kt: 'kotlin', kts: 'kotlin',
  go: 'go',
  rs: 'rust',
  rb: 'ruby',
  php: 'php',
  swift: 'swift',
  vue: 'vue',
  svelte: 'svelte',
  ps1: 'powershell', psd1: 'powershell', psm1: 'powershell',
  sh: 'shellcheck', bash: 'shellcheck', zsh: 'shellcheck', fish: 'shellcheck',
  // Markup / styles
  html: 'html', htm: 'html',
  css: 'css',
  scss: 'sass', sass: 'sass', less: 'sass',
  xml: 'xml',
  md: 'markdown', markdown: 'markdown',
  toml: 'toml',
  yml: 'yaml', yaml: 'yaml',
  // Config
  env: 'settings', ini: 'settings', cfg: 'settings', conf: 'settings', properties: 'settings',
  // Data
  db: 'database', sqlite: 'database', sqlite3: 'database', sql: 'database',
  csv: 'table', tsv: 'table', xls: 'table', xlsx: 'table',
  // Images
  png: 'image', jpg: 'image', jpeg: 'image', gif: 'image', webp: 'image', bmp: 'image', ico: 'image', svg: 'image', avif: 'image',
  // Audio/video
  mp3: 'audio', wav: 'audio', ogg: 'audio', flac: 'audio', m4a: 'audio', aac: 'audio',
  mp4: 'video', avi: 'video', mkv: 'video', mov: 'video', webm: 'video', flv: 'video',
  // Documents / office
  pdf: 'pdf',
  doc: 'word', docx: 'word',
  ppt: 'powerpoint', pptx: 'powerpoint',
  txt: 'document', rtf: 'document',
  log: 'log',
  // Archives
  zip: 'zip', tar: 'zip', gz: 'zip', tgz: 'zip', rar: 'zip', '7z': 'zip', bz2: 'zip', xz: 'zip',
  // Binaries / executables
  exe: 'exe', msi: 'exe', dll: 'exe', bin: 'exe', so: 'exe',
  // Fonts
  ttf: 'font', otf: 'font', woff: 'font', woff2: 'font', eot: 'font',
  // Security
  pem: 'lock', key: 'lock', crt: 'lock', p12: 'lock'
}
// File names without an extension that need a dedicated icon (exact match, including dotfiles)
const FILE_TYPE_ICON_BY_NAME = {
  dockerfile: 'docker',
  makefile: 'settings',
  '.gitignore': 'git',
  '.gitattributes': 'git',
  license: 'document',
  readme: 'document'
}

function getFileTypeIcon(node) {
  if (node.type === 'directory') return FILE_TREE_FOLDER_SVG
  const name = node.name || ''
  const lowerName = name.toLowerCase()
  const dotIdx = lowerName.lastIndexOf('.')
  const ext = dotIdx >= 0 ? lowerName.slice(dotIdx + 1) : ''
  // First match by full file name (Dockerfile/Makefile/.gitignore/.env etc.)
  let icon = FILE_TYPE_ICON_BY_NAME[lowerName] || ''
  // Then match by extension (.env → env → settings)
  if (!icon && ext) icon = FILE_TYPE_ICON_MAP[ext] || ''
  if (!icon) {
    // Has an extension but no dedicated icon matched → generic file icon
    icon = 'document'
  }
  return `<img src="/file-icons/${icon}.svg" alt="" class="file-type-icon">`
}

async function handleFileTreeNodeClick(agentId, node) {
  if (node.type === 'directory') {
    await toggleNodeExpand(agentId, node)
    return
  }

  await openWorkspaceFile(node.path, agentId)
}

// ===== Editor directory tree keyboard operation =====
// Sync the cursor selection when a node is clicked, so subsequent arrow keys continue from that node
function selectFileTreeNode(agentId, node) {
  fileTreeSelectedAgentId.value = agentId
  fileTreeSelectedPath.value = node.path
}

// Scroll the cursor-selected node into view
function scrollFileTreeNodeIntoView(path) {
  nextTick(() => {
    const el = document.querySelector(`.workspace-tree-node[data-node-path="${CSS.escape(path)}"]`)
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' })
  })
}

// Focus the directory tree container so arrow keys/Enter take effect immediately (prefer the currently selected Agent's tree, otherwise the first visible tree)
function focusFileTreeContainer() {
  nextTick(() => {
    const agentId = selectedAgentId.value
    let el = agentId
      ? document.querySelector(`.workspace-file-tree-list[data-agent-id="${CSS.escape(agentId)}"]`)
      : null
    if (!el) el = document.querySelector('.workspace-file-tree-list')
    if (el) el.focus()
  })
}

// Move the cursor by direction within the current Agent's visible node list
function moveFileTreeSelection(agentId, delta) {
  const nodes = getVisibleFileTreeNodes(agentId)
  if (!nodes.length) return
  const currentPath = fileTreeSelectedAgentId.value === agentId ? fileTreeSelectedPath.value : null
  let index = nodes.findIndex((item) => item.node.path === currentPath)
  if (index === -1) {
    index = delta > 0 ? 0 : nodes.length - 1
  } else {
    index = Math.min(nodes.length - 1, Math.max(0, index + delta))
  }
  const target = nodes[index].node
  fileTreeSelectedAgentId.value = agentId
  fileTreeSelectedPath.value = target.path
  scrollFileTreeNodeIntoView(target.path)
}

// Directory tree container key events: up/down move the cursor, Enter expands/collapses a directory or opens a file
async function handleFileTreeKeydown(event, agentId) {
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    moveFileTreeSelection(agentId, event.key === 'ArrowDown' ? 1 : -1)
    return
  }
  if (event.key === 'Enter') {
    const path = fileTreeSelectedAgentId.value === agentId ? fileTreeSelectedPath.value : null
    if (!path) return
    const nodes = getVisibleFileTreeNodes(agentId)
    const target = nodes.find((item) => item.node.path === path)
    if (!target) return
    event.preventDefault()
    await handleFileTreeNodeClick(agentId, target.node)
  }
}

// node is a directory node; node being null means the target is that Agent's working directory root
const fileTreeContextMenu = ref({ visible: false, x: 0, y: 0, agentId: '', node: null })

// Directory tree in-app clipboard: { mode: 'copy'|'cut', agentId, path, name, kind, content?, children? }
const fileTreeClipboard = ref(null)

// Directory tree "upload": hidden file input and its context (records the target Agent and directory)
const fileTreeUploadInput = ref(null)
const fileTreeUploadContext = ref({ agentId: '', dirPath: '' })

// Generic input prompt state (e.g. naming a new file/folder)
const inputPrompt = ref({
  visible: false,
  title: '',
  label: '',
  placeholder: '',
  value: '',
  error: '',
  onConfirm: null,
})

function openInputPrompt({ title, label = '', placeholder = '', value = '', onConfirm }) {
  inputPrompt.value = { visible: true, title, label, placeholder, value, error: '', onConfirm }
}

function cancelInputPrompt() {
  inputPrompt.value = { ...inputPrompt.value, visible: false, onConfirm: null }
}

function confirmInputPrompt() {
  const prompt = inputPrompt.value
  if (!prompt.visible) return
  const result = prompt.onConfirm ? prompt.onConfirm(prompt.value) : null
  // A string returned by onConfirm means validation failed; keep the modal open showing it as an error
  if (typeof result === 'string') {
    inputPrompt.value = { ...prompt, error: result }
    return
  }
  inputPrompt.value = { ...prompt, visible: false, onConfirm: null }
}

function closeFileTreeContextMenu() {
  if (fileTreeContextMenu.value.visible) {
    fileTreeContextMenu.value = { ...fileTreeContextMenu.value, visible: false }
  }
}

// Absolute path of the directory the menu acts on: directory nodes use node.path, the root uses agent.working_dir
function getFileTreeContextDirPath() {
  const menu = fileTreeContextMenu.value
  if (menu.node && menu.node.type === 'directory' && menu.node.path) return menu.node.path
  const agent = resolveFileTreeAgent(menu.agentId)
  return agent?.working_dir || ''
}

// Absolute path of the node the menu acts on: file nodes use node.path, directories/roots use the directory path
function getFileTreeContextTargetPath() {
  const menu = fileTreeContextMenu.value
  if (menu.node && menu.node.type === 'file' && menu.node.path) return menu.node.path
  return getFileTreeContextDirPath()
}

// Tree node corresponding to the directory the menu acts on: directory nodes return themselves, file nodes/roots return null (meaning the working directory root)
function getFileTreeContextDirNode() {
  const menu = fileTreeContextMenu.value
  if (menu.node && menu.node.type === 'directory') return menu.node
  return null
}

// Convert an absolute path to a path relative to working_dir (returns an empty string when outside the working directory)
function toWorkingDirRelativePath(agentId, absPath) {
  const agent = resolveFileTreeAgent(agentId)
  const workingDir = String(agent?.working_dir || '').replace(/\/+$/, '')
  const normalized = String(absPath || '').replace(/\/+$/, '')
  if (!workingDir || !normalized) return ''
  if (normalized === workingDir) return ''
  if (!normalized.startsWith(workingDir + '/')) return ''
  return normalized.slice(workingDir.length + 1)
}

// Copy text to the clipboard (prefer the Clipboard API, fall back to execCommand in non-secure contexts)
async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    if (!document.execCommand('copy')) throw new Error('copy failed')
  } finally {
    document.body.removeChild(textarea)
  }
}

// Right-click on a directory tree node/working directory root: pop up the menu in place (viewport coordinates + boundary clamping)
function openFileTreeContextMenu(agent, node, event) {
  if (!agent || !event) return
  const MENU_W = 220
  const MENU_H = 420
  let x = event.clientX
  let y = event.clientY
  if (x + MENU_W > window.innerWidth) x = Math.max(window.innerWidth - MENU_W, 0)
  if (y + MENU_H > window.innerHeight) y = Math.max(window.innerHeight - MENU_H, 0)
  fileTreeContextMenu.value = {
    visible: true,
    x,
    y,
    agentId: agent.agent_id,
    node: node || null,
  }
  // Close when clicking outside the menu (one-time listener, avoiding a permanent document listener)
  nextTick(() => {
    document.addEventListener('pointerdown', closeFileTreeContextMenu, { once: true })
  })
}

const fileTreeContextActions = computed(() => {
  const hasAgent = Boolean(fileTreeContextMenu.value.agentId)
  const hasNode = Boolean(fileTreeContextMenu.value.node)
  // Paste availability: the clipboard exists and matches the target node (same node across directories allowed, cross-node not supported)
  const menuNodeId = String(resolveFileTreeAgent(fileTreeContextMenu.value.agentId)?.node_id || '').trim()
  const canPaste = hasAgent && Boolean(fileTreeClipboard.value)
    && (!fileTreeClipboard.value.nodeId || !menuNodeId || fileTreeClipboard.value.nodeId === menuNodeId)
  // "Remove" is only available for virtual directory sessions created by "Open Directory" (real Agents are not removed here)
  const isVirtualDir = resolveFileTreeAgent(fileTreeContextMenu.value.agentId)?.virtual === true
  // "Download" is only available for file nodes (directories/roots are not supported)
  const isFileNode = fileTreeContextMenu.value.node?.type === 'file'
  return [
    { id: 'new-file', label: 'New File', icon: FILE_TREE_CTX_ICONS.newFile, enabled: hasAgent },
    { id: 'new-folder', label: 'New Folder', icon: FILE_TREE_CTX_ICONS.newFolder, enabled: hasAgent },
    { id: 'find-in-folder', label: 'Find in Folder', icon: FILE_TREE_CTX_ICONS.find, enabled: hasAgent },
    { id: 'refresh', label: 'Refresh', icon: FILE_TREE_CTX_ICONS.refresh, enabled: hasAgent },
    { id: 'upload', label: 'Upload', icon: FILE_TREE_CTX_ICONS.upload, enabled: hasAgent },
    { id: 'download', label: 'Download', icon: FILE_TREE_CTX_ICONS.download, enabled: isFileNode },
    { id: 'copy', label: 'Copy', icon: FILE_TREE_CTX_ICONS.copy, enabled: hasNode },
    { id: 'cut', label: 'Cut', icon: FILE_TREE_CTX_ICONS.cut, enabled: hasNode },
    { id: 'paste', label: 'Paste', icon: FILE_TREE_CTX_ICONS.paste, enabled: canPaste },
    { id: 'copy-path', label: 'Copy Path', icon: FILE_TREE_CTX_ICONS.copyPath, enabled: hasAgent },
    { id: 'copy-relative-path', label: 'Copy Relative Path', icon: FILE_TREE_CTX_ICONS.link, enabled: hasAgent },
    { id: 'rename', label: 'Rename', icon: FILE_TREE_CTX_ICONS.rename, enabled: hasNode },
    { id: 'delete', label: 'Delete', icon: FILE_TREE_CTX_ICONS.trash, enabled: hasNode },
    { id: 'remove-dir', label: 'Remove Directory', icon: FILE_TREE_CTX_ICONS.removeDir, enabled: isVirtualDir },
  ]
})

// Convert an absolute path to a glob relative to working_dir (used by "Find in Folder")
function buildDirSearchGlob(agentId, dirPath) {
  const agent = resolveFileTreeAgent(agentId)
  const workingDir = String(agent?.working_dir || '').replace(/\/$/, '')
  const normalizedDir = String(dirPath || '').replace(/\/$/, '')
  if (!workingDir || !normalizedDir || normalizedDir === workingDir) return ''
  if (!normalizedDir.startsWith(workingDir + '/')) return ''
  const relative = normalizedDir.slice(workingDir.length + 1)
  return relative ? `${relative}/**` : ''
}

// Execute a directory tree context menu action
async function runFileTreeContextAction(action) {
  if (!action || action.enabled === false) return
  const menu = { ...fileTreeContextMenu.value }
  const agent = resolveFileTreeAgent(menu.agentId)
  closeFileTreeContextMenu()
  if (!agent) return

  if (action.id === 'remove-dir') {
    removeWorkspaceDir(agent.agent_id)
    return
  }

  if (action.id === 'new-file' || action.id === 'new-folder') {
    const kind = action.id === 'new-file' ? 'file' : 'directory'
    const label = kind === 'file' ? 'file' : 'folder'
    const dirPath = getFileTreeContextDirPath() || agent.working_dir
    openInputPrompt({
      title: `New ${label}`,
      label: `${label} name`,
      placeholder: `Enter the new ${label} name`,
      value: '',
      onConfirm: (rawName) => {
        const trimmedName = String(rawName || '').trim()
        if (!trimmedName) return 'Name cannot be empty'
        if (trimmedName.includes('/') || trimmedName.includes('\\')) return 'Name cannot contain path separators'
        const absPath = `${String(dirPath).replace(/\/$/, '')}/${trimmedName}`
        createFileOrDirectory(agent.agent_id, absPath, kind)
          .then(() => refreshFileTreeDir(agent.agent_id, menu.node))
          .then(() => (kind === 'file' ? openWorkspaceFile(absPath, agent.agent_id) : null))
          .then(() => showToast(`${label} created`, 'success'))
          .catch((error) => showToast(error.message || `Failed to create ${label}`, 'error'))
        return null
      },
    })
    return
  }

  if (action.id === 'find-in-folder') {
    const dirPath = getFileTreeContextDirPath()
    globalSearchFileGlob.value = buildDirSearchGlob(agent.agent_id, dirPath)
    setWorkspaceSidebarView('search')
    nextTick(() => {
      const input = document.querySelector('.workspace-global-search-input')
      if (input) input.focus()
    })
    return
  }

  if (action.id === 'refresh') {
    await refreshFileTreeDir(agent.agent_id, menu.node)
    return
  }

  if (action.id === 'upload') {
    // Upload target directory: directory nodes use their own path, file nodes/roots fall back to the working directory
    const dirPath = getFileTreeContextDirPath() || agent.working_dir
    if (!dirPath) {
      showToast('Cannot determine the upload directory', 'error')
      return
    }
    uploadFileToDir(agent.agent_id, dirPath)
    return
  }

  if (action.id === 'download') {
    const targetPath = getFileTreeContextTargetPath()
    if (!targetPath) return
    await downloadFileFromNode(agent.agent_id, targetPath)
    return
  }

  if (action.id === 'copy' || action.id === 'cut') {
    const node = menu.node
    if (!node || !node.path) return
    await setFileTreeClipboard(action.id === 'cut' ? 'cut' : 'copy', agent.agent_id, node)
    return
  }

  if (action.id === 'paste') {
    const destDir = getFileTreeContextDirPath()
    if (!destDir) return
    await pasteFileTreeClipboard(agent.agent_id, destDir)
    await refreshFileTreeDir(agent.agent_id, getFileTreeContextDirNode())
    return
  }

  if (action.id === 'copy-path') {
    const targetPath = getFileTreeContextTargetPath()
    if (!targetPath) return
    try {
      await copyTextToClipboard(targetPath)
      showToast('Path copied', 'success')
    } catch (error) {
      showToast('Failed to copy path', 'error')
    }
    return
  }

  if (action.id === 'copy-relative-path') {
    const targetPath = getFileTreeContextTargetPath()
    if (!targetPath) return
    const relativePath = toWorkingDirRelativePath(agent.agent_id, targetPath)
    if (!relativePath) {
      showToast('The path is not inside the working directory; cannot generate a relative path', 'error')
      return
    }
    try {
      await copyTextToClipboard(relativePath)
      showToast('Relative path copied', 'success')
    } catch (error) {
      showToast('Failed to copy relative path', 'error')
    }
    return
  }

  if (action.id === 'rename') {
    const node = menu.node
    if (!node || !node.path) return
    const isDir = node.type === 'directory'
    const parentPath = String(node.path).replace(/\/+$/, '').split('/').slice(0, -1).join('/') || '/'
    openInputPrompt({
      title: `Rename ${isDir ? 'folder' : 'file'}`,
      label: 'New name',
      placeholder: `Enter the new ${isDir ? 'folder' : 'file'} name`,
      value: node.name || '',
      onConfirm: (rawName) => {
        const trimmedName = String(rawName || '').trim()
        if (!trimmedName) return 'Name cannot be empty'
        if (trimmedName.includes('/') || trimmedName.includes('\\')) return 'Name cannot contain path separators'
        if (trimmedName === node.name) return null
        const newAbsPath = `${parentPath.replace(/\/$/, '')}/${trimmedName}`
        renameFileOrDirectory(agent.agent_id, node.path, newAbsPath)
          .then(() => refreshFileTreeDir(agent.agent_id, menu.node))
          .then(() => showToast('Renamed successfully', 'success'))
          .catch((error) => showToast(error.message || 'Rename failed', 'error'))
        return null
      },
    })
    return
  }

  if (action.id === 'delete') {
    const node = menu.node
    if (!node || !node.path) return
    const isDir = node.type === 'directory'
    const confirmMessage = isDir
      ? `Are you sure you want to delete the folder "${node.name}" and all of its contents? This action cannot be undone.`
      : `Are you sure you want to delete the file "${node.name}"? This action cannot be undone.`
    showConfirm(
      confirmMessage,
      () => {
        deleteFileOrDirectory(agent.agent_id, node.path, isDir)
          .then(() => refreshFileTreeDir(agent.agent_id, menu.node))
          .then(() => showToast('Deleted', 'success'))
          .catch((error) => showToast(error.message || 'Delete failed', 'error'))
      },
      () => {},
      false
    )
  }
}

function uploadFileToDir(agentId, dirPath) {
  fileTreeUploadContext.value = { agentId, dirPath }
  const input = fileTreeUploadInput.value
  if (!input) return
  // Reset value to allow selecting the same file again
  input.value = ''
  input.click()
}

// Read a local file as a dataURL (the backend /file-upload supports the dataURL prefix and is binary-safe)
function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error || new Error('Failed to read file'))
    reader.readAsDataURL(file)
  })
}

// Hidden file input change: upload each to the target directory (keeping the original file names), then refresh the directory tree
async function onFileTreeUploadInputChange(event) {
  const input = event?.target
  const files = Array.from(input?.files || [])
  const { agentId, dirPath } = fileTreeUploadContext.value
  if (input) input.value = ''
  if (!files.length || !agentId || !dirPath) return
  const agent = resolveFileTreeAgent(agentId)
  if (!agent || !agent.node_id) {
    showToast('Target Agent node not found', 'error')
    return
  }
  const { host, port } = getGatewayAddress()
  const targetNodeId = String(agent.node_id).trim()
  const baseDir = String(dirPath).replace(/\/+$/, '')
  let okCount = 0
  const errors = []
  for (const file of files) {
    try {
      const data = await readFileAsDataUrl(file)
      const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-upload'), {
        method: 'POST',
        body: JSON.stringify({ path: `${baseDir}/${file.name}`, data, node_id: targetNodeId })
      })
      const result = await response.json()
      if (!response.ok || !result.success) {
        throw new Error(result.error?.message || 'Upload failed')
      }
      okCount += 1
    } catch (error) {
      errors.push(`${file.name}: ${error.message || 'Upload failed'}`)
    }
  }
  await refreshFileTreeDir(agentId, getFileTreeContextDirNode())
  if (errors.length === 0) {
    showToast(`Uploaded ${okCount} file(s)`, 'success')
  } else if (okCount > 0) {
    showToast(`Uploaded ${okCount} file(s), ${errors.length} failed: ${errors[0]}`, 'error')
  } else {
    showToast(errors[0] || 'Upload failed', 'error')
  }
}

// Download a file on a node to the local browser (via /file-content, text ≤10MB only)
async function downloadFileFromNode(agentId, filePath) {
  const agent = resolveFileTreeAgent(agentId)
  if (!agent || !agent.node_id) {
    showToast('Target Agent node not found', 'error')
    return
  }
  const { host, port } = getGatewayAddress()
  const targetNodeId = String(agent.node_id).trim()
  try {
    const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-content'), {
      method: 'POST',
      body: JSON.stringify({ path: filePath, node_id: targetNodeId })
    })
    const result = await response.json()
    if (!response.ok || !result.success || !result.data) {
      throw new Error(result.error?.message || 'Download failed')
    }
    const content = result.data.content || ''
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const objectUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = String(filePath).split('/').filter(Boolean).pop() || 'download.txt'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(objectUrl)
    showToast('Download started', 'success')
  } catch (error) {
    showToast(error.message || 'Download failed', 'error')
  }
}

// Refresh the specified directory node (node being null refreshes the working directory root)
async function refreshFileTreeDir(agentId, node) {
  const agent = resolveFileTreeAgent(agentId)
  if (!agent) return
  if (!node) {
    fileTreeState.value.delete(agentId)
    initFileTreeState(agentId)
    await initFileTree(agentId, agent.working_dir)
    triggerRef(fileTreeState)
    return
  }
  node.loaded = false
  node.children = []
  await loadFileTreeNode(agentId, node)
  triggerRef(fileTreeState)
}

async function createFileOrDirectory(agentId, absPath, kind) {
  const { host, port } = getGatewayAddress()
  const agent = resolveFileTreeAgent(agentId)
  if (!agent) {
    throw new Error(`Agent not found: ${agentId}`)
  }
  if (!agent.node_id) {
    throw new Error(`Agent has no node_id: ${agentId}`)
  }
  const targetNodeId = String(agent.node_id).trim()
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-create'), {
    method: 'POST',
    body: JSON.stringify({ path: absPath, content: '', kind, node_id: targetNodeId })
  })
  const result = await response.json()
  if (!response.ok || !result.success) {
    throw new Error(result.error?.message || 'Creation failed')
  }
  return result.data
}

// Call the backend delete file/directory API (directories require recursive for recursive deletion)
async function deleteFileOrDirectory(agentId, absPath, recursive = false) {
  const { host, port } = getGatewayAddress()
  const agent = resolveFileTreeAgent(agentId)
  if (!agent) {
    throw new Error(`Agent not found: ${agentId}`)
  }
  if (!agent.node_id) {
    throw new Error(`Agent has no node_id: ${agentId}`)
  }
  const targetNodeId = String(agent.node_id).trim()
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-delete'), {
    method: 'POST',
    body: JSON.stringify({ path: absPath, recursive, node_id: targetNodeId })
  })
  const result = await response.json()
  if (!response.ok || !result.success) {
    throw new Error(result.error?.message || 'Delete failed')
  }
  return result.data
}

// Call the backend rename/move file/directory API (does not overwrite existing paths)
async function renameFileOrDirectory(agentId, absPath, newAbsPath) {
  const { host, port } = getGatewayAddress()
  const agent = resolveFileTreeAgent(agentId)
  if (!agent) {
    throw new Error(`Agent not found: ${agentId}`)
  }
  if (!agent.node_id) {
    throw new Error(`Agent has no node_id: ${agentId}`)
  }
  const targetNodeId = String(agent.node_id).trim()
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-rename'), {
    method: 'POST',
    body: JSON.stringify({ path: absPath, new_path: newAbsPath, node_id: targetNodeId })
  })
  const result = await response.json()
  if (!response.ok || !result.success) {
    throw new Error(result.error?.message || 'Rename failed')
  }
  return result.data
}

async function listDirectoryEntries(agentId, dirPath) {
  const { host, port } = getGatewayAddress()
  const agent = resolveFileTreeAgent(agentId)
  if (!agent) throw new Error(`Agent not found: ${agentId}`)
  if (!agent.node_id) throw new Error(`Agent has no node_id: ${agentId}`)
  const targetNodeId = String(agent.node_id).trim()
  const response = await fetchWithAuth(
    buildNodeHttpUrl(host, port, targetNodeId, `directories?path=${encodeURIComponent(dirPath)}`)
  )
  const result = await response.json()
  if (!response.ok || !result.success) {
    throw new Error(result.error?.message || 'Failed to read directory')
  }
  return result.data.items || []
}

// Recursively collect directory contents (files read their content, directories keep their structure)
async function collectDirectorySnapshot(agentId, dirPath) {
  const entries = await listDirectoryEntries(agentId, dirPath)
  const children = []
  for (const entry of entries) {
    if (entry.type === 'directory') {
      children.push({
        name: entry.name,
        kind: 'directory',
        children: await collectDirectorySnapshot(agentId, entry.path),
      })
    } else {
      const content = await fetchFileContent(entry.path, agentId)
      children.push({ name: entry.name, kind: 'file', content })
    }
  }
  return children
}

// Write a clipboard node into the target directory (files write their content, directories are rebuilt recursively)
async function writeClipboardNode(agentId, destDir, node) {
  const absPath = `${String(destDir).replace(/\/$/, '')}/${node.name}`
  if (node.kind === 'directory') {
    await createFileOrDirectory(agentId, absPath, 'directory')
    for (const child of node.children || []) {
      await writeClipboardNode(agentId, absPath, child)
    }
    return
  }
  await writeFileContent(agentId, absPath, node.content ?? '')
}

// Generate a non-conflicting name in the target directory: name.ext -> name (copy).ext -> name (copy 2).ext
async function resolvePasteName(agentId, destDir, name) {
  const existing = new Set((await listDirectoryEntries(agentId, destDir)).map(i => i.name))
  if (!existing.has(name)) return name
  const dotIndex = name.lastIndexOf('.')
  const hasExt = dotIndex > 0
  const base = hasExt ? name.slice(0, dotIndex) : name
  const ext = hasExt ? name.slice(dotIndex) : ''
  let candidate = `${base} (copy)${ext}`
  let counter = 2
  while (existing.has(candidate)) {
    candidate = `${base} (copy ${counter})${ext}`
    counter++
  }
  return candidate
}

// Copy/cut: store the node contents in the in-app clipboard
async function setFileTreeClipboard(mode, agentId, node) {
  if (!node || !node.path) return
  const kind = node.type === 'directory' ? 'directory' : 'file'
  // Record the source node: on paste, node_id determines whether it is cross-node (same node across directories allowed, cross-node not supported)
  const sourceNodeId = String(resolveFileTreeAgent(agentId)?.node_id || '').trim()
  try {
    if (kind === 'directory') {
      const children = await collectDirectorySnapshot(agentId, node.path)
      fileTreeClipboard.value = { mode, agentId, nodeId: sourceNodeId, path: node.path, name: node.name, kind, children }
    } else {
      const content = await fetchFileContent(node.path, agentId)
      fileTreeClipboard.value = { mode, agentId, nodeId: sourceNodeId, path: node.path, name: node.name, kind, content }
    }
    showToast(mode === 'cut' ? 'Cut, can paste into the target directory' : 'Copied, can paste into the target directory', 'success')
  } catch (error) {
    showToast(error.message || 'Copy failed', 'error')
  }
}

// Paste: write the clipboard contents into the target directory
async function pasteFileTreeClipboard(agentId, destDir) {
  const clip = fileTreeClipboard.value
  if (!clip) return
  // Determined by node_id: same node across directories allowed; cross-node requires file content transfer and is not supported yet
  const targetNodeId = String(resolveFileTreeAgent(agentId)?.node_id || '').trim()
  if (clip.nodeId && targetNodeId && clip.nodeId !== targetNodeId) {
    showToast('Cross-node paste is not supported yet', 'error')
    return
  }
  const normalizedDest = String(destDir).replace(/\/+$/, '')
  const sourceParent = String(clip.path).replace(/\/+$/, '').split('/').slice(0, -1).join('/') || '/'
  if (clip.mode === 'cut' && sourceParent === normalizedDest) {
    showToast('Source and target directories are the same; nothing to paste', 'info')
    return
  }
  try {
    if (clip.mode === 'cut') {
      const targetPath = `${normalizedDest}/${clip.name}`
      await renameFileOrDirectory(agentId, clip.path, targetPath)
      fileTreeClipboard.value = null
      showToast('Moved', 'success')
    } else {
      const finalName = await resolvePasteName(agentId, normalizedDest, clip.name)
      await writeClipboardNode(agentId, normalizedDest, { ...clip, name: finalName })
      showToast('Pasted', 'success')
    }
  } catch (error) {
    showToast(error.message || 'Paste failed', 'error')
  }
}

const fileTreeDragState = ref(null)
// Path of the currently highlighted drop target directory (for visual feedback)
const fileTreeDropTargetPath = ref('')

// Drag start: record source node info (no backend reads, to avoid drag lag)
function handleFileTreeDragStart(event, agentId, node) {
  if (!node || !node.path) return
  const sourceNodeId = String(resolveFileTreeAgent(agentId)?.node_id || '').trim()
  fileTreeDragState.value = {
    agentId,
    nodeId: sourceNodeId,
    path: node.path,
    name: node.name,
    kind: node.type === 'directory' ? 'directory' : 'file',
  }
  fileTreeDropTargetPath.value = ''
  if (event.dataTransfer) {
    // Some browsers require data to be set before drop fires
    event.dataTransfer.effectAllowed = 'copyMove'
    try { event.dataTransfer.setData('text/plain', node.path) } catch (e) { /* ignore */ }
  }
}

// Drag end: clean up state and highlight
function handleFileTreeDragEnd() {
  fileTreeDragState.value = null
  fileTreeDropTargetPath.value = ''
}

// Whether the drop target is a valid directory: same node, not the source itself, not a descendant of the source directory, and not the source directory itself
function isValidFileTreeDropTarget(targetDirPath) {
  const drag = fileTreeDragState.value
  if (!drag || !targetDirPath) return false
  const normalizedTarget = String(targetDirPath).replace(/\/+$/, '')
  const normalizedSource = String(drag.path).replace(/\/+$/, '')
  // Cannot drop onto itself (dragging a directory onto itself)
  if (normalizedTarget === normalizedSource) return false
  // Cannot drop into the directory containing the source (no change in place)
  const sourceParent = normalizedSource.split('/').slice(0, -1).join('/') || '/'
  if (normalizedTarget === sourceParent) return false
  // A directory cannot be dragged into its own descendant directory (would cause self-nesting)
  if (drag.kind === 'directory' && normalizedTarget.startsWith(normalizedSource + '/')) return false
  return true
}

// Dragging over a directory node/root node: highlight (valid targets only)
function handleFileTreeDragOver(event, dirPath) {
  const drag = fileTreeDragState.value
  if (!drag) return
  // Reject cross-node outright (no droppable feedback)
  const targetNodeId = String(resolveFileTreeAgent(drag.agentId)?.node_id || '').trim()
  if (drag.nodeId && targetNodeId && drag.nodeId !== targetNodeId) return
  if (!isValidFileTreeDropTarget(dirPath)) return
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = (event.ctrlKey || event.metaKey) ? 'copy' : 'move'
  }
  fileTreeDropTargetPath.value = String(dirPath).replace(/\/+$/, '')
}

// Leaving the drop target: clear the highlight (only when leaving the currently highlighted target)
function handleFileTreeDragLeave(dirPath) {
  const normalized = String(dirPath || '').replace(/\/+$/, '')
  if (fileTreeDropTargetPath.value === normalized) fileTreeDropTargetPath.value = ''
}

// Drop: hold Ctrl/⌘ to copy, otherwise move; operates within the same directory tree
async function handleFileTreeDrop(event, agentId, destDir) {
  event.preventDefault()
  const drag = fileTreeDragState.value
  fileTreeDropTargetPath.value = ''
  if (!drag) return
  // Hard constraint: only allowed within the same directory tree (same node_id)
  const targetNodeId = String(resolveFileTreeAgent(agentId)?.node_id || '').trim()
  if (drag.nodeId && targetNodeId && drag.nodeId !== targetNodeId) {
    showToast('Drag and drop is only supported within the same directory tree', 'error')
    fileTreeDragState.value = null
    return
  }
  if (!isValidFileTreeDropTarget(destDir)) {
    fileTreeDragState.value = null
    return
  }
  const normalizedDest = String(destDir).replace(/\/+$/, '')
  const isCopy = event.ctrlKey || event.metaKey
  fileTreeDragState.value = null
  try {
    if (isCopy) {
      // Copy: read the source content (recursive for directories) → write to the target directory with a non-conflicting name
      const snapshot = drag.kind === 'directory'
        ? { kind: 'directory', children: await collectDirectorySnapshot(agentId, drag.path) }
        : { kind: 'file', content: await fetchFileContent(drag.path, agentId) }
      const finalName = await resolvePasteName(agentId, normalizedDest, drag.name)
      await writeClipboardNode(agentId, normalizedDest, { ...snapshot, name: finalName })
      showToast('Copied', 'success')
    } else {
      // Move: reuse file-rename (does not overwrite existing paths)
      const targetPath = `${normalizedDest}/${drag.name}`
      await renameFileOrDirectory(agentId, drag.path, targetPath)
      showToast('Moved', 'success')
    }
    // Refresh the target directory; for a move the source directory also needs refreshing
    await refreshFileTreeDir(agentId, resolveFileTreeDirNodeByPath(agentId, normalizedDest))
    if (!isCopy) {
      const sourceParent = String(drag.path).replace(/\/+$/, '').split('/').slice(0, -1).join('/') || '/'
      if (sourceParent !== normalizedDest) {
        await refreshFileTreeDir(agentId, resolveFileTreeDirNodeByPath(agentId, sourceParent))
      }
    }
  } catch (error) {
    showToast(error.message || (isCopy ? 'Copy failed' : 'Move failed'), 'error')
  }
}

function resolveFileTreeDirNodeByPath(agentId, dirPath) {
  const agent = resolveFileTreeAgent(agentId)
  const workingDir = String(agent?.working_dir || '').replace(/\/+$/, '')
  const normalized = String(dirPath || '').replace(/\/+$/, '')
  if (!workingDir || !normalized || normalized === workingDir) return null
  const nodes = fileTreeState.value.get(agentId) || []
  const stack = [...nodes]
  while (stack.length) {
    const node = stack.pop()
    if (node.type === 'directory' && String(node.path).replace(/\/+$/, '') === normalized) return node
    if (Array.isArray(node.children) && node.children.length) stack.push(...node.children)
  }
  return null
}

// Write file content (used by paste, overwrites the target path)
async function writeFileContent(agentId, absPath, content) {
  const { host, port } = getGatewayAddress()
  const agent = resolveFileTreeAgent(agentId)
  if (!agent) throw new Error(`Agent not found: ${agentId}`)
  if (!agent.node_id) throw new Error(`Agent has no node_id: ${agentId}`)
  const targetNodeId = String(agent.node_id).trim()
  const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, 'file-write'), {
    method: 'POST',
    body: JSON.stringify({ path: absPath, content, node_id: targetNodeId })
  })
  const result = await response.json()
  if (!response.ok || !result.success) {
    throw new Error(result.error?.message || 'Failed to write file')
  }
  return result.data
}

function initFileTreeState(agentId) {
  if (!fileTreeState.value.has(agentId)) {
    fileTreeState.value.set(agentId, [])
    fileTreeExpanded.value.set(agentId, new Set())
    fileTreeLoading.value.set(agentId, new Set())
  }
}

// Load the child directories of a file tree node
async function loadFileTreeNode(agentId, node) {
  const loadingSet = fileTreeLoading.value.get(agentId)
  if (!loadingSet) return
  
  // Mark as loading
  loadingSet.add(node.path)
  
  try {
    const { host, port } = getGatewayAddress()
    // Use the current Agent's node_id, not the editor session's node_id
    // Virtual directory sessions (opening a node's directory directly without creating an Agent) are not in agentList; get node_id from their agent info
    const agent = agentList.value.find(a => a.agent_id === agentId) || getVirtualWorkspaceAgent(agentId)
    if (!agent) {
      console.error('[FILETREE] Agent not found:', agentId)
      return
    }
    if (!agent.node_id) {
      console.error('[FILETREE] Agent has no node_id:', agent)
      return
    }
    const targetNodeId = String(agent.node_id).trim()
    const response = await fetchWithAuth(buildNodeHttpUrl(host, port, targetNodeId, `directories?path=${encodeURIComponent(node.path)}`))
    
    if (!response.ok) {
      const error = await response.json()
      console.error('[FILETREE] Failed to load directory:', error)
      return
    }
    
    const result = await response.json()
    if (result.success && result.data) {
      // Convert to tree node format
      const children = (result.data.items || []).map(item => {
        // File nodes do not need children and loaded fields
        if (item.type === 'file') {
          return {
            name: item.name,
            path: item.path,
            type: 'file'
          }
        }
        // Directory nodes need children and loaded fields
        return {
          name: item.name,
          path: item.path,
          type: 'directory',
          expanded: false,
          loaded: false,
          children: []
        }
      })
      
      // Update the node's children
      node.children = children
      node.loaded = true
    }
  } catch (error) {
    console.error('[FILETREE] Error loading directory:', error)
  } finally {
    // Remove the loading state
    loadingSet.delete(node.path)
  }
}

// Initialize the file tree (load the root directory)
async function initFileTree(agentId, rootPath) {
  initFileTreeState(agentId)
  
  // Create the root node
  const rootNode = {
    name: rootPath.split('/').pop() || rootPath,
    path: rootPath,
    type: 'directory',
    expanded: false,
    loaded: false,
    children: []
  }
  
  // Load the contents of the root directory
  await loadFileTreeNode(agentId, rootNode)
  
  // Save to state
  fileTreeState.value.set(agentId, [rootNode])
}

function flattenVisibleFileTreeNodes(nodes, depth = 0) {
  const visibleNodes = []

  for (const node of nodes) {
    visibleNodes.push({ node, depth })

    if (node.expanded && node.children && node.children.length > 0) {
      visibleNodes.push(...flattenVisibleFileTreeNodes(node.children, depth + 1))
    }
  }

  return visibleNodes
}

function getVisibleFileTreeNodes(agentId) {
  const treeNodes = fileTreeState.value.get(agentId) || []
  return flattenVisibleFileTreeNodes(treeNodes)
}

// Recursively find a node
function findNode(nodes, path) {
  for (const node of nodes) {
    if (node.path === path) {
      return node
    }
    if (node.children && node.children.length > 0) {
      const found = findNode(node.children, path)
      if (found) return found
    }
  }
  return null
}

// Toggle node expand/collapse
async function toggleNodeExpand(agentId, node) {
  const expandedSet = fileTreeExpanded.value.get(agentId)
  if (!expandedSet) return
  
  if (node.expanded) {
    // Collapse
    node.expanded = false
    expandedSet.delete(node.path)
  } else {
    // Expand
    node.expanded = true
    expandedSet.add(node.path)
    
    // Load children if they have not been loaded yet
    if (!node.loaded) {
      await loadFileTreeNode(agentId, node)
    }
  }
}

  return {
    // State (kept for App.vue code/template access)
    fileTreeState,
    fileTreeExpanded,
    fileTreeLoading,
    expandedAgents,
    selectedAgentId,
    fileTreeSelectedPath,
    fileTreeSelectedAgentId,
    fileTreeContextMenu,
    fileTreeUploadInput,
    inputPrompt,
    fileTreeDropTargetPath,
    // Node interaction
    getFileTypeIcon,
    handleFileTreeNodeClick,
    selectFileTreeNode,
    focusFileTreeContainer,
    revealTabInFileTree,
    toggleAgentExpanded,
    toggleStoppedNodeCollapse,
    isStoppedNodeCollapsed,
    // Keyboard navigation
    handleFileTreeKeydown,
    // Context menu
    copyTextToClipboard,
    openFileTreeContextMenu,
    cancelInputPrompt,
    confirmInputPrompt,
    fileTreeContextActions,
    runFileTreeContextAction,
    // Upload/download
    readFileAsDataUrl,
    onFileTreeUploadInputChange,
    // Drag and drop
    handleFileTreeDragStart,
    handleFileTreeDragEnd,
    handleFileTreeDragOver,
    handleFileTreeDragLeave,
    handleFileTreeDrop,
    // Core loading
    initFileTree,
    getVisibleFileTreeNodes,
  }
}