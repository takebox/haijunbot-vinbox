// useFileTree unit tests
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useFileTree } from './useFileTree.js'

// Build a useFileTree dependency-injection harness
function makeAgent({ id = 'agent-1', nodeId = 'node-1', workingDir = '/home/user/proj', virtual = false } = {}) {
  return { agent_id: id, node_id: nodeId, working_dir: workingDir, virtual }
}

function makeHarness({ agent = null, directoryItems = [], fetchImpl } = {}) {
  const agentList = ref(agent ? [agent] : [])
  const getVirtualWorkspaceAgent = vi.fn((agentId) => (agent && agent.agent_id === agentId ? agent : null))
  const resolveFileTreeAgent = vi.fn((agentId) => (agent && agent.agent_id === agentId ? agent : null))
  const resolveAgentForPath = vi.fn((_path) => (agent ? { agentId: agent.agent_id, agent } : null))
  const openWorkspaceFile = vi.fn()
  const setWorkspaceSidebarView = vi.fn()
  const removeWorkspaceDir = vi.fn()
  const fetchFileContent = vi.fn(async (path) => `content-of-${path}`)
  const fetchWithAuth = vi.fn(
    fetchImpl ||
      (async (url) => {
        const path = String(url).split('/').pop()
        if (path.startsWith('directories?')) {
          return { ok: true, json: async () => ({ success: true, data: { items: directoryItems } }) }
        }
        return { ok: true, json: async () => ({ success: true, data: {} }) }
      })
  )
  const buildNodeHttpUrl = vi.fn((host, port, nodeId, path) => `http://${host}:${port}/api/node/${nodeId}/${path}`)
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const showToast = vi.fn()
  const showConfirm = vi.fn((msg, onOk) => onOk && onOk())
  const globalSearchFileGlob = ref('')
  const ensureWorkspaceSidebarFileTree = vi.fn()
  const api = useFileTree({
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
  })
  return {
    api,
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
  }
}

// Wait for all microtasks/macrotasks to complete (internal async chain)
const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

