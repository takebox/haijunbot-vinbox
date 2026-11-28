// useDiff unit tests
import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { useDiff } from './useDiff.js'

function makeHarness({ windowWidthValue = 1200 } = {}) {
  const windowWidth = ref(windowWidthValue)
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const getCurrentAgentNodeId = vi.fn(() => '')
  const fetchWithAuth = vi.fn()
  const buildNodeHttpUrl = vi.fn((host, port, nodeId, path) => `http://${host}:${port}/api/node/${nodeId}/${path}`)
  const api = useDiff({
    windowWidth,
    getGatewayAddress,
    getCurrentAgentNodeId,
    fetchWithAuth,
    buildNodeHttpUrl
  })
  return { api, windowWidth, getGatewayAddress, getCurrentAgentNodeId, fetchWithAuth, buildNodeHttpUrl }
}

// Build a valid diff file object (matching the backend response shape)
function makeFile(filePath, additions, deletions, rows) {
  return { file_path: filePath, additions, deletions, rows }
}

describe('useDiff', () => {
  it('exposes the expected API', () => {
    const { api } = makeHarness()
    expect(typeof api.showDiffModal).toBe('object') // ref
    expect(typeof api.diffFiles).toBe('object') // ref
    expect(typeof api.diffActiveIndex).toBe('object') // ref
    expect(typeof api.diffLoading).toBe('object') // ref
    expect(typeof api.diffError).toBe('object') // ref
    expect(typeof api.diffMobileShowDetail).toBe('object') // ref
    expect(typeof api.diffActiveHtml).toBe('object') // computed ref
    expect(typeof api.selectDiffFile).toBe('function')
    expect(typeof api.viewDiff).toBe('function')
  })

  it('initial state: modal hidden, no files, no error, not loading', () => {
    const { api } = makeHarness()
    expect(api.showDiffModal.value).toBe(false)
    expect(api.diffFiles.value).toEqual([])
    expect(api.diffActiveIndex.value).toBe(0)
    expect(api.diffLoading.value).toBe(false)
    expect(api.diffError.value).toBe('')
    expect(api.diffMobileShowDetail.value).toBe(false)
    expect(api.diffActiveHtml.value).toBe('')
  })

  describe('diffActiveHtml', () => {
    it('returns an empty string when no file is selected', () => {
      const { api } = makeHarness()
      expect(api.diffActiveHtml.value).toBe('')
    })
    it('returns the rendered result (non-empty HTML) when a file is selected', () => {
      const { api } = makeHarness()
      const file = makeFile('a.py', 1, 0, [{ type: 'insert', content: 'x = 1' }])
      api.diffFiles.value = [file]
      api.diffActiveIndex.value = 0
      expect(typeof api.diffActiveHtml.value).toBe('string')
      expect(api.diffActiveHtml.value.length).toBeGreaterThan(0)
    })
    it('updates as the selected file index changes', () => {
      const { api } = makeHarness()
      const fileA = makeFile('a.py', 1, 0, [{ type: 'insert', content: 'a' }])
      const fileB = makeFile('b.py', 0, 1, [{ type: 'delete', content: 'b' }])
      api.diffFiles.value = [fileA, fileB]
      api.diffActiveIndex.value = 0
      const htmlA = api.diffActiveHtml.value
      api.diffActiveIndex.value = 1
      const htmlB = api.diffActiveHtml.value
      expect(htmlA).not.toBe(htmlB)
    })
  })

  describe('selectDiffFile', () => {
    it('desktop: switches the index without entering mobile detail', () => {
      const { api } = makeHarness({ windowWidthValue: 1200 })
      api.selectDiffFile(2)
      expect(api.diffActiveIndex.value).toBe(2)
      expect(api.diffMobileShowDetail.value).toBe(false)
    })
    it('mobile (<=768): switches the index and enters the fullscreen detail', () => {
      const { api } = makeHarness({ windowWidthValue: 768 })
      api.selectDiffFile(1)
      expect(api.diffActiveIndex.value).toBe(1)
      expect(api.diffMobileShowDetail.value).toBe(true)
    })
    it('mobile boundary: 768 counts as a narrow viewport', () => {
      const { api } = makeHarness({ windowWidthValue: 768 })
      api.selectDiffFile(0)
      expect(api.diffMobileShowDetail.value).toBe(true)
    })
  })

  describe('viewDiff', () => {
    it('invalid agent (no agent_id) returns early without requesting', async () => {
      const { api, fetchWithAuth } = makeHarness()
      await api.viewDiff(null)
      await api.viewDiff({})
      expect(fetchWithAuth).not.toHaveBeenCalled()
      expect(api.showDiffModal.value).toBe(false)
    })

    it('on success: fetches the structured diff and fills the file list', async () => {
      const { api, fetchWithAuth, buildNodeHttpUrl, getGatewayAddress } = makeHarness()
      const file = makeFile('src/a.js', 3, 1, [
        { type: 'equal', content: 'line1' },
        { type: 'insert', content: 'line2' },
        { type: 'delete', content: 'line3' }
      ])
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ files: [file] })
      })
      await api.viewDiff({ agent_id: 'agent-1' })
      expect(api.showDiffModal.value).toBe(true)
      expect(api.diffLoading.value).toBe(false)
      expect(api.diffError.value).toBe('')
      expect(api.diffFiles.value).toEqual([file])
      expect(api.diffActiveIndex.value).toBe(0)
      expect(api.diffMobileShowDetail.value).toBe(false)
      // The correct node URL was built
      expect(getGatewayAddress).toHaveBeenCalled()
      expect(buildNodeHttpUrl).toHaveBeenCalledWith('127.0.0.1', '8000', 'master', 'agent/agent-1/diff')
      expect(fetchWithAuth).toHaveBeenCalledTimes(1)
    })

    it('on success: uses the agent node when node_id is set', async () => {
      const { api, fetchWithAuth, buildNodeHttpUrl } = makeHarness()
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ files: [] })
      })
      await api.viewDiff({ agent_id: 'agent-1', node_id: 'node-9' })
      expect(buildNodeHttpUrl).toHaveBeenCalledWith('127.0.0.1', '8000', 'node-9', 'agent/agent-1/diff')
    })

    it('on success: falls back to the current agent node when node_id is missing', async () => {
      const { api, fetchWithAuth, buildNodeHttpUrl, getCurrentAgentNodeId } = makeHarness()
      getCurrentAgentNodeId.mockReturnValue('cur-node')
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ files: [] })
      })
      await api.viewDiff({ agent_id: 'agent-1' })
      expect(buildNodeHttpUrl).toHaveBeenCalledWith('127.0.0.1', '8000', 'cur-node', 'agent/agent-1/diff')
    })

    it('on success: keeps an empty array when the backend returns no files', async () => {
      const { api, fetchWithAuth } = makeHarness()
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ files: [] })
      })
      await api.viewDiff({ agent_id: 'agent-1' })
      expect(api.diffFiles.value).toEqual([])
      expect(api.diffError.value).toBe('')
    })

    it('non-2xx HTTP: sets the error message', async () => {
      const { api, fetchWithAuth } = makeHarness()
      fetchWithAuth.mockResolvedValue({ ok: false, status: 500 })
      await api.viewDiff({ agent_id: 'agent-1' })
      expect(api.diffError.value).toBe('Failed to fetch diff')
      expect(api.diffFiles.value).toEqual([])
      expect(api.diffLoading.value).toBe(false)
    })

    it('request error: sets an error message with details', async () => {
      const { api, fetchWithAuth } = makeHarness()
      fetchWithAuth.mockRejectedValue(new Error('network down'))
      await api.viewDiff({ agent_id: 'agent-1' })
      expect(api.diffError.value).toContain('Failed to fetch diff')
      expect(api.diffError.value).toContain('network down')
      expect(api.diffLoading.value).toBe(false)
    })

    it('filters invalid file data (missing rows / invalid row types)', async () => {
      const { api, fetchWithAuth } = makeHarness()
      const validFile = makeFile('ok.py', 1, 0, [{ type: 'insert', content: 'x' }])
      const badRows = makeFile('bad.py', 1, 0, [{ type: 'weird' }])
      const noRows = makeFile('norows.py', 1, 0, null)
      const notObject = 'not-an-object'
      fetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => ({ files: [validFile, badRows, noRows, notObject] })
      })
      await api.viewDiff({ agent_id: 'agent-1' })
      expect(api.diffFiles.value).toEqual([validFile])
    })
  })
})
