// useTopology unit tests
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useTopology } from './useTopology.js'

// Build a DI harness for useTopology
function makeHarness({ extSessions = [], daemonSessions = [] } = {}) {
  const fetchBrowserExtensionSessions = vi.fn(async () => extSessions)
  const fetchDaemonSessions = vi.fn(async () => daemonSessions)
  const api = useTopology({
    fetchBrowserExtensionSessions,
    fetchDaemonSessions,
  })
  return { api, fetchBrowserExtensionSessions, fetchDaemonSessions }
}

describe('useTopology', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('initial state: empty session lists and closed overlay', () => {
    const { api } = makeHarness()
    expect(api.topologyExtensionSessions.value).toEqual([])
    expect(api.topologyDaemonSessions.value).toEqual([])
    expect(api.showTopologyOverlay.value).toBe(false)
  })

  it('refreshTopologyAccessSessions fetches extension and daemon sessions', async () => {
    const { api, fetchBrowserExtensionSessions, fetchDaemonSessions } = makeHarness({
      extSessions: [{ session_id: 'ext-1' }],
      daemonSessions: [{ session_id: 'daemon-1' }],
    })
    await api.refreshTopologyAccessSessions()
    expect(fetchBrowserExtensionSessions).toHaveBeenCalledTimes(1)
    expect(fetchDaemonSessions).toHaveBeenCalledTimes(1)
    expect(api.topologyExtensionSessions.value).toEqual([{ session_id: 'ext-1' }])
    expect(api.topologyDaemonSessions.value).toEqual([{ session_id: 'daemon-1' }])
  })

  it('refreshTopologyAccessSessions falls back to an empty array for non-array results', async () => {
    const { api, fetchBrowserExtensionSessions, fetchDaemonSessions } = makeHarness()
    fetchBrowserExtensionSessions.mockResolvedValue(null)
    fetchDaemonSessions.mockResolvedValue(undefined)
    await api.refreshTopologyAccessSessions()
    expect(api.topologyExtensionSessions.value).toEqual([])
    expect(api.topologyDaemonSessions.value).toEqual([])
  })

  it('startTopologyAccessPolling refreshes immediately and starts 5s polling', async () => {
    const { api, fetchBrowserExtensionSessions } = makeHarness({ extSessions: [{ session_id: 'e1' }] })
    api.startTopologyAccessPolling()
    // Refresh immediately
    await Promise.resolve()
    await Promise.resolve()
    expect(fetchBrowserExtensionSessions).toHaveBeenCalledTimes(1)
    // Refresh again after 5 seconds
    vi.advanceTimersByTime(5000)
    await Promise.resolve()
    await Promise.resolve()
    expect(fetchBrowserExtensionSessions).toHaveBeenCalledTimes(2)
  })

  it('startTopologyAccessPolling does not start twice when called repeatedly', async () => {
    const { api, fetchBrowserExtensionSessions } = makeHarness()
    api.startTopologyAccessPolling()
    api.startTopologyAccessPolling()
    await Promise.resolve()
    await Promise.resolve()
    expect(fetchBrowserExtensionSessions).toHaveBeenCalledTimes(1)
  })

  it('stopTopologyAccessPolling stops polling', async () => {
    const { api, fetchBrowserExtensionSessions } = makeHarness()
    api.startTopologyAccessPolling()
    api.stopTopologyAccessPolling()
    const callsBefore = fetchBrowserExtensionSessions.mock.calls.length
    vi.advanceTimersByTime(15000)
    expect(fetchBrowserExtensionSessions.mock.calls.length).toBe(callsBefore)
  })

  it('openTopologyOverlay opens the overlay and starts polling', async () => {
    const { api, fetchBrowserExtensionSessions } = makeHarness()
    api.openTopologyOverlay()
    expect(api.showTopologyOverlay.value).toBe(true)
    await Promise.resolve()
    await Promise.resolve()
    expect(fetchBrowserExtensionSessions).toHaveBeenCalled()
  })

  it('closeTopologyOverlay closes the overlay and stops polling', async () => {
    const { api, fetchBrowserExtensionSessions } = makeHarness()
    api.openTopologyOverlay()
    api.closeTopologyOverlay()
    expect(api.showTopologyOverlay.value).toBe(false)
    const callsBefore = fetchBrowserExtensionSessions.mock.calls.length
    vi.advanceTimersByTime(15000)
    expect(fetchBrowserExtensionSessions.mock.calls.length).toBe(callsBefore)
  })
})