describe('useFileTree', () => {
  beforeEach(() => {
    // CSS.escape may be missing in jsdom; mock it to avoid scrollFileTreeNodeIntoView failing
    globalThis.CSS = globalThis.CSS || {}
    globalThis.CSS.escape = globalThis.CSS.escape || ((s) => s)
  })

  it('exposes the expected interface', () => {
    const { api } = makeHarness()
    // State refs
    expect(typeof api.fileTreeState).toBe('object')
    expect(typeof api.fileTreeExpanded).toBe('object')
    expect(typeof api.fileTreeLoading).toBe('object')
    expect(typeof api.expandedAgents).toBe('object')
    expect(typeof api.selectedAgentId).toBe('object')
    expect(typeof api.fileTreeSelectedPath).toBe('object')
    expect(typeof api.fileTreeSelectedAgentId).toBe('object')
    expect(typeof api.fileTreeContextMenu).toBe('object')
    expect(typeof api.fileTreeUploadInput).toBe('object')
    expect(typeof api.inputPrompt).toBe('object')
    expect(typeof api.fileTreeDropTargetPath).toBe('object')
    // Functions
    expect(typeof api.initFileTree).toBe('function')
    expect(typeof api.getVisibleFileTreeNodes).toBe('function')
    expect(typeof api.toggleAgentExpanded).toBe('function')
    expect(typeof api.handleFileTreeKeydown).toBe('function')
    expect(typeof api.runFileTreeContextAction).toBe('function')
    expect(typeof api.handleFileTreeDrop).toBe('function')
  })

  it('initial state', () => {
    const { api } = makeHarness()
    expect(api.fileTreeState.value.size).toBe(0)
    expect(api.expandedAgents.value.size).toBe(0)
    expect(api.selectedAgentId.value).toBeNull()
    expect(api.fileTreeSelectedPath.value).toBeNull()
    expect(api.fileTreeSelectedAgentId.value).toBeNull()
    expect(api.fileTreeContextMenu.value.visible).toBe(false)
    expect(api.inputPrompt.value.visible).toBe(false)
    expect(api.fileTreeDropTargetPath.value).toBe('')
  })

  describe('initFileTree', () => {
    it('initializes state and creates the root node', async () => {
      const agent = makeAgent()
      const { api, fetchWithAuth } = makeHarness({ agent })
      await api.initFileTree('agent-1', '/home/user/proj')
      expect(api.fileTreeState.value.has('agent-1')).toBe(true)
      expect(api.fileTreeExpanded.value.has('agent-1')).toBe(true)
      expect(api.fileTreeLoading.value.has('agent-1')).toBe(true)
      const roots = api.fileTreeState.value.get('agent-1')
      expect(roots.length).toBe(1)
      const root = roots[0]
      expect(root.name).toBe('proj')
      expect(root.path).toBe('/home/user/proj')
      expect(root.type).toBe('directory')
      expect(root.expanded).toBe(false)
      expect(fetchWithAuth).toHaveBeenCalled()
    })

    it('root loads child nodes: file nodes have no children/loaded, directory nodes do', async () => {
      const agent = makeAgent()
      const { api } = makeHarness({
        agent,
        directoryItems: [
          { name: 'main.js', path: '/home/user/proj/main.js', type: 'file' },
          { name: 'src', path: '/home/user/proj/src', type: 'directory' },
        ],
      })
      await api.initFileTree('agent-1', '/home/user/proj')
      const root = api.fileTreeState.value.get('agent-1')[0]
      expect(root.loaded).toBe(true)
      const fileNode = root.children.find((c) => c.name === 'main.js')
      expect(fileNode.type).toBe('file')
      expect(fileNode.children).toBeUndefined()
      expect(fileNode.loaded).toBeUndefined()
      const dirNode = root.children.find((c) => c.name === 'src')
      expect(dirNode.type).toBe('directory')
      expect(dirNode.children).toEqual([])
      expect(dirNode.loaded).toBe(false)
      expect(dirNode.expanded).toBe(false)
    })
  })

  describe('toggleNodeExpand (triggered via handleFileTreeNodeClick) / getVisibleFileTreeNodes', () => {
    it('expanding an unloaded node loads its children; calling again collapses', async () => {
      const agent = makeAgent()
      const { api, fetchWithAuth } = makeHarness({
        agent,
        directoryItems: [{ name: 'src', path: '/home/user/proj/src', type: 'directory' }],
      })
      await api.initFileTree('agent-1', '/home/user/proj')
      // The root was already loaded by initFileTree; the src subdirectory is not yet loaded
      const root = api.fileTreeState.value.get('agent-1')[0]
      const srcNode = root.children.find((c) => c.name === 'src')
      expect(srcNode.loaded).toBe(false)
      const callsBefore = fetchWithAuth.mock.calls.length
      // Expand src (internally calls toggleNodeExpand → loadFileTreeNode)
      await api.handleFileTreeNodeClick('agent-1', srcNode)
      expect(srcNode.expanded).toBe(true)
      expect(api.fileTreeExpanded.value.get('agent-1').has(srcNode.path)).toBe(true)
      expect(fetchWithAuth.mock.calls.length).toBeGreaterThan(callsBefore) // children were loaded
      expect(srcNode.loaded).toBe(true)
      // Collapse
      await api.handleFileTreeNodeClick('agent-1', srcNode)
      expect(srcNode.expanded).toBe(false)
      expect(api.fileTreeExpanded.value.get('agent-1').has(srcNode.path)).toBe(false)
    })

    it('re-expanding an already loaded node does not request the backend again', async () => {
      const agent = makeAgent()
      const { api, fetchWithAuth } = makeHarness({
        agent,
        directoryItems: [{ name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }],
      })
      await api.initFileTree('agent-1', '/home/user/proj')
      const root = api.fileTreeState.value.get('agent-1')[0]
      await api.handleFileTreeNodeClick('agent-1', root)
      const callsAfterFirstExpand = fetchWithAuth.mock.calls.length
      await api.handleFileTreeNodeClick('agent-1', root) // collapse
      await api.handleFileTreeNodeClick('agent-1', root) // expand again (already loaded)
      expect(fetchWithAuth.mock.calls.length).toBe(callsAfterFirstExpand)
    })

    it('getVisibleFileTreeNodes flattens according to expansion state', async () => {
      const agent = makeAgent()
      const { api } = makeHarness({
        agent,
        directoryItems: [
          { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' },
          { name: 'src', path: '/home/user/proj/src', type: 'directory' },
        ],
      })
      await api.initFileTree('agent-1', '/home/user/proj')
      const root = api.fileTreeState.value.get('agent-1')[0]
      // When collapsed there is only the root
      expect(api.getVisibleFileTreeNodes('agent-1').map((x) => x.node.path)).toEqual(['/home/user/proj'])
      // After expanding the root, child nodes appear
      await api.handleFileTreeNodeClick('agent-1', root)
      const visible = api.getVisibleFileTreeNodes('agent-1').map((x) => x.node.path)
      expect(visible).toEqual(['/home/user/proj', '/home/user/proj/a.js', '/home/user/proj/src'])
      // Depth: root 0, child nodes 1
      const depths = api.getVisibleFileTreeNodes('agent-1').map((x) => x.depth)
      expect(depths).toEqual([0, 1, 1])
    })
  })

  describe('getFileTypeIcon', () => {
    it('returns the folder SVG for directories', () => {
      const { api } = makeHarness()
      const icon = api.getFileTypeIcon({ name: 'src', path: '/x/src', type: 'directory' })
      expect(icon).toContain('<svg')
    })
    it('maps icons by extension', () => {
      const { api } = makeHarness()
      expect(api.getFileTypeIcon({ name: 'main.js', path: '/x/main.js', type: 'file' })).toContain('/file-icons/javascript.svg')
      expect(api.getFileTypeIcon({ name: 'app.py', path: '/x/app.py', type: 'file' })).toContain('/file-icons/python.svg')
      expect(api.getFileTypeIcon({ name: 'readme.md', path: '/x/readme.md', type: 'file' })).toContain('/file-icons/markdown.svg')
    })
    it('falls back to the generic file icon for unknown extensions', () => {
      const { api } = makeHarness()
      expect(api.getFileTypeIcon({ name: 'unknown.zzz', path: '/x/unknown.zzz', type: 'file' })).toContain('/file-icons/document.svg')
    })
    it('matches by full file name (.gitignore)', () => {
      const { api } = makeHarness()
      expect(api.getFileTypeIcon({ name: '.gitignore', path: '/x/.gitignore', type: 'file' })).toContain('/file-icons/git.svg')
    })
  })

  describe('handleFileTreeNodeClick / selectFileTreeNode', () => {
    it('clicking a directory toggles expansion', async () => {
      const agent = makeAgent()
      const { api } = makeHarness({ agent })
      await api.initFileTree('agent-1', '/home/user/proj')
      const root = api.fileTreeState.value.get('agent-1')[0]
      await api.handleFileTreeNodeClick('agent-1', root)
      expect(root.expanded).toBe(true)
    })
    it('clicking a file opens the workspace file', async () => {
      const agent = makeAgent()
      const { api, openWorkspaceFile } = makeHarness({ agent })
      const fileNode = { name: 'main.js', path: '/home/user/proj/main.js', type: 'file' }
      await api.handleFileTreeNodeClick('agent-1', fileNode)
      expect(openWorkspaceFile).toHaveBeenCalledWith('/home/user/proj/main.js', 'agent-1')
    })
    it('selectFileTreeNode records the cursor selection', () => {
      const { api } = makeHarness()
      api.selectFileTreeNode('agent-1', { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' })
      expect(api.fileTreeSelectedAgentId.value).toBe('agent-1')
      expect(api.fileTreeSelectedPath.value).toBe('/home/user/proj/a.js')
    })
  })

  describe('toggleAgentExpanded', () => {
    it('expands the Agent and initializes the file tree', async () => {
      const agent = makeAgent()
      const { api } = makeHarness({ agent })
      api.toggleAgentExpanded('agent-1')
      expect(api.selectedAgentId.value).toBe('agent-1')
      expect(api.expandedAgents.value.has('agent-1')).toBe(true)
      await flush()
      expect(api.fileTreeState.value.has('agent-1')).toBe(true)
    })
    it('calling again collapses the Agent', () => {
      const agent = makeAgent()
      const { api } = makeHarness({ agent })
      api.toggleAgentExpanded('agent-1')
      api.toggleAgentExpanded('agent-1')
      expect(api.expandedAgents.value.has('agent-1')).toBe(false)
    })
  })

  describe('toggleStoppedNodeCollapse / isStoppedNodeCollapsed', () => {
    it('toggles the collapse state', () => {
      const { api } = makeHarness()
      expect(api.isStoppedNodeCollapsed('n1')).toBe(false)
      api.toggleStoppedNodeCollapse('n1')
      expect(api.isStoppedNodeCollapsed('n1')).toBe(true)
      api.toggleStoppedNodeCollapse('n1')
      expect(api.isStoppedNodeCollapsed('n1')).toBe(false)
    })
  })

  describe('handleFileTreeKeydown', () => {
    it('ArrowDown moves the cursor to the next visible node', async () => {
      const agent = makeAgent()
      const { api } = makeHarness({
        agent,
        directoryItems: [
          { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' },
          { name: 'b.js', path: '/home/user/proj/b.js', type: 'file' },
        ],
      })
      await api.initFileTree('agent-1', '/home/user/proj')
      const root = api.fileTreeState.value.get('agent-1')[0]
      await api.handleFileTreeNodeClick('agent-1', root)
      // Initially nothing selected → ArrowDown selects the first visible node (the root)
      const evt = { key: 'ArrowDown', preventDefault: vi.fn() }
      await api.handleFileTreeKeydown(evt, 'agent-1')
      expect(evt.preventDefault).toHaveBeenCalled()
      expect(api.fileTreeSelectedPath.value).toBe('/home/user/proj')
      // Press ArrowDown again → selects a.js
      const evt2 = { key: 'ArrowDown', preventDefault: vi.fn() }
      await api.handleFileTreeKeydown(evt2, 'agent-1')
      expect(api.fileTreeSelectedPath.value).toBe('/home/user/proj/a.js')
    })
    it('Enter opens the selected file', async () => {
      const agent = makeAgent()
      const { api, openWorkspaceFile } = makeHarness({
        agent,
        directoryItems: [{ name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }],
      })
      await api.initFileTree('agent-1', '/home/user/proj')
      const root = api.fileTreeState.value.get('agent-1')[0]
      await api.handleFileTreeNodeClick('agent-1', root)
      api.selectFileTreeNode('agent-1', { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' })
      const evt = { key: 'Enter', preventDefault: vi.fn() }
      await api.handleFileTreeKeydown(evt, 'agent-1')
      expect(evt.preventDefault).toHaveBeenCalled()
      expect(openWorkspaceFile).toHaveBeenCalledWith('/home/user/proj/a.js', 'agent-1')
    })
  })

  describe('inputPrompt', () => {
    it('confirmInputPrompt keeps the modal open on validation failure', () => {
      const { api } = makeHarness()
      api.inputPrompt.value = {
        visible: true,
        title: 't',
        label: 'l',
        placeholder: 'p',
        value: '',
        error: '',
        onConfirm: () => 'Name cannot be empty',
      }
      api.confirmInputPrompt()
      expect(api.inputPrompt.value.visible).toBe(true)
      expect(api.inputPrompt.value.error).toBe('Name cannot be empty')
    })
    it('confirmInputPrompt closes the modal on success', () => {
      const { api } = makeHarness()
      const onConfirm = vi.fn(() => null)
      api.inputPrompt.value = {
        visible: true,
        title: 't',
        label: 'l',
        placeholder: 'p',
        value: 'x',
        error: '',
        onConfirm,
      }
      api.confirmInputPrompt()
      expect(onConfirm).toHaveBeenCalledWith('x')
      expect(api.inputPrompt.value.visible).toBe(false)
    })
    it('cancelInputPrompt closes the modal', () => {
      const { api } = makeHarness()
      api.inputPrompt.value = { ...api.inputPrompt.value, visible: true, onConfirm: () => null }
      api.cancelInputPrompt()
      expect(api.inputPrompt.value.visible).toBe(false)
    })
  })

  describe('openFileTreeContextMenu', () => {
    it('pops up the menu within the viewport and records the coordinates', () => {
      const { api } = makeHarness()
      const agent = makeAgent()
      const event = { clientX: 100, clientY: 100 }
      api.openFileTreeContextMenu(agent, null, event)
      expect(api.fileTreeContextMenu.value.visible).toBe(true)
      expect(api.fileTreeContextMenu.value.agentId).toBe('agent-1')
      expect(api.fileTreeContextMenu.value.node).toBeNull()
      expect(api.fileTreeContextMenu.value.x).toBe(100)
      expect(api.fileTreeContextMenu.value.y).toBe(100)
    })
    it('does not pop up when there is no agent or event', () => {
      const { api } = makeHarness()
      api.openFileTreeContextMenu(null, null, { clientX: 0, clientY: 0 })
      api.openFileTreeContextMenu(makeAgent(), null, null)
      expect(api.fileTreeContextMenu.value.visible).toBe(false)
    })
  })

  describe('fileTreeContextActions', () => {
    it('at the root (no node) only Agent-level actions are available', () => {
      const { api } = makeHarness({ agent: makeAgent() })
      api.openFileTreeContextMenu(makeAgent(), null, { clientX: 0, clientY: 0 })
      const actions = api.fileTreeContextActions.value
      const ids = actions.filter((a) => a.enabled).map((a) => a.id)
      // No node: new/find/refresh/upload/copy-path/relative-path are available; download/copy/cut/rename/delete are not
      expect(ids).toContain('new-file')
      expect(ids).toContain('refresh')
      expect(ids).toContain('upload')
      expect(ids).toContain('copy-path')
      expect(ids).not.toContain('download')
      expect(ids).not.toContain('copy')
      expect(ids).not.toContain('rename')
      expect(ids).not.toContain('delete')
    })
    it('on a file node download/copy/cut/rename/delete are available', () => {
      const { api } = makeHarness({ agent: makeAgent() })
      const fileNode = { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }
      api.openFileTreeContextMenu(makeAgent(), fileNode, { clientX: 0, clientY: 0 })
      const actions = api.fileTreeContextActions.value
      const ids = actions.filter((a) => a.enabled).map((a) => a.id)
      expect(ids).toContain('download')
      expect(ids).toContain('copy')
      expect(ids).toContain('cut')
      expect(ids).toContain('rename')
      expect(ids).toContain('delete')
    })
  })

  describe('runFileTreeContextAction', () => {
    it('new file: opens the input prompt, then calls the backend and refreshes on confirm', async () => {
      const agent = makeAgent()
      const { api, fetchWithAuth, showToast, openWorkspaceFile } = makeHarness({ agent })
      api.openFileTreeContextMenu(agent, null, { clientX: 0, clientY: 0 })
      const action = api.fileTreeContextActions.value.find((a) => a.id === 'new-file')
      await api.runFileTreeContextAction(action)
      expect(api.inputPrompt.value.visible).toBe(true)
      expect(api.inputPrompt.value.title).toContain('New file')
      // Confirm
      api.inputPrompt.value.value = 'hello.txt'
      api.confirmInputPrompt()
      await flush()
      // Creation request
      const createCall = fetchWithAuth.mock.calls.find((c) => String(c[0]).includes('file-create'))
      expect(createCall).toBeTruthy()
      const body = JSON.parse(createCall[1].body)
      expect(body.path).toBe('/home/user/proj/hello.txt')
      expect(body.kind).toBe('file')
      expect(openWorkspaceFile).toHaveBeenCalledWith('/home/user/proj/hello.txt', 'agent-1')
      expect(showToast).toHaveBeenCalledWith('file created', 'success')
    })
    it('new file: validation fails when the name is empty', async () => {
      const agent = makeAgent()
      const { api, fetchWithAuth } = makeHarness({ agent })
      api.openFileTreeContextMenu(agent, null, { clientX: 0, clientY: 0 })
      const action = api.fileTreeContextActions.value.find((a) => a.id === 'new-file')
      await api.runFileTreeContextAction(action)
      api.inputPrompt.value.value = '   '
      api.confirmInputPrompt()
      expect(api.inputPrompt.value.visible).toBe(true)
      expect(api.inputPrompt.value.error).toBe('Name cannot be empty')
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })
    it('delete file: calls the backend and refreshes after confirm', async () => {
      const agent = makeAgent()
      const { api, fetchWithAuth, showToast, showConfirm } = makeHarness({ agent })
      const fileNode = { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }
      api.openFileTreeContextMenu(agent, fileNode, { clientX: 0, clientY: 0 })
      const action = api.fileTreeContextActions.value.find((a) => a.id === 'delete')
      await api.runFileTreeContextAction(action)
      expect(showConfirm).toHaveBeenCalled()
      await flush()
      const deleteCall = fetchWithAuth.mock.calls.find((c) => String(c[0]).includes('file-delete'))
      expect(deleteCall).toBeTruthy()
      const body = JSON.parse(deleteCall[1].body)
      expect(body.path).toBe('/home/user/proj/a.js')
      expect(showToast).toHaveBeenCalledWith('Deleted', 'success')
    })
    it('copy path: calls the clipboard and toasts', async () => {
      const agent = makeAgent()
      const { api, showToast } = makeHarness({ agent })
      const fileNode = { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }
      api.openFileTreeContextMenu(agent, fileNode, { clientX: 0, clientY: 0 })
      // Mock navigator.clipboard
      const writeText = vi.fn().mockResolvedValue(undefined)
      Object.defineProperty(globalThis.navigator, 'clipboard', { value: { writeText }, configurable: true })
      const action = api.fileTreeContextActions.value.find((a) => a.id === 'copy-path')
      await api.runFileTreeContextAction(action)
      expect(writeText).toHaveBeenCalledWith('/home/user/proj/a.js')
      expect(showToast).toHaveBeenCalledWith('Path copied', 'success')
    })
    it('remove-dir: calls removeWorkspaceDir', async () => {
      const agent = makeAgent({ virtual: true })
      const { api, removeWorkspaceDir } = makeHarness({ agent })
      api.openFileTreeContextMenu(agent, null, { clientX: 0, clientY: 0 })
      const action = api.fileTreeContextActions.value.find((a) => a.id === 'remove-dir')
      expect(action.enabled).toBe(true)
      await api.runFileTreeContextAction(action)
      expect(removeWorkspaceDir).toHaveBeenCalledWith('agent-1')
    })
    it('find-in-folder: sets the search glob and switches to the search view', async () => {
      const agent = makeAgent()
      const { api, globalSearchFileGlob, setWorkspaceSidebarView } = makeHarness({ agent })
      const dirNode = { name: 'src', path: '/home/user/proj/src', type: 'directory' }
      api.openFileTreeContextMenu(agent, dirNode, { clientX: 0, clientY: 0 })
      const action = api.fileTreeContextActions.value.find((a) => a.id === 'find-in-folder')
      await api.runFileTreeContextAction(action)
      expect(globalSearchFileGlob.value).toBe('src/**')
      expect(setWorkspaceSidebarView).toHaveBeenCalledWith('search')
    })
  })

  describe('drag and drop', () => {
    it('handleFileTreeDragStart records the source node', () => {
      const agent = makeAgent()
      const { api } = makeHarness({ agent })
      const fileNode = { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }
      const event = { dataTransfer: { effectAllowed: '', setData: vi.fn() } }
      api.handleFileTreeDragStart(event, 'agent-1', fileNode)
      expect(event.dataTransfer.effectAllowed).toBe('copyMove')
      expect(event.dataTransfer.setData).toHaveBeenCalledWith('text/plain', '/home/user/proj/a.js')
    })
    it('handleFileTreeDragOver rejects invalid targets (itself/the source directory/descendant directories)', () => {
      const agent = makeAgent()
      const { api } = makeHarness({ agent })
      const dirNode = { name: 'src', path: '/home/user/proj/src', type: 'directory' }
      const startEvent = { dataTransfer: { effectAllowed: '', setData: vi.fn() } }
      api.handleFileTreeDragStart(startEvent, 'agent-1', dirNode)
      // Cannot drag onto itself
      const selfEvent = { preventDefault: vi.fn(), dataTransfer: { dropEffect: '' } }
      api.handleFileTreeDragOver(selfEvent, '/home/user/proj/src')
      expect(selfEvent.preventDefault).not.toHaveBeenCalled()
      expect(api.fileTreeDropTargetPath.value).toBe('')
      // Cannot drag into the source directory
      const parentEvent = { preventDefault: vi.fn(), dataTransfer: { dropEffect: '' } }
      api.handleFileTreeDragOver(parentEvent, '/home/user/proj')
      expect(parentEvent.preventDefault).not.toHaveBeenCalled()
      // A directory cannot be dragged into its own descendant directory
      const childEvent = { preventDefault: vi.fn(), dataTransfer: { dropEffect: '' } }
      api.handleFileTreeDragOver(childEvent, '/home/user/proj/src/sub')
      expect(childEvent.preventDefault).not.toHaveBeenCalled()
    })
    it('handleFileTreeDragOver highlights a valid target and sets dropEffect', () => {
      const agent = makeAgent()
      const { api } = makeHarness({ agent })
      const fileNode = { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }
      const startEvent = { dataTransfer: { effectAllowed: '', setData: vi.fn() } }
      api.handleFileTreeDragStart(startEvent, 'agent-1', fileNode)
      const overEvent = { preventDefault: vi.fn(), dataTransfer: { dropEffect: '' }, ctrlKey: true }
      api.handleFileTreeDragOver(overEvent, '/home/user/proj/src')
      expect(overEvent.preventDefault).toHaveBeenCalled()
      expect(overEvent.dataTransfer.dropEffect).toBe('copy')
      expect(api.fileTreeDropTargetPath.value).toBe('/home/user/proj/src')
      // Leaving clears the highlight
      api.handleFileTreeDragLeave('/home/user/proj/src')
      expect(api.fileTreeDropTargetPath.value).toBe('')
    })
    it('handleFileTreeDragEnd cleans up the drag state', () => {
      const agent = makeAgent()
      const { api } = makeHarness({ agent })
      const fileNode = { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }
      const startEvent = { dataTransfer: { effectAllowed: '', setData: vi.fn() } }
      api.handleFileTreeDragStart(startEvent, 'agent-1', fileNode)
      api.handleFileTreeDragEnd()
      expect(api.fileTreeDropTargetPath.value).toBe('')
    })
  })

  describe('copy/paste', () => {
    it('copying a file then pasting into another directory (calls file-rename for move / file-write for copy)', async () => {
      const agent = makeAgent()
      const { api, fetchWithAuth, fetchFileContent, showToast } = makeHarness({ agent })
      // Copy: via the context menu copy
      const fileNode = { name: 'a.js', path: '/home/user/proj/a.js', type: 'file' }
      api.openFileTreeContextMenu(agent, fileNode, { clientX: 0, clientY: 0 })
      const copyAction = api.fileTreeContextActions.value.find((a) => a.id === 'copy')
      await api.runFileTreeContextAction(copyAction)
      expect(fetchFileContent).toHaveBeenCalledWith('/home/user/proj/a.js', 'agent-1')
      expect(showToast).toHaveBeenCalledWith('Copied, can paste into the target directory', 'success')
      // Paste into the src directory
      const dirNode = { name: 'src', path: '/home/user/proj/src', type: 'directory' }
      api.openFileTreeContextMenu(agent, dirNode, { clientX: 0, clientY: 0 })
      const pasteAction = api.fileTreeContextActions.value.find((a) => a.id === 'paste')
      expect(pasteAction.enabled).toBe(true)
      await api.runFileTreeContextAction(pasteAction)
      await flush()
      const writeCall = fetchWithAuth.mock.calls.find((c) => String(c[0]).includes('file-write'))
      expect(writeCall).toBeTruthy()
      const body = JSON.parse(writeCall[1].body)
      expect(body.path).toBe('/home/user/proj/src/a.js')
      expect(body.content).toBe('content-of-/home/user/proj/a.js')
    })
  })
})
