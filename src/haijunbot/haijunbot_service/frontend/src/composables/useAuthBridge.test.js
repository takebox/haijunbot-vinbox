// useAuthBridge unit tests
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { useAuthBridge } from './useAuthBridge.js'

function parseGatewayAddress(address) {
  address = String(address || '').trim()
  if (!address) return null
  try {
    const url = new URL(address)
    return {
      protocol: url.protocol.replace(':', ''),
      host: url.hostname,
      port: url.port || (url.protocol === 'https:' || url.protocol === 'wss:' ? '443' : '80'),
      path: url.pathname,
    }
  } catch {
    return null
  }
}

function makeHarness() {
  const auth = ref({ token: 'token-abc', password: '', userInfo: null })
  const terminalName = ref('my-terminal')
  const gatewayUrl = ref('ws://127.0.0.1:8000')
  const syncTokenToDaemon = vi.fn()
  const api = useAuthBridge({ auth, terminalName, gatewayUrl: () => gatewayUrl, parseGatewayAddress, syncTokenToDaemon })
  api.installAuthBridge()
  return { api, auth, terminalName, gatewayUrl, syncTokenToDaemon }
}

describe('useAuthBridge', () => {
  beforeEach(() => {
    localStorage.clear()
    delete window.__haijunbotAuthBridge
  })

  it('installAuthBridge mounts window.__haijunbotAuthBridge', () => {
    makeHarness()
    expect(window.__haijunbotAuthBridge).toBeDefined()
    expect(typeof window.__haijunbotAuthBridge.getToken).toBe('function')
    expect(typeof window.__haijunbotAuthBridge.getName).toBe('function')
    expect(typeof window.__haijunbotAuthBridge.getGateway).toBe('function')
    expect(typeof window.__haijunbotAuthBridge.syncToDaemon).toBe('function')
  })

  it('getToken prefers the in-memory token', () => {
    const { auth } = makeHarness()
    auth.value.token = 'mem-token'
    expect(window.__haijunbotAuthBridge.getToken()).toBe('mem-token')
  })

  it('getToken falls back to localStorage when the in-memory token is empty', () => {
    const { auth } = makeHarness()
    auth.value.token = ''
    localStorage.setItem('haijunbot_auth_token', 'saved-token')
    expect(window.__haijunbotAuthBridge.getToken()).toBe('saved-token')
  })

  it('getToken returns null when both sources are empty', () => {
    const { auth } = makeHarness()
    auth.value.token = ''
    expect(window.__haijunbotAuthBridge.getToken()).toBeNull()
  })

  it('getName returns the terminal name', () => {
    makeHarness()
    expect(window.__haijunbotAuthBridge.getName()).toBe('my-terminal')
  })

  it('getGateway converts ws to an http base address', () => {
    makeHarness()
    expect(window.__haijunbotAuthBridge.getGateway()).toBe('http://127.0.0.1:8000')
  })

  it('getGateway converts wss to an https base address', () => {
    const { gatewayUrl } = makeHarness()
    gatewayUrl.value = 'wss://example.com:443'
    expect(window.__haijunbotAuthBridge.getGateway()).toBe('https://example.com:443')
  })

  it('getGateway returns null for an invalid address', () => {
    const { gatewayUrl } = makeHarness()
    gatewayUrl.value = 'not a url'
    expect(window.__haijunbotAuthBridge.getGateway()).toBeNull()
  })

  it('syncToDaemon calls the injected syncTokenToDaemon', () => {
    const { syncTokenToDaemon, auth } = makeHarness()
    window.__haijunbotAuthBridge.syncToDaemon()
    expect(syncTokenToDaemon).toHaveBeenCalledWith(
      auth.value.token,
      window.__haijunbotAuthBridge.getGateway()
    )
  })
})
