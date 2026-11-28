import { ref } from 'vue'

// Local daemon login-state sync composable.
//
// Extracted from App.vue's <script setup> while preserving identical behavior:
// - when the frontend token changes, automatically push the "remote gateway URL + token" to the local
//   haijunbot-daemon so it learns the login state without manual configuration (multiple gateways coexist, no overwrites).
// - daemon online probe: probes the local loopback /api/status, used to hide the lobby's "install local backend service"
//   onboarding entry.
// - daemon port setting: after writing localStorage, immediately re-pushes the login state with the new URL.
//
// Dependency injection:
// - auth: ref({ password, token, userInfo })
// - terminalName: ref(string) (terminal name, pushed along with /api/auth)
// - autoInstallBrowserExt: ref(boolean) (auto install/update browser extension toggle, pushed with the login state)
// - getGateway: function (returns the current gateway's HTTP base URL, injected by the caller;
//   actually sourced from window.__haijunbotAuthBridge.getGateway(), injected here to avoid a circular dependency)
export function useDaemonSync({ auth, terminalName, autoInstallBrowserExt, getGateway }) {
  // Note: gateway is the remote gateway URL, while the daemon URL is the local loopback; the two must be kept separate.
  const DAEMON_DEFAULT_URL = 'http://127.0.0.1:17800'
  const DAEMON_URL_STORAGE_KEY = 'haijunbot_daemon_url'
  const DAEMON_DEFAULT_PORT = '17800'

  // Normalize the daemon URL: strip whitespace, add an http:// prefix, remove trailing slashes.
  // Empty string returns empty (the caller decides whether to fall back to the default), letting the settings page distinguish "not configured".
  function normalizeDaemonUrl(value) {
    let url = String(value || '').trim()
    if (!url) return ''
    if (!/^https?:\/\//i.test(url)) url = 'http://' + url
    return url.replace(/\/+$/, '')
  }

  // Extract the port from the saved daemon URL (the settings page only exposes the port; the IP is always loopback 127.0.0.1).
  function extractDaemonPort(url) {
    const normalized = normalizeDaemonUrl(url)
    if (!normalized) return ''
    try {
      return new URL(normalized).port || ''
    } catch {
      return ''
    }
  }

  // Resolve the local daemon URL: default loopback 17800, overridable via localStorage (the settings page can change the port when it is occupied)
  function getDaemonUrl() {
    let url
    try {
      url = localStorage.getItem(DAEMON_URL_STORAGE_KEY) || ''
    } catch {
      url = ''
    }
    return normalizeDaemonUrl(url) || DAEMON_DEFAULT_URL
  }

  // Port shown on the settings page (default port when unconfigured, so the user can tweak it)
  function loadDaemonPort() {
    let url
    try {
      url = localStorage.getItem(DAEMON_URL_STORAGE_KEY) || ''
    } catch {
      url = ''
    }
    return extractDaemonPort(url) || DAEMON_DEFAULT_PORT
  }

  const daemonPort = ref(loadDaemonPort())
  // Save the daemon port: only accepts a port number (IP is always local loopback 127.0.0.1).
  // After writing localStorage, immediately re-push the login state with the new URL, so a changed
  // port takes effect for subsequent requests without a page refresh.
  function saveDaemonPortSetting(nextValue = daemonPort.value) {
    const port = String(nextValue || '').trim()
    // Empty or default port clears the override and returns to the default URL
    if (!port || port === DAEMON_DEFAULT_PORT) {
      daemonPort.value = DAEMON_DEFAULT_PORT
      try {
        localStorage.removeItem(DAEMON_URL_STORAGE_KEY)
      } catch (error) {
        console.warn('[DAEMON] Failed to clear daemon port:', error)
      }
    } else {
      daemonPort.value = port
      try {
        localStorage.setItem(DAEMON_URL_STORAGE_KEY, `http://127.0.0.1:${port}`)
      } catch (error) {
        console.warn('[DAEMON] Failed to save daemon port:', error)
      }
    }
    // Re-push the login state to the local daemon immediately after the port changes (same approach as the terminal name / extension toggle)
    syncTokenToDaemon(auth.value.token, getGateway())
  }

  // Whether the local daemon is installed and running: probe local loopback /api/status (daemon listens on 127.0.0.1, CORS fully open, no auth needed).
  // Probe locally rather than the gateway /api/daemon/sessions: the latter is a global session list that would mix in other devices when several are online.
  // A successful probe means "local daemon installed"; the frontend then hides the lobby install entry (same as the browser extension hide logic).
  const localDaemonOnline = ref(false)
  let localDaemonProbeTimer = null
  async function probeLocalDaemon() {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 1500)
    try {
      const resp = await fetch(`${getDaemonUrl()}/api/status`, {
        signal: controller.signal,
        credentials: 'omit',
      })
      if (!resp.ok) {
        localDaemonOnline.value = false
        return
      }
      const data = await resp.json()
      localDaemonOnline.value = !!data?.success
    } catch {
      // daemon not installed/not started is expected; silently treat as offline
      localDaemonOnline.value = false
    } finally {
      clearTimeout(timer)
    }
  }
  function startLocalDaemonProbe() {
    if (localDaemonProbeTimer) return
    probeLocalDaemon()
    localDaemonProbeTimer = setInterval(probeLocalDaemon, 10000)
  }
  function stopLocalDaemonProbe() {
    if (localDaemonProbeTimer) {
      clearInterval(localDaemonProbeTimer)
      localDaemonProbeTimer = null
    }
  }

  // Sync the current login state to the local daemon.
  // token non-empty → POST /api/auth {gateway, token, name}; token empty → POST /api/logout {gateway}.
  // name is the "terminal name"; the daemon sends it when logging into the gateway (hello frame) so the gateway can distinguish terminals.
  // Fully fire-and-forget: no await, no throw, no toast, no blocking of the main flow; silent when the daemon is absent.
  function syncTokenToDaemon(token, gateway) {
    try {
      if (!gateway) return
      const daemonUrl = getDaemonUrl()
      const isLogout = !token
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 1500)
      fetch(`${daemonUrl}${isLogout ? '/api/logout' : '/api/auth'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          isLogout
            ? { gateway }
            : {
                gateway,
                token,
                name: terminalName.value || '',
                // Push the "auto install/update browser extension" toggle together with the login state; the daemon
                // uses it to decide whether to auto-sync when the gateway extension version changes (kept in memory only).
                auto_install_browser_ext: autoInstallBrowserExt.value,
              },
        ),
        signal: controller.signal,
        credentials: 'omit',
      })
        .then(() => {})
        .catch((e) => {
          // daemon absent (connection refused) or timeout is expected; keep only a debug-level log, no noise
          console.debug('[AUTH] sync token to daemon skipped:', e?.message || e)
        })
        .finally(() => clearTimeout(timer))
    } catch (e) {
      console.debug('[AUTH] sync token to daemon failed:', e?.message || e)
    }
  }

  return {
    daemonPort,
    localDaemonOnline,
    normalizeDaemonUrl,
    extractDaemonPort,
    getDaemonUrl,
    loadDaemonPort,
    saveDaemonPortSetting,
    probeLocalDaemon,
    startLocalDaemonProbe,
    stopLocalDaemonProbe,
    syncTokenToDaemon,
  }
}
