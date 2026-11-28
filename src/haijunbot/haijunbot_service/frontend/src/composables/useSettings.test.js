// useSettings unit tests
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import { useSettings } from './useSettings.js'

// Flush all microtasks (for async functions with multiple awaits)
async function flushPromises() {
  for (let i = 0; i < 20; i++) {
    await Promise.resolve()
  }
}

// Build a useSettings dependency-injection harness
function makeHarness(overrides = {}) {
  const showToast = vi.fn()
  const showConfirm = vi.fn()
  const showAdminPanel = ref(false)
  const adminPanelRef = ref(null)
  const pushOverlayState = vi.fn()
  const getGatewayAddress = vi.fn(() => ({ host: '127.0.0.1', port: 8080 }))
  const getHttpProtocol = vi.fn(() => 'http')
  const fetchWithAuth = vi.fn()
  const buildNodeHttpUrl = vi.fn((host, port, nodeId, path) => `http://${host}:${port}/api/nodes/${nodeId}/${path}`)
  const availableNodeOptions = ref([])
  const isRestartingGateway = ref(false)
  const restartFrontendService = ref(false)

  const api = useSettings({
    showAdminPanel,
    adminPanelRef,
    pushOverlayState: () => pushOverlayState,
    getGatewayAddress,
    getHttpProtocol,
    fetchWithAuth,
    buildNodeHttpUrl,
    showToast,
    showConfirm,
    availableNodeOptions,
    isRestartingGateway: () => isRestartingGateway,
    restartFrontendService: () => restartFrontendService,
    ...overrides,
  })
  return {
    api,
    showToast,
    showConfirm,
    showAdminPanel,
    adminPanelRef,
    pushOverlayState,
    getGatewayAddress,
    getHttpProtocol,
    fetchWithAuth,
    buildNodeHttpUrl,
    availableNodeOptions,
    isRestartingGateway,
    restartFrontendService,
  }
}

