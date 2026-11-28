// WebSocket connection management: connects to gateway, heartbeat, exponential backoff reconnection.
//
// Connection URL: {gateway}/api/browser-ext/ws
// Auth: subprotocol ['haijunbot-ext', 'haijunbot-token.<urlencoded-token>']

const HEARTBEAT_INTERVAL_MS = 20000; // Send a ping every 20s
const RECONNECT_BASE_MS = 1000; // First reconnect after 1s
const RECONNECT_MAX_MS = 30000; // Cap at 30s

// Close code used when gateway authentication fails (see the extension WS endpoint in haijunbot_web_gateway/app.py).
// Receiving this close code means the current Token is invalid (e.g., the gateway restarted and the JWT signing key changed,
// or the Token expired). Reconnecting with the same Token will only result in infinite failures; the upper layer must
// clear the Token cache and obtain a new one.
const CLOSE_AUTH_FAILED = 4401;
const CLOSE_FORBIDDEN = 4403;

export class WsClient {
  /**
   * @param {object} opts
   * @param {(msg: object) => void} opts.onMessage Message received callback
   * @param {(state: string) => void} opts.onStateChange Connection state change callback
   */
  constructor({ onMessage, onStateChange, onAuthError }) {
    this.onMessage = onMessage;
    this.onStateChange = onStateChange;
    this.onAuthError = onAuthError;
    this.ws = null;
    this.state = "disconnected"; // disconnected | connecting | connected
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.manualClose = false;
  }

  setState(state) {
    if (this.state === state) return;
    this.state = state;
    try {
      this.onStateChange?.(state);
    } catch (e) {
      console.warn("[HaijunBot] onStateChange error", e);
    }
  }

  /**
   * Establish a connection.
   * @param {string} gateway Gateway address, e.g. https://hjb-ai.cn or http://127.0.0.1:8000
   * @param {string} token Gateway token
   */
  connect(gateway, token) {
    this.manualClose = false;
    this.gateway = normalizeGateway(gateway);
    this.token = token;
    this._open();
  }

  _open() {
    if (!this.gateway) {
      console.warn("[HaijunBot] gateway not configured");
      return;
    }
    this._clearReconnect();
    this.setState("connecting");

    const wsUrl = toWsUrl(this.gateway) + "/api/browser-ext/ws";
    const protocols = ["haijunbot-ext"];
    if (this.token) {
      protocols.push("haijunbot-token." + encodeURIComponent(this.token));
    }

    let ws;
    try {
      ws = new WebSocket(wsUrl, protocols);
    } catch (e) {
      console.error("[HaijunBot] WebSocket construct failed", e);
      this._scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      console.log("[HaijunBot] ws connected");
      this.reconnectAttempts = 0;
      this.setState("connected");
      this._startHeartbeat();
      // The upper layer (service_worker) sends hello after open
      try {
        this.onOpen?.();
      } catch (e) {
        console.warn("[HaijunBot] onOpen error", e);
      }
    };

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (e) {
        console.warn("[HaijunBot] invalid json from gateway", event.data);
        return;
      }
      if (msg && msg.type === "pong") {
        return; // Heartbeat response, no need to report
      }
      try {
        this.onMessage?.(msg);
      } catch (e) {
        console.error("[HaijunBot] onMessage error", e);
      }
    };

    ws.onclose = (event) => {
      console.log("[HaijunBot] ws closed", event.code, event.reason);
      this._stopHeartbeat();
      this.setState("disconnected");
      if (this.manualClose) {
        return;
      }
      // Auth failed: the current Token is invalid; reconnecting with the same Token will inevitably be rejected again.
      // Delegate to the upper layer to clear the Token cache and obtain a new one, avoiding an infinite "disconnect-reconnect" loop.
      if (event.code === CLOSE_AUTH_FAILED || event.code === CLOSE_FORBIDDEN) {
        console.warn(
          "[HaijunBot] ws auth failed, code=",
          event.code,
          "reason=",
          event.reason,
        );
        try {
          this.onAuthError?.(event.code, event.reason);
        } catch (e) {
          console.warn("[HaijunBot] onAuthError error", e);
        }
        return;
      }
      this._scheduleReconnect();
    };

    ws.onerror = (event) => {
      console.warn("[HaijunBot] ws error", event);
      // onclose will fire shortly after; reconnection logic is handled there
    };
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: "ping" }));
        } catch (e) {
          console.warn("[HaijunBot] ping failed", e);
        }
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  _stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  _scheduleReconnect() {
    this._clearReconnect();
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, this.reconnectAttempts),
      RECONNECT_MAX_MS,
    );
    this.reconnectAttempts += 1;
    console.log(
      `[HaijunBot] reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`,
    );
    this.reconnectTimer = setTimeout(() => {
      this._open();
    }, delay);
  }

  _clearReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /** Send a message; returns false when not connected (commands are not cached during disconnection). */
  send(obj) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }
    try {
      this.ws.send(JSON.stringify(obj));
      return true;
    } catch (e) {
      console.warn("[HaijunBot] send failed", e);
      return false;
    }
  }

  /** Manually disconnect (no more auto-reconnect). */
  close() {
    this.manualClose = true;
    this._clearReconnect();
    this._stopHeartbeat();
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {
        // ignore
      }
    }
    this.ws = null;
    this.setState("disconnected");
  }

  get isConnected() {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Whether the connection is still valid (no need to rebuild).
   *
   * Besides OPEN, CONNECTING is also considered valid: an in-progress handshake should not be interrupted by a duplicate connect from the upper layer.
   * Returns false for CLOSING / CLOSED or when manually closed (manualClose),
   * delegating to the upper layer for reconnection or internal backoff reconnect.
   */
  isAlive() {
    if (this.manualClose) return false;
    if (!this.ws) return false;
    return (
      this.ws.readyState === WebSocket.OPEN ||
      this.ws.readyState === WebSocket.CONNECTING
    );
  }
}

/** Normalize gateway address: strip trailing slashes. */
export function normalizeGateway(gateway) {
  if (!gateway) return "";
  let g = String(gateway).trim();
  if (!g) return "";
  if (!/^https?:\/\//i.test(g)) {
    // Prepend https by default
    g = "https://" + g;
  }
  return g.replace(/\/+$/, "");
}

/** http(s) -> ws(s). */
export function toWsUrl(gateway) {
  return gateway.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");
}
