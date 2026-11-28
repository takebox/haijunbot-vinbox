// Browser extension login-state bridge composable.
//
// Extracted from App.vue's <script setup> while preserving identical behavior:
// Lets the HaijunBot browser extension read the current login state, avoiding repeated logins or manual Token entry.
// The extension calls window.__haijunbotAuthBridge.getToken() via a main-world script to obtain the Token,
// and uses getGateway() to get the currently configured gateway URL (the gateway and frontend may be on
// different domains), so the extension can associate the Token with the correct gateway.
//
// Dependency injection:
// - auth: ref({ password, token, userInfo })
// - terminalName: ref(string) (terminal name, reported to the gateway by the extension via hello)
// - gatewayUrl: ref(string) (currently configured gateway URL, ws(s)://host:port)
//   Note: gatewayUrl is defined by useGatewayConnection; this composable is called before it,
//   so it is injected as a getter (re-evaluated internally via gatewayUrlGetter()) to avoid TDZ.
// - parseGatewayAddress: function (parses a gateway URL into { protocol, host, port })
// - syncTokenToDaemon: function (token, gateway) -> manually triggers one daemon sync
export function useAuthBridge({ auth, terminalName, gatewayUrl: gatewayUrlGetter, parseGatewayAddress, syncTokenToDaemon }) {
  const gatewayUrl = () => gatewayUrlGetter()
  function installAuthBridge() {
    window.__haijunbotAuthBridge = {
      // Prefer the in-memory Token; when empty, fall back to localStorage (haijunbot_auth_token is persisted
      // in the no-login scenario), letting the extension recover via the page when the persisted Token goes
      // stale. Note: this page only serves the single configured gateway (see getGateway); the localStorage
      // Token belongs to that gateway and the extension matches it per getGateway(), naturally multi-gateway.
      getToken: () => auth.value.token || localStorage.getItem('haijunbot_auth_token') || null,
      // Terminal name: reported to the gateway by the extension via hello, so the gateway can distinguish terminals.
      getName: () => terminalName.value || null,
      getGateway: () => {
        const parsed = parseGatewayAddress(gatewayUrl().value)
        if (!parsed) return null
        // The gateway URL may be configured with ws(s):// (the frontend uses it for WebSocket), but here it
        // is handed to the daemon as an "HTTP base URL", so the transport security must be preserved:
        // wss→https, ws→http. Downgrading everything to http would make the daemon connect with plaintext ws
        // to an HTTPS port, which nginx rejects with 400, surfacing as websocket: bad handshake.
        const schemeMap = { ws: 'http', wss: 'https', http: 'http', https: 'https' }
        const scheme = schemeMap[parsed.protocol] || parsed.protocol || 'http'
        const host = parsed.host || window.location.hostname || '127.0.0.1'
        const port = parsed.port || '8000'
        return `${scheme}://${host}:${port}`
      },
      // Manually trigger one daemon sync for real-browser verification / debugging
      syncToDaemon: () => syncTokenToDaemon(auth.value.token, window.__haijunbotAuthBridge.getGateway()),
    }
  }

  return {
    installAuthBridge,
  }
}