describe('useSettings', () => {
  beforeEach(() => {
    localStorage.clear()
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('initial state: notification toggles read localStorage, sync/update states default', () => {
    localStorage.setItem('haijunbot_notify_on_exit', 'true')
    localStorage.setItem('haijunbot_notify_on_input', 'false')
    const { api } = makeHarness()
    expect(api.notifyOnExit.value).toBe(true)
    expect(api.notifyOnInput.value).toBe(false)
    expect(api.syncConfigSourceNode.value).toBe('')
    expect(api.syncConfigTargetNodes.value).toEqual([])
    expect(api.syncConfigSections.value).toEqual(['llms', 'llm_groups'])
    expect(api.isSyncingConfig.value).toBe(false)
    expect(api.isUpdatingCode.value).toBe(false)
  })

  it('saveNotifySettings writes to localStorage', () => {
    const { api } = makeHarness()
    api.notifyOnExit.value = true
    api.notifyOnInput.value = true
    api.saveNotifySettings()
    expect(localStorage.getItem('haijunbot_notify_on_exit')).toBe('true')
    expect(localStorage.getItem('haijunbot_notify_on_input')).toBe('true')
  })

  it('handleSyncConfig sets the source node, shows a confirmation, then calls syncConfig', async () => {
    const { api, showConfirm, fetchWithAuth, availableNodeOptions } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'node-1' }, { node_id: 'master' }]
    // syncConfig depends on: GET source config + POST target config
    fetchWithAuth.mockImplementation(async (url, options) => {
      if (options.method === 'GET') {
        return { ok: true, json: async () => ({ success: true, data: { config: { llms: [{ id: 'llm-1' }] } } }) }
      }
      return { ok: true, json: async () => ({ success: true, data: {} }) }
    })
    api.handleSyncConfig({ sourceNodeId: 'node-1' })
    expect(api.syncConfigSourceNode.value).toBe('node-1')
    expect(showConfirm).toHaveBeenCalledTimes(1)
    // Run the confirm callback (internally calls async syncConfig; wait for microtasks)
    const confirmCallback = showConfirm.mock.calls[0][1]
    confirmCallback()
    await flushPromises()
    expect(api.isSyncingConfig.value).toBe(false)
    expect(fetchWithAuth).toHaveBeenCalled()
  })

  it('handleSyncConfig falls back to an empty string when sourceNodeId is missing', () => {
    const { api, showConfirm } = makeHarness()
    api.handleSyncConfig({ sourceNodeId: '' })
    expect(api.syncConfigSourceNode.value).toBe('')
    expect(showConfirm).toHaveBeenCalledTimes(1)
  })

  it('openAdminSystemAction opens the admin panel, pushes overlay state, and scrolls to system config', async () => {
    const { api, showAdminPanel, pushOverlayState, adminPanelRef } = makeHarness()
    const openSystemAction = vi.fn()
    adminPanelRef.value = { openSystemAction }
    api.openAdminSystemAction('restart')
    expect(showAdminPanel.value).toBe(true)
    expect(pushOverlayState).toHaveBeenCalledTimes(1)
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(openSystemAction).toHaveBeenCalledWith('restart')
  })

  it('openAdminSystemAction safely skips when adminPanelRef is empty', async () => {
    const { api, showAdminPanel } = makeHarness()
    api.openAdminSystemAction('restart')
    expect(showAdminPanel.value).toBe(true)
    await new Promise(resolve => setTimeout(resolve, 0))
  })

  it('confirmUpdateCodeToMain shows a confirmation, then calls updateCodeToMain', async () => {
    const { api, showConfirm, fetchWithAuth, availableNodeOptions } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'master' }]
    fetchWithAuth.mockResolvedValue({ ok: true, json: async () => ({ success: true, data: { message: 'ok' } }) })
    api.confirmUpdateCodeToMain()
    expect(showConfirm).toHaveBeenCalledTimes(1)
    const confirmCallback = showConfirm.mock.calls[0][1]
    confirmCallback()
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    expect(api.isUpdatingCode.value).toBe(false)
    expect(fetchWithAuth).toHaveBeenCalled()
  })

  it('confirmRestartAllNodes shows a confirmation, then calls restartAllNodes', async () => {
    vi.useFakeTimers()
    const { api, showConfirm, fetchWithAuth, availableNodeOptions, isRestartingGateway } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'node-1' }, { node_id: 'master' }]
    fetchWithAuth.mockResolvedValue({ ok: true, json: async () => ({ success: true }) })
    api.confirmRestartAllNodes()
    expect(showConfirm).toHaveBeenCalledTimes(1)
    const confirmCallback = showConfirm.mock.calls[0][1]
    confirmCallback()
    // restartAllNodes internally uses a 1s per-node interval plus a 3s reset timer; advance timers and flush microtasks
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()
    expect(isRestartingGateway.value).toBe(false)
    expect(fetchWithAuth).toHaveBeenCalled()
  })

  it('restartAllNodes restarts child nodes then master, 1 second apart', async () => {
    vi.useFakeTimers()
    const { api, fetchWithAuth, availableNodeOptions, isRestartingGateway, showToast } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'node-1' }, { node_id: 'node-2' }, { node_id: 'master' }]
    fetchWithAuth.mockResolvedValue({ ok: true, json: async () => ({ success: true }) })
    const promise = api.restartAllNodes()
    // Child node node-1 restarts (call 1)
    await flushPromises()
    expect(fetchWithAuth).toHaveBeenCalledTimes(1)
    // After node-1 waits 1s, node-2 restarts (call 2)
    await vi.advanceTimersByTimeAsync(1000)
    expect(fetchWithAuth).toHaveBeenCalledTimes(2)
    // After node-2 waits 1s, master restarts (call 3; master does not wait)
    await vi.advanceTimersByTimeAsync(1000)
    expect(fetchWithAuth).toHaveBeenCalledTimes(3)
    // The finally block resets isRestartingGateway after 3000ms
    await vi.advanceTimersByTimeAsync(3000)
    await promise
    expect(isRestartingGateway.value).toBe(false)
    expect(showToast).toHaveBeenCalledWith('Restart commands sent to all nodes', 'success')
  })

  it('restartAllNodes continues and warns when a child node restart fails', async () => {
    vi.useFakeTimers()
    const { api, fetchWithAuth, availableNodeOptions, showToast } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'node-1' }, { node_id: 'master' }]
    fetchWithAuth.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) })
    const promise = api.restartAllNodes()
    await flushPromises()
    expect(showToast).toHaveBeenCalledWith('Node "node-1" restart failed: HTTP 500', 'error')
    // After node-1 waits 1s, master restarts
    await vi.advanceTimersByTimeAsync(1000)
    expect(fetchWithAuth).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(3000)
    await promise
  })

  it('syncConfig warns when there are no target nodes', async () => {
    const { api, availableNodeOptions, showToast } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'master' }]
    await api.syncConfig()
    expect(showToast).toHaveBeenCalledWith('No other nodes to sync to', 'warning')
  })

  it('syncConfig syncs successfully to all target nodes', async () => {
    const { api, fetchWithAuth, availableNodeOptions, showToast } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'node-1' }, { node_id: 'node-2' }, { node_id: 'master' }]
    fetchWithAuth.mockImplementation(async (url, options) => {
      if (options.method === 'GET') {
        return { ok: true, json: async () => ({ success: true, data: { config: { llms: [{ id: 'llm-1' }], llm_groups: [] } } }) }
      }
      return { ok: true, json: async () => ({ success: true, data: {} }) }
    })
    await api.syncConfig()
    expect(showToast).toHaveBeenCalledWith('Config sync succeeded, applied to 2 nodes', 'success')
    expect(api.isSyncingConfig.value).toBe(false)
  })

  it('syncConfig warns when the source config is empty', async () => {
    const { api, fetchWithAuth, availableNodeOptions, showToast } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'node-1' }, { node_id: 'master' }]
    fetchWithAuth.mockResolvedValue({ ok: true, json: async () => ({ success: true, data: { config: {} } }) })
    await api.syncConfig()
    expect(showToast).toHaveBeenCalledWith('No config data to sync', 'warning')
  })

  it('syncConfig guards against re-entry: returns early when isSyncingConfig is true', async () => {
    const { api, fetchWithAuth } = makeHarness()
    api.isSyncingConfig.value = true
    await api.syncConfig()
    expect(fetchWithAuth).not.toHaveBeenCalled()
  })

  it('updateCodeToMain warns when there are no online nodes', async () => {
    const { api, availableNodeOptions, showToast } = makeHarness()
    availableNodeOptions.value = []
    await api.updateCodeToMain()
    expect(showToast).toHaveBeenCalledWith('No online nodes to update', 'warning')
  })

  it('updateCodeToMain updates all nodes successfully', async () => {
    const { api, fetchWithAuth, availableNodeOptions, showToast } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'node-1' }, { node_id: 'node-2' }]
    fetchWithAuth.mockResolvedValue({ ok: true, json: async () => ({ success: true, data: { message: 'ok' } }) })
    await api.updateCodeToMain()
    expect(showToast).toHaveBeenCalledWith('Code update succeeded, updated 2/2 nodes', 'success')
    expect(api.isUpdatingCode.value).toBe(false)
  })

  it('updateCodeToMain reports partial success when some nodes fail', async () => {
    const { api, fetchWithAuth, availableNodeOptions, showToast } = makeHarness()
    availableNodeOptions.value = [{ node_id: 'node-1' }, { node_id: 'node-2' }]
    fetchWithAuth
      .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: { message: 'ok' } }) })
      .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({ error: { message: 'Failed' } }) })
    await api.updateCodeToMain()
    expect(showToast).toHaveBeenCalledWith('Code update partially succeeded, 1/2 nodes', 'warning')
  })

  it('updateCodeToMain guards against re-entry: returns early when isUpdatingCode is true', async () => {
    const { api, fetchWithAuth } = makeHarness()
    api.isUpdatingCode.value = true
    await api.updateCodeToMain()
    expect(fetchWithAuth).not.toHaveBeenCalled()
  })
})
