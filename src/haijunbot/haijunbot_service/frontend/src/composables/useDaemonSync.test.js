// useDaemonSync unit tests
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import { useDaemonSync } from './useDaemonSync.js'

function makeHarness() {
  const auth = ref({ token: 'token-123', password: '', userInfo: null })
  const terminalName = ref('test-terminal')
  const autoInstallBrowserExt = ref(true)
  const getGateway = vi.fn(() => 'http://127.0.0.1:8000')
  const api = useDaemonSync({ auth, terminalName, autoInstallBrowserExt, getGateway })
  return { api, auth, terminalName, autoInstallBrowserExt, getGateway }
}

describe('useDaemonSync', () => {
  beforeEach(() => {
    localStorage.clear()
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('exposes the expected API', () => {
    const { api } = makeHarness()
    expect(typeof api.syncTokenToDaemon).toBe('function')
    expect(typeof api.saveDaemonPortSetting).toBe('function')
    expect(typeof api.getDaemonUrl).toBe('function')
    expect(typeof api.startLocalDaemonProbe).toBe('function')
    expect(typeof api.stopLocalDaemonProbe).toBe('function')
    expect(api.daemonPort.value).toBe('17800')
    expect(api.localDaemonOnline.value).toBe(false)
  })

  it('getDaemonUrl defaults to loopback 17800', () => {
    const { api } = makeHarness()
    expect(api.getDaemonUrl()).toBe('http://127.0.0.1:17800')
  })

  it('getDaemonUrl reads a port override from localStorage', () => {
    const { api } = makeHarness()
    localStorage.setItem('haijunbot_daemon_url', 'http://127.0.0.1:18000')
    expect(api.getDaemonUrl()).toBe('http://127.0.0.1:18000')
  })

  it('syncTokenToDaemon POSTs /api/auth when a token exists', () => {
    const { api } = makeHarness()
    const fetchMock = vi.fn(() => Promise.resolve())
    globalThis.fetch = fetchMock
    api.syncTokenToDaemon('token-123', 'http://127.0.0.1:8000')
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:17800/api/auth',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          gateway: 'http://127.0.0.1:8000',
          token: 'token-123',
          name: 'test-terminal',
          auto_install_browser_ext: true,
        }),
      })
    )
  })

  it('syncTokenToDaemon POSTs /api/logout when the token is empty', () => {
    const { api } = makeHarness()
    const fetchMock = vi.fn(() => Promise.resolve())
    globalThis.fetch = fetchMock
    api.syncTokenToDaemon('', 'http://127.0.0.1:8000')
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:17800/api/logout',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ gateway: 'http://127.0.0.1:8000' }),
      })
    )
  })

  it('syncTokenToDaemon returns silently without requesting when gateway is missing', () => {
    const { api } = makeHarness()
    const fetchMock = vi.fn()
    globalThis.fetch = fetchMock
    api.syncTokenToDaemon('token', null)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('saveDaemonPortSetting clears the override for the default port', () => {
    const { api } = makeHarness()
    localStorage.setItem('haijunbot_daemon_url', 'http://127.0.0.1:18000')
    api.saveDaemonPortSetting('17800')
    expect(api.daemonPort.value).toBe('17800')
    expect(localStorage.getItem('haijunbot_daemon_url')).toBeNull()
  })

  it('saveDaemonPortSetting writes a custom port to localStorage and re-syncs', () => {
    const { api } = makeHarness()
    const fetchMock = vi.fn(() => Promise.resolve())
    globalThis.fetch = fetchMock
    api.saveDaemonPortSetting('19000')
    expect(api.daemonPort.value).toBe('19000')
    expect(localStorage.getItem('haijunbot_daemon_url')).toBe('http://127.0.0.1:19000')
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:19000/api/auth',
      expect.anything()
    )
  })

  it('probeLocalDaemon sets online on success', async () => {
    const { api } = makeHarness()
    globalThis.fetch = vi.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    }))
    await api.probeLocalDaemon()
    expect(api.localDaemonOnline.value).toBe(true)
  })

  it('probeLocalDaemon sets offline on failure', async () => {
    const { api } = makeHarness()
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('ECONNREFUSED')))
    await api.probeLocalDaemon()
    expect(api.localDaemonOnline.value).toBe(false)
  })
})
