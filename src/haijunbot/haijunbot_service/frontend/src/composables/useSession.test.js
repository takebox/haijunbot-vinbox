// useSession unit tests
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useSession } from './useSession.js'

function makeHarness({ agentId = null } = {}) {
  const currentAgentId = ref(agentId)
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: '8000' }))
  const getCurrentAgentNodeId = vi.fn(() => '')
  const fetchWithAuth = vi.fn()
  const buildNodeHttpUrl = vi.fn((host, port, nodeId, path) => `http://${host}:${port}/api/node/${nodeId}/${path}`)
  const loadHistoryMessages = vi.fn()
  const api = useSession({
    currentAgentId,
    getGatewayAddress,
    getCurrentAgentNodeId,
    fetchWithAuth,
    buildNodeHttpUrl,
    loadHistoryMessages
  })
  return { api, currentAgentId, getGatewayAddress, getCurrentAgentNodeId, fetchWithAuth, buildNodeHttpUrl, loadHistoryMessages }
}

describe('useSession', () => {
  beforeEach(() => {
    // Global alert does not exist in Node; mock it to avoid errors
    globalThis.alert = vi.fn()
  })

  it('exposes the expected API', () => {
    const { api } = makeHarness()
    expect(typeof api.showSessionDialog).toBe('object') // ref
    expect(typeof api.availableSessions).toBe('object') // ref
    expect(typeof api.restoreSession).toBe('function')
    expect(typeof api.cancelSessionDialog).toBe('function')
  })

  it('initial state: dialog hidden and session list empty', () => {
    const { api } = makeHarness()
    expect(api.showSessionDialog.value).toBe(false)
    expect(api.availableSessions.value).toEqual([])
  })

  describe('restoreSession', () => {
    it('does not make a request without a sessionFile', async () => {
      const { api, fetchWithAuth } = makeHarness({ agentId: 'agent-1' })
      await api.restoreSession(null)
      await api.restoreSession('')
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })

    it('does not make a request without a currentAgentId', async () => {
      const { api, fetchWithAuth } = makeHarness({ agentId: null })
      await api.restoreSession('session.json')
      expect(fetchWithAuth).not.toHaveBeenCalled()
    })

    it('on success: closes the dialog and loads history messages', async () => {
      const { api, fetchWithAuth, buildNodeHttpUrl, getGatewayAddress, loadHistoryMessages } = makeHarness({ agentId: 'agent-1' })
      fetchWithAuth.mockResolvedValue({
        json: async () => ({ success: true })
      })
      api.showSessionDialog.value = true
      await api.restoreSession('session.json')
      expect(api.showSessionDialog.value).toBe(false)
      expect(loadHistoryMessages).toHaveBeenCalledWith(false)
      expect(getGatewayAddress).toHaveBeenCalled()
      expect(buildNodeHttpUrl).toHaveBeenCalledWith('127.0.0.1', '8000', 'master', 'agents/agent-1/sessions')
      expect(fetchWithAuth).toHaveBeenCalledTimes(1)
      // The POST body includes session_file and node_id
      const [, options] = fetchWithAuth.mock.calls[0]
      expect(options.method).toBe('POST')
      expect(JSON.parse(options.body)).toEqual({ session_file: 'session.json', node_id: 'master' })
    })

    it('uses the current agent node when node_id is available', async () => {
      const { api, fetchWithAuth, buildNodeHttpUrl, getCurrentAgentNodeId } = makeHarness({ agentId: 'agent-1' })
      getCurrentAgentNodeId.mockReturnValue('node-9')
      fetchWithAuth.mockResolvedValue({
        json: async () => ({ success: true })
      })
      await api.restoreSession('session.json')
      expect(buildNodeHttpUrl).toHaveBeenCalledWith('127.0.0.1', '8000', 'node-9', 'agents/agent-1/sessions')
    })

    it('backend failure: shows an error alert and keeps the dialog open', async () => {
      const { api, fetchWithAuth, loadHistoryMessages } = makeHarness({ agentId: 'agent-1' })
      fetchWithAuth.mockResolvedValue({
        json: async () => ({ success: false, error: 'file not found' })
      })
      api.showSessionDialog.value = true
      await api.restoreSession('session.json')
      expect(api.showSessionDialog.value).toBe(true)
      expect(globalThis.alert).toHaveBeenCalledWith('Failed to restore session: file not found')
      expect(loadHistoryMessages).not.toHaveBeenCalled()
    })

    it('request error: shows an alert with the error details', async () => {
      const { api, fetchWithAuth } = makeHarness({ agentId: 'agent-1' })
      fetchWithAuth.mockRejectedValue(new Error('network down'))
      await api.restoreSession('session.json')
      expect(globalThis.alert).toHaveBeenCalledWith('Failed to restore session: network down')
    })
  })

  describe('cancelSessionDialog', () => {
    it('closes the dialog and loads history messages (without restoring a session)', () => {
      const { api, loadHistoryMessages } = makeHarness()
      api.showSessionDialog.value = true
      api.cancelSessionDialog()
      expect(api.showSessionDialog.value).toBe(false)
      expect(loadHistoryMessages).toHaveBeenCalledWith(false)
    })
  })
})
