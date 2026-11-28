// Background service worker: connection management + command dispatch entry (supports multiple gateways).
//
// Responsibilities:
// 1. Read configured gateway list from chrome.storage, establish independent WebSocket connections for each gateway
// 2. Send hello after connection (extension version, browser info, tab snapshot)
// 3. On receiving command, dispatch to CommandRouter for execution and return result
// 4. Broadcast connection status of each gateway to popup
//
// Token source: read window.__haijunbotAuthBridge exposed by the HaijunBot web page in the page's main world
// via chrome.scripting.executeScript({ world: "MAIN" }) (getToken / getGateway),
// thereby reusing the browser's login session to automatically connect to the gateway without requiring the user to manually fill in a Token.
// Note: cannot use content script to inject inline scripts for main world bridging; this is blocked by page CSP in MV3.
//
// Multi-gateway note: the same browser can connect to multiple HaijunBot gateways simultaneously, each with independent connections, sessions, and Tokens.
// Note: all gateways share the same set of browser tabs (an inherent characteristic of browser extension architecture).

import { WsClient } from "./ws_client.js";
import { CommandRouter } from "./command_router.js";

// Extension version: dynamically read from manifest to avoid version drift with manifest.json
const EXTENSION_VERSION = chrome.runtime.getManifest().version;

const router = new CommandRouter();

// Gateway-indexed state (key is normalized gateway address, e.g. http://127.0.0.1:8000)
const clients = new Map(); // gateway -> WsClient
const tokens = new Map(); // gateway -> token
const sessions = new Map(); // gateway -> session_id
const states = new Map(); // gateway -> 'disconnected' | 'connecting' | 'connected'
// gatewayKey -> consecutive auth failure count, used to avoid futile reconnect cycles (reset on successful connection)
const authErrorAttempts = new Map();

// Maximum auto-retry count after auth failure: stop reconnecting when exceeded, prompt user to re-login
const AUTH_ERROR_MAX_RETRIES = 3;

// Notification ID for extension updates (same ID auto-replaces on repeated creation, avoiding stacking)
const UPDATE_NOTIFICATION_ID = "haijunbot-extension-update";

// Key in chrome.storage.local for recording "already notified new version number".
// Only notify once per version to avoid popping up notifications on every reconnect/wake.
const NOTIFIED_VERSION_KEY = "notified_extension_version";

// Key in chrome.storage.local for caching "terminal name".
// This value is configured by the HaijunBot web settings page; the extension reads and caches it during login state probing,
// for hello to report to the gateway (gateway uses it to distinguish different terminals). Uses cached value when page is not open.
const TERMINAL_NAME_KEY = "terminal_name";

// Key in chrome.storage.local for persisting "per-gateway login Tokens", shaped like { [gatewayKey]: token }.
// Same principle as daemon-side credentials.json: persist Token to disk so that after extension/browser restart, login state is automatically restored
// without needing to re-open the HaijunBot page for probing. Corresponding entries are cleared on auth failure/disconnect/gateway removal.
const TOKENS_KEY = "gateway_tokens";

// Key in chrome.storage.local for storing "gateway allow/block list", shaped like {mode, patterns}.
//
// Why needed: autoDiscoverGateways automatically includes and connects to "gateways already logged in the browser",
// so gateways the user only logged into once will also be connected long-term. The list is used to keep such gateways out.
// mode semantics are consistent with the daemon-side gatewayfilter package:
//   off       no restriction (default)
//   whitelist only allow gateways matching patterns
//   blacklist only block gateways matching patterns
// patterns match against host:port (ignoring protocol differences), supporting * and ? wildcards.
const GATEWAY_FILTER_KEY = "gateway_filter";

/** Read gateway allow/block list configuration (defaults to off + empty list). */
async function loadGatewayFilter() {
  try {
    const cfg = await chrome.storage.local.get([GATEWAY_FILTER_KEY]);
    const raw = cfg[GATEWAY_FILTER_KEY];
    if (!raw || typeof raw !== "object") return { mode: "off", patterns: [] };
    const mode = normalizeFilterMode(raw.mode);
    const patterns = Array.isArray(raw.patterns)
      ? raw.patterns.map((p) => String(p || "").trim()).filter(Boolean)
      : [];
    return { mode, patterns };
  } catch (e) {
    console.warn("[HaijunBot] read gateway filter failed", e);
    return { mode: "off", patterns: [] };
  }
}

/** Save gateway allow/block list configuration. */
async function saveGatewayFilter(mode, patterns) {
  const value = {
    mode: normalizeFilterMode(mode),
    patterns: Array.isArray(patterns)
      ? patterns.map((p) => String(p || "").trim()).filter(Boolean)
      : [],
  };
  await chrome.storage.local.set({ [GATEWAY_FILTER_KEY]: value });
  return value;
}

/** Normalize list mode: invalid values fall back to off (consistent with daemon-side NormalizeMode). */
function normalizeFilterMode(mode) {
  const m = String(mode || "")
    .trim()
    .toLowerCase();
  if (m === "whitelist" || m === "blacklist") return m;
  return "off";
}

/**
 * Wildcard matching: '*' matches any length (including empty), '?' matches exactly one character.
 *
 * Case-insensitive; both pattern and hostPort are trimmed first.
 * Implemented with two pointers + backtracking (worst case O(n*m)), deliberately not using RegExp: to avoid user-input
 * special characters (like '.', '(') being treated as regex metacharacters causing semantic deviation.
 * Behavior is consistent with daemon-side gatewayfilter.Match.
 */
function wildcardMatch(pattern, hostPort) {
  const p = String(pattern || "")
    .trim()
    .toLowerCase();
  const s = String(hostPort || "")
    .trim()
    .toLowerCase();
  let pi = 0;
  let si = 0;
  let star = -1;
  let mark = 0;
  while (si < s.length) {
    if (pi < p.length && (p[pi] === "?" || p[pi] === s[si])) {
      pi++;
      si++;
    } else if (pi < p.length && p[pi] === "*") {
      star = pi;
      mark = si;
      pi++;
    } else if (star !== -1) {
      pi = star + 1;
      mark++;
      si = mark;
    } else {
      return false;
    }
  }
  while (pi < p.length && p[pi] === "*") pi++;
  return pi === p.length;
}

/**
 * Determine whether a gateway is allowed to establish a connection (gateway allow/block list).
 *
 * Semantics consistent with daemon-side Filter.Allows:
 *   off       → always allow;
 *   whitelist → allow only if any pattern matches (empty list = deny all);
 *   blacklist → deny if any pattern matches (empty list = allow all).
 */
async function gatewayFilterAllows(gateway) {
  const { mode, patterns } = await loadGatewayFilter();
  if (mode === "off") return true;
  const key = gatewayKey(gateway);
  if (!key) return true;
  const hit = patterns.some((p) => wildcardMatch(p, key));
  return mode === "whitelist" ? hit : !hit;
}

/** Read the list of configured gateways. */
async function loadGateways() {
  const cfg = await chrome.storage.local.get(["gateways"]);
  const list = cfg.gateways;
  return Array.isArray(list) ? list : [];
}

/** Save the gateway list. */
async function saveGateways(list) {
  await chrome.storage.local.set({ gateways: list });
}

/**
 * Load persisted per-gateway Tokens from chrome.storage.local into the in-memory tokens Map.
 * Called after extension/browser restart, so connect can obtain Tokens without re-probing pages, automatically restoring login state.
 * Silently skips when storage is missing or corrupted, keeping memory empty (subsequent page probing serves as fallback).
 */
async function loadTokensFromStorage() {
  try {
    const cfg = await chrome.storage.local.get([TOKENS_KEY]);
    const saved = cfg[TOKENS_KEY];
    if (!saved || typeof saved !== "object") return;
    for (const [key, token] of Object.entries(saved)) {
      if (key && token) tokens.set(key, token);
    }
  } catch (e) {
    console.warn("[HaijunBot] load tokens from storage failed", e);
  }
}

/**
 * Persist the in-memory tokens Map to chrome.storage.local (async fire-and-forget).
 * Write failure only logs a warning and does not affect in-memory semantics (worst case is needing to re-probe pages after restart).
 */
function persistTokens() {
  const obj = {};
  for (const [key, token] of tokens.entries()) {
    if (key && token) obj[key] = token;
  }
  chrome.storage.local.set({ [TOKENS_KEY]: obj }).catch((e) => {
    console.warn("[HaijunBot] persist tokens failed", e);
  });
}

/** Normalize gateway address: strip trailing slashes. */
function normalizeGateway(gateway) {
  if (!gateway) return "";
  let g = String(gateway).trim();
  if (!g) return "";
  if (!/^https?:\/\//i.test(g)) {
    g = "http://" + g;
  }
  return g.replace(/\/+$/, "");
}

/** Parse browser name, version, and OS from User-Agent (for front-end display; falls back to empty when missing). */
function parseBrowserInfo() {
  const ua = navigator.userAgent || "";
  const result = { user_agent: ua, platform: navigator.platform || "" };
  // Browser name and version: note the order; Edge/Opera UAs also contain Chrome markers and must be matched first.
  const patterns = [
    { name: "Edge", re: /Edg\/([\d.]+)/ },
    { name: "Opera", re: /OPR\/([\d.]+)/ },
    { name: "Firefox", re: /Firefox\/([\d.]+)/ },
    { name: "Chrome", re: /Chrome\/([\d.]+)/ },
    { name: "Safari", re: /Version\/([\d.]+).*Safari\// },
    { name: "IE", re: /(?:MSIE\s|Trident\/.*rv:)([\d.]+)/ },
  ];
  for (const p of patterns) {
    const m = ua.match(p.re);
    if (m) {
      result.name = p.name;
      result.version = m[1];
      break;
    }
  }
  // Operating system (note the order: iOS UA also contains Mac OS X, must be matched first)
  if (/Windows NT/.test(ua)) result.os = "Windows";
  else if (/Android/.test(ua)) result.os = "Android";
  else if (/iPhone|iPad|iPod/.test(ua)) result.os = "iOS";
  else if (/Mac OS X/.test(ua)) result.os = "macOS";
  else if (/Linux/.test(ua)) result.os = "Linux";
  return result;
}

/** Collect browser information needed for the hello frame. */
async function buildHello() {
  const tabs = await chrome.tabs.query({});
  const hello = {
    type: "hello",
    client_id: await getClientId(),
    extension_version: EXTENSION_VERSION,
    browser_info: parseBrowserInfo(),
    tabs: tabs.map((t) => ({
      tab_id: t.id,
      url: t.url,
      title: t.title,
      active: t.active,
      window_id: t.windowId,
    })),
    // Capability list supported by this extension (dynamically reported; gateway passes to front-end capability list display)
    capabilities: router.getCapabilities(),
  };
  // Terminal name: configured by the HaijunBot web settings page; the extension caches it and reports it with hello,
  // enabling the gateway to distinguish different terminals. When empty, the field is omitted (gateway falls back to hostname).
  const name = await getTerminalName();
  if (name) hello.name = name;
  return hello;
}

/** Read cached terminal name (may be empty). */
async function getTerminalName() {
  try {
    const cfg = await chrome.storage.local.get([TERMINAL_NAME_KEY]);
    return String(cfg[TERMINAL_NAME_KEY] || "").trim();
  } catch (e) {
    console.warn("[HaijunBot] read terminal name failed", e);
    return "";
  }
}

/** Cache terminal name (empty values are not written, to avoid overwriting existing names). */
async function cacheTerminalName(name) {
  const value = String(name || "").trim();
  if (!value) return;
  try {
    await chrome.storage.local.set({ [TERMINAL_NAME_KEY]: value });
  } catch (e) {
    console.warn("[HaijunBot] cache terminal name failed", e);
  }
}

/** Stable client ID (generated on first use and persisted). */
async function getClientId() {
  const cfg = await chrome.storage.local.get(["client_id"]);
  if (cfg.client_id) return cfg.client_id;
  const id =
    "ext-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  await chrome.storage.local.set({ client_id: id });
  return id;
}

/** Broadcast status to popup (popup may not be open; failures are ignored). */
function broadcastState() {
  chrome.runtime
    .sendMessage({ type: "haijunbot_state", gateways: listStatus() })
    .catch(() => {
      // Errors when popup is not open; ignored
    });
}

/**
 * Toggle the extension toolbar icon based on connection status.
 *
 * - Any gateway is connected: use the original color icon (cyan highlight, indicating online)
 * - Otherwise (no gateways / all disconnected or connecting): use the dimmed icon (indicating offline)
 *
 * setIcon does not automatically restore after the service worker is recycled, so it is re-set on every state change;
 * failures only log a warning and do not affect connection logic.
 */
function updateActionIcon() {
  const connected = Array.from(states.values()).some((s) => s === "connected");
  const suffix = connected ? "" : "_off";
  const path = {
    16: `icons/icon16${suffix}.png`,
    32: `icons/icon32${suffix}.png`,
    48: `icons/icon48${suffix}.png`,
    128: `icons/icon128${suffix}.png`,
  };
  const title = connected
    ? "HaijunBot Browser Bridge (Connected)"
    : "HaijunBot Browser Bridge (Disconnected)";
  try {
    chrome.action
      .setIcon({ path })
      .catch((e) => console.warn("[HaijunBot] setIcon failed", e));
    chrome.action.setTitle({ title }).catch(() => {});
  } catch (e) {
    console.warn("[HaijunBot] updateActionIcon error", e);
  }
}

/** Summarize the status of all gateways. */
function listStatus() {
  const all = new Set([...clients.keys(), ...states.keys()]);
  return Array.from(all).map((gateway) => ({
    gateway,
    state: states.get(gateway) || "disconnected",
    session_id: sessions.get(gateway) || null,
    has_token: Boolean(tokens.get(gatewayKey(gateway))),
  }));
}

/**
 * Compare the gateway's packaged version with the local version; show a system notification to prompt the user to upgrade when outdated.
 *
 * Only notify once per new version (recorded in chrome.storage.local), to avoid repeated popups on every reconnect or
 * service worker wake. When notification creation fails (e.g. user has disabled notification permissions),
 * only log a warning; does not affect the connection flow.
 *
 * @param {string} gateway Gateway address, used for notification message context
 * @param {string} latest Latest extension version packaged by the gateway
 */
async function maybeNotifyUpdate(gateway, latest) {
  const latestVersion = String(latest || "").trim();
  if (!latestVersion) return;
  if (latestVersion === String(EXTENSION_VERSION).trim()) return;

  let notified = null;
  try {
    const cfg = await chrome.storage.local.get([NOTIFIED_VERSION_KEY]);
    notified = cfg[NOTIFIED_VERSION_KEY] || null;
  } catch (e) {
    console.warn("[HaijunBot] read notified version failed", e);
  }
  if (notified === latestVersion) return;

  try {
    await chrome.notifications.create(UPDATE_NOTIFICATION_ID, {
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "HaijunBot Browser Extension Update Available",
      message:
        `Current v${EXTENSION_VERSION} -> Latest v${latestVersion}. ` +
        `Please open the HaijunBot web page, re-download from "Install Browser Extension", and reload the extension.`,
      priority: 1,
    });
  } catch (e) {
    console.warn("[HaijunBot] create update notification failed", e);
    return;
  }
  console.log("[HaijunBot] update notification shown", gateway, latestVersion);

  // Record the notified version to avoid repeated interruptions; write failure does not affect the main flow
  try {
    await chrome.storage.local.set({ [NOTIFIED_VERSION_KEY]: latestVersion });
  } catch (e) {
    console.warn("[HaijunBot] save notified version failed", e);
  }
}

/** Handle messages dispatched by a gateway. */
async function handleMessage(gateway, msg) {
  if (!msg || typeof msg !== "object") return;
  switch (msg.type) {
    case "hello_ack":
      sessions.set(gateway, msg.session_id || null);
      console.log("[HaijunBot] hello_ack", gateway, "session_id=", msg.session_id);
      // Successful handshake means the Token is valid; reset auth failure count
      authErrorAttempts.delete(gatewayKey(gateway));
      setState(gateway, "connected");
      // Gateway sends latest version with handshake: new versions can be discovered without opening the HaijunBot web page
      maybeNotifyUpdate(gateway, msg.latest_extension_version).catch((e) =>
        console.warn("[HaijunBot] maybeNotifyUpdate error", e),
      );
      break;
    case "command": {
      // Pass the command source gateway and login Token to the router: screenshot-type capabilities need to upload results to
      // "the gateway where the Agent that invoked this command resides" (= command source gateway), reusing login session for auth.
      const result = await router.handle(msg, {
        gateway,
        token: tokens.get(gatewayKey(gateway)),
      });
      const client = clients.get(gateway);
      const ok = client && client.send(result);
      if (!ok) {
        console.warn(
          "[HaijunBot] failed to send result (disconnected)",
          gateway,
          result.id,
        );
      }
      break;
    }
    case "error":
      console.warn("[HaijunBot] gateway error", gateway, msg.payload);
      break;
    default:
      console.log("[HaijunBot] unknown message", gateway, msg.type);
  }
}

/**
 * Update a gateway's state and broadcast.
 *
 * Return directly when state has not changed: MV3's service worker re-runs module top-level code on every wake
 * (including connectAll), creating a new WsClient for each gateway and going through connecting -> connected
 * -> hello_ack again; without deduplication, every wake would send multiple broadcasts to the popup, forming a broadcast storm.
 */
function setState(gateway, state) {
  if (states.get(gateway) === state) return;
  states.set(gateway, state);
  updateActionIcon();
  broadcastState();
}

/**
 * Handle gateway authentication failure (WebSocket closed with 4401/4403).
 *
 * Typical scenario: after gateway restart, the JWT signing key changes (randomly generated on each start when HAIJUNBOT_JWT_SECRET is not set),
 * and the old Token cached in the browser page's localStorage immediately becomes invalid; continuing to reconnect with the old Token
 * will result in an infinite "disconnect-reconnect" loop.
 *
 * Handling strategy: clear that gateway's Token cache, re-probe from the page once (if the user has re-logged in, a new Token can be obtained);
 * reconnect if probing succeeds, stop auto-reconnect and prompt the user to re-login if it fails, avoiding futile cycles.
 */
async function handleAuthError(gateway, code, reason) {
  const g = normalizeGateway(gateway);
  const tokenKey = gatewayKey(g);
  console.warn(
    "[HaijunBot] auth error, clearing cached token",
    g,
    "code=",
    code,
    "reason=",
    reason,
  );
  tokens.delete(tokenKey);
  persistTokens();
  // Discard the old connection holding the invalid Token, to avoid subsequent connect reusing it
  const stale = clients.get(g);
  if (stale) {
    clients.delete(g);
    stale.close();
  }
  sessions.delete(g);
  setState(g, "disconnected");

  // Consecutive auth failure count: the Token in the page may also be invalid (user has not yet re-logged in),
  // in which case re-probing would get the same old Token; retry count must be limited to avoid another cycle.
  const attempts = (authErrorAttempts.get(tokenKey) || 0) + 1;
  authErrorAttempts.set(tokenKey, attempts);
  if (attempts > AUTH_ERROR_MAX_RETRIES) {
    console.warn(
      "[HaijunBot] auth failed repeatedly, stop reconnecting. " +
        "Please re-login to the HaijunBot page for this gateway in the browser, then click \"Connect\".",
      g,
    );
    broadcastState();
    return;
  }

  let token = null;
  try {
    token = await refreshTokenFromPages(g);
  } catch (e) {
    console.warn("[HaijunBot] token re-probe failed", g, e);
  }
  if (!token) {
    console.warn(
      "[HaijunBot] no valid token after auth error, stop reconnecting:",
      g,
    );
    broadcastState();
    return;
  }
  console.log(
    "[HaijunBot] reconnecting with refreshed token for",
    g,
    `(attempt ${attempts}/${AUTH_ERROR_MAX_RETRIES})`,
  );
  try {
    await connect(g, true);
  } catch (e) {
    console.warn("[HaijunBot] reconnect after auth error failed", g, e);
  }
}

/**
 * Establish a connection to the specified gateway.
 *
 * @param {string} gateway Gateway address
 * @param {boolean} force When true, force rebuild the connection (user explicitly clicked "Connect" for retry);
 *   when false, if there is already a connecting/connected connection, reuse it directly,
 *   to avoid killing and rebuilding healthy connections when the service worker wakes and re-runs connectAll.
 */
async function connect(gateway, force = false) {
  const g = normalizeGateway(gateway);
  if (!g) {
    console.warn("[HaijunBot] empty gateway, skip connect");
    return;
  }
  // Gateway allow/block list interception: this is the single entry point for all connections (auto-discovery, popup clicks,
  // auth failure reconnects all go through here), so checking here covers all paths.
  // Only blocks "new connections"; does not actively disconnect existing connections (consistent with daemon-side semantics).
  if (!(await gatewayFilterAllows(g))) {
    console.warn("[HaijunBot] gateway blocked by filter, skip connect:", g);
    setState(g, "disconnected");
    throw new Error(`Gateway ${g} is not in the allow list (blocked by gateway allow/block list).`);
  }
  if (!force) {
    const current = clients.get(g);
    if (current && current.isAlive()) {
      console.log("[HaijunBot] connect: reuse existing connection for", g);
      return;
    }
  } else {
    // User-initiated connection (force=true): reset auth failure count to allow retry
    authErrorAttempts.delete(gatewayKey(g));
  }
  // Token prefers current login session; if not yet obtained, actively request from the page once
  const tokenKey = gatewayKey(g);
  let token = tokens.get(tokenKey);
  if (!token) {
    console.log("[HaijunBot] connect: no cached token, probing pages for", g);
    token = await requestTokenFromPages(g);
    console.log("[HaijunBot] connect: probe done, has_token=", Boolean(token));
    if (token) {
      tokens.set(tokenKey, token);
      persistTokens();
    }
  }
  if (!token) {
    console.warn(
      "[HaijunBot] no auth token yet for",
      g,
      ", waiting for HaijunBot page",
    );
    setState(g, "disconnected");
    throw new Error(
      `No login session Token obtained for ${g}. Please open and login to the HaijunBot page for this gateway in the browser first, then retry.`,
    );
  }

  const existing = clients.get(g);
  if (existing) {
    existing.close();
  }

  const client = new WsClient({
    onMessage: (msg) => handleMessage(g, msg),
    onStateChange: (state) => setState(g, state),
    onAuthError: (code, reason) => handleAuthError(g, code, reason),
  });
  client.onOpen = async () => {
    try {
      const hello = await buildHello();
      client.send(hello);
    } catch (e) {
      console.error("[HaijunBot] send hello failed", g, e);
    }
  };
  clients.set(g, client);
  client.connect(g, token);
}

/**
 * Disconnect a specified gateway connection.
 *
 * Immediately clear that gateway's Token cache after disconnect, to avoid the next connection reusing a potentially invalid old Token;
 * then asynchronously re-probe the login state from the page; if found, write back to cache for direct use by the next connect
 * (probe results do not trigger a connection; the WebSocket is only established when the user clicks "Connect").
 *
 * @param {string} gateway Gateway address
 * @param {boolean} skipProbe When true, do not re-probe Token (used for scenarios like removing a gateway)
 */
function disconnect(gateway, skipProbe = false) {
  const g = normalizeGateway(gateway);
  const client = clients.get(g);
  if (client) {
    client.close();
    clients.delete(g);
  }
  sessions.delete(g);
  const tokenKey = gatewayKey(g);
  // Clear Token cache to avoid reusing invalid Token
  tokens.delete(tokenKey);
  persistTokens();
  // Active disconnect is treated as user intent; reset auth failure count
  authErrorAttempts.delete(tokenKey);
  setState(g, "disconnected");
  if (skipProbe) return;
  // Asynchronously re-probe page login state without blocking the disconnect flow
  refreshTokenFromPages(g).catch((e) =>
    console.warn("[HaijunBot] refresh token after disconnect failed", g, e),
  );
}

/**
 * Re-probe Token from the page and write back to cache (does not establish a connection).
 * When probing fails, do not write; keep cache empty and let subsequent connect decide how to prompt.
 */
async function refreshTokenFromPages(gateway) {
  const g = normalizeGateway(gateway);
  if (!g) return null;
  let token = null;
  try {
    token = await requestTokenFromPages(g);
  } catch (e) {
    console.warn("[HaijunBot] token probe failed", g, e);
    return null;
  }
  if (token) {
    tokens.set(gatewayKey(g), token);
    persistTokens();
    console.log("[HaijunBot] token refreshed from page for", g);
  } else {
    console.log("[HaijunBot] no token available from page for", g);
  }
  return token;
}

/**
 * Normalize to host:port for comparison.
 * The gateway declared by the front-end page and the gateway entered by the user may differ in protocol
 * (e.g. page says http://host:443, user says https://host:443),
 * so comparison ignores protocol differences and only compares host and port.
 */
function gatewayKey(gateway) {
  let g = String(gateway || "").trim();
  if (!g) return "";
  // Explicitly recognize ws:// and wss://: gateway addresses that daemon/extension connects to may naturally be WebSocket
  // form; if passed to normalizeGateway, an "http://" prefix would be wrongly added, causing URL parsing to treat
  // "ws" as the hostname and lose the port, making the allow/block list fail to match.
  if (/^wss?:\/\//i.test(g)) {
    g = g.replace(/\/+$/, "");
  } else {
    g = normalizeGateway(g);
  }
  if (!g) return "";
  try {
    const url = new URL(g);
    const port =
      url.port ||
      (url.protocol === "https:" || url.protocol === "wss:" ? "443" : "80");
    return `${url.hostname}:${port}`;
  } catch (e) {
    return g;
  }
}

/**
 * Read the Token and gateway address exposed by __haijunbotAuthBridge in the tab's main world.
 * Must be injected via chrome.scripting.executeScript({ world: "MAIN" }):
 * in MV3, dynamically inserted inline scripts from the isolated world (content script) will not execute in the main world.
 * This function is serialized before injection and must not reference external variables.
 * @returns {{token: string|null, gateway: string|null, name: string|null}|null}
 */
function readAuthBridgeInMainWorld() {
  try {
    const bridge = window.__haijunbotAuthBridge;
    if (!bridge) return null;
    const token =
      typeof bridge.getToken === "function" ? bridge.getToken() || null : null;
    let gateway = null;
    if (typeof bridge.getGateway === "function") {
      gateway = bridge.getGateway() || null;
    }
    // Terminal name: configured by the page settings page, reported to gateway with hello
    let name = null;
    if (typeof bridge.getName === "function") {
      name = bridge.getName() || null;
    }
    return { token, gateway: gateway || location.origin, name };
  } catch (e) {
    return null;
  }
}

/**
 * Actively read the login session Token for the specified gateway from already-open HaijunBot pages.
 * Reads the page-exposed __haijunbotAuthBridge via main world injection,
 * where gateway is declared by the page via __haijunbotAuthBridge.getGateway() (gateway and front-end may be on different domains).
 */
async function requestTokenFromPages(gateway) {
  const g = normalizeGateway(gateway);
  const gKey = gatewayKey(g);
  try {
    const tabs = await chrome.tabs.query({});
    console.log("[HaijunBot] token probe start, tabs=", tabs.length);
    for (const tab of tabs) {
      if (!tab.id || !/^https?:/i.test(tab.url || "")) continue;
      try {
        const results = await withTimeout(
          chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: readAuthBridgeInMainWorld,
            world: "MAIN",
          }),
          3000,
          `executeScript timeout: ${tab.url}`,
        );
        const resp = results && results[0] ? results[0].result : null;
        if (!resp) continue;
        console.log(
          "[HaijunBot] token probe",
          tab.url,
          "gateway=",
          resp.gateway,
          "has_token=",
          Boolean(resp.token),
        );
        if (!resp.token) continue;
        // Also cache the page-configured terminal name for hello reporting (uses cached value when page is not open)
        if (resp.name) await cacheTerminalName(resp.name);
        // Only accept responses where the declared gateway matches the target gateway (ignoring protocol differences)
        if (gatewayKey(resp.gateway) === gKey) {
          return resp.token;
        }
      } catch (e) {
        // This tab cannot be injected (restricted pages etc.), skip
        console.log(
          "[HaijunBot] token probe skipped",
          tab.url,
          "reason=",
          (e && e.message) || String(e),
        );
      }
    }
  } catch (e) {
    console.warn("[HaijunBot] requestTokenFromPages failed", g, e);
  }
  return null;
}

/**
 * Scan all tabs and collect "(gateway, token)" for gateways that are "logged in and have declared a gateway address".
 *
 * Used for auto-discovering the user's logged-in gateways: the extension does not require the user to manually fill in gateway addresses;
 * as long as a HaijunBot page for some gateway is open in the browser and in a logged-in state, it can be automatically added to the gateway list.
 * Difference from requestTokenFromPages: the latter only probes for a specified gateway, while this function return all matches.
 *
 * @returns {Promise<Array<{gateway: string, token: string}>>}
 */
async function discoverGatewaysFromPages() {
  const found = new Map(); // gatewayKey -> {gateway, token}
  let tabs = [];
  try {
    tabs = await chrome.tabs.query({});
  } catch (e) {
    console.warn("[HaijunBot] discover: query tabs failed", e);
    return [];
  }
  for (const tab of tabs) {
    if (!tab.id || !/^https?:/i.test(tab.url || "")) continue;
    let resp = null;
    try {
      const results = await withTimeout(
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: readAuthBridgeInMainWorld,
          world: "MAIN",
        }),
        3000,
        `executeScript timeout: ${tab.url}`,
      );
      resp = results && results[0] ? results[0].result : null;
    } catch (e) {
      // This tab cannot be injected (restricted pages etc.), skip
      continue;
    }
    if (!resp || !resp.token) continue;
    const g = normalizeGateway(resp.gateway);
    if (!g) continue;
    // Also cache the page-configured terminal name for hello reporting
    if (resp.name) await cacheTerminalName(resp.name);
    const key = gatewayKey(g);
    if (!found.has(key)) found.set(key, { gateway: g, token: resp.token });
  }
  return Array.from(found.values());
}

/**
 * Automatically add "gateways already logged in from pages" to the configuration list and connect.
 *
 * Trigger timing: extension start/install, service worker cold start (see connectAll).
 * Idempotent: gateways already in the configuration list are not written again, but their Token cache is refreshed.
 * A single gateway connection failure does not affect other gateways (silently logs).
 *
 * @returns {Promise<string[]>} Gateway addresses newly added to the configuration list this time
 */
async function autoDiscoverGateways() {
  const discovered = await discoverGatewaysFromPages();
  if (discovered.length === 0) return [];
  const list = await loadGateways();
  const configured = new Set(list.map(gatewayKey));
  const added = [];
  for (const { gateway, token } of discovered) {
    const key = gatewayKey(gateway);
    tokens.set(key, token);
    persistTokens();
    if (!configured.has(key)) {
      list.push(gateway);
      configured.add(key);
      added.push(gateway);
    }
  }
  if (added.length > 0) {
    await saveGateways(list);
    console.log("[HaijunBot] auto-added gateways from pages:", added.join(", "));
    broadcastState();
  }
  // Connect all discovered gateways (including newly added this time and already-configured ones where page re-probing found a Token)
  for (const { gateway } of discovered) {
    try {
      await connect(gateway);
    } catch (e) {
      console.warn(
        "[HaijunBot] auto-connect discovered gateway failed",
        gateway,
        e,
      );
    }
  }
  return added;
}

/** Add timeout protection to a Promise, to avoid individual tab injection hangs dragging down the overall flow. */
function withTimeout(promise, ms, message) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(message)), ms);
    promise.then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      },
    );
  });
}

/** Add a gateway to the configuration list (deduplicated). */
async function addGateway(gateway) {
  const g = normalizeGateway(gateway);
  if (!g) return;
  const list = await loadGateways();
  const normalized = list.map(normalizeGateway);
  if (!normalized.includes(g)) {
    list.push(g);
    await saveGateways(list);
  }
}

// ---------------- Interaction with popup ----------------

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) return false;

  if (message.type === "haijunbot_connect") {
    const gateway = message.gateway;
    if (!gateway) {
      sendResponse({ success: false, error: "gateway is required" });
      return true;
    }
    addGateway(gateway)
      .then(() => connect(gateway, true))
      .then(() => sendResponse({ success: true }))
      .catch((e) =>
        sendResponse({ success: false, error: (e && e.message) || String(e) }),
      );
    return true; // Async response
  }
  if (message.type === "haijunbot_disconnect") {
    if (message.gateway) {
      disconnect(message.gateway);
    } else {
      // Disconnect all when not specified
      for (const g of Array.from(clients.keys())) {
        disconnect(g);
      }
    }
    sendResponse({ success: true });
    return true;
  }
  if (message.type === "haijunbot_get_status") {
    sendResponse({ success: true, gateways: listStatus() });
    return true;
  }
  // Gateway allow/block list: read (populate form when popup opens)
  if (message.type === "haijunbot_get_gateway_filter") {
    loadGatewayFilter()
      .then((v) => sendResponse({ success: true, ...v }))
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  // Gateway allow/block list: save (popup submits form)
  if (message.type === "haijunbot_set_gateway_filter") {
    saveGatewayFilter(message.mode, message.patterns)
      .then((v) => {
        // After list changes, do not actively disconnect currently "configured but rejected" gateways (consistent with only blocking
        // new connections semantics); only broadcast state once for popup refresh.
        broadcastState();
        sendResponse({ success: true, ...v });
      })
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  if (message.type === "haijunbot_remove_gateway") {
    const g = normalizeGateway(message.gateway);
    // Gateway has been removed; no need to probe Token anymore
    disconnect(g, true);
    // disconnect rewrites states; clean up afterwards to avoid residual ghost entries
    clients.delete(g);
    sessions.delete(g);
    tokens.delete(gatewayKey(g));
    persistTokens();
    states.delete(g);
    loadGateways()
      .then((list) =>
        saveGateways(list.filter((x) => normalizeGateway(x) !== g)),
      )
      .then(() => {
        broadcastState();
        sendResponse({ success: true });
      })
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  // ---------------- Script management (Tampermonkey-like) ----------------
  // popup manages installed scripts via the following messages, uniformly forwarded to CommandRouter's script.* routes.
  if (message.type === "haijunbot_script_list") {
    router
      .handle({ id: "popup", action: "script.list", params: {} })
      .then(sendResponse)
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  if (message.type === "haijunbot_script_get") {
    router
      .handle({ id: "popup", action: "script.get", params: { id: message.id } })
      .then(sendResponse)
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  if (message.type === "haijunbot_script_install") {
    router
      .handle({
        id: "popup",
        action: "script.install",
        params: {
          name: message.name,
          source: message.source,
          description: message.description,
          match: message.match,
          version: message.version,
        },
      })
      .then(sendResponse)
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  // Download and install script from URL (source is fetched by background-side fetch; popup does not touch source code)
  if (message.type === "haijunbot_script_install_from_url") {
    router
      .handle({
        id: "popup",
        action: "script.install_from_url",
        params: {
          url: message.url,
          name: message.name,
          description: message.description,
          match: message.match,
          version: message.version,
        },
      })
      .then(sendResponse)
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  if (message.type === "haijunbot_script_uninstall") {
    router
      .handle({
        id: "popup",
        action: "script.uninstall",
        params: { id: message.id },
      })
      .then(sendResponse)
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  if (message.type === "haijunbot_script_export") {
    router
      .handle({
        id: "popup",
        action: "script.export",
        params: { id: message.id },
      })
      .then(sendResponse)
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  if (message.type === "haijunbot_script_set_enabled") {
    router
      .handle({
        id: "popup",
        action: "script.set_enabled",
        params: { id: message.id, enabled: message.enabled },
      })
      .then(sendResponse)
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }
  // Content script injection report (for diagnostics)
  if (message.type === "haijunbot_cs_loaded") {
    console.log("[HaijunBot] content script loaded:", message.url);
    return false;
  }
  return false;
});

/**
 * Cold start: first auto-discover gateways already logged in from pages (no manual configuration needed), then establish connections for all configured gateways.
 *
 * Auto-discovery failure (e.g. no HaijunBot pages at all) does not affect subsequent connections for configured gateways.
 */
async function connectAll() {
  // First restore persisted login Tokens, so configured gateways can connect directly without re-probing pages.
  await loadTokensFromStorage();
  try {
    await autoDiscoverGateways();
  } catch (e) {
    console.warn("[HaijunBot] auto discover gateways failed", e);
  }
  const list = await loadGateways();
  for (const gateway of list) {
    await connect(gateway);
  }
}

// Auto-connect on extension install/startup
chrome.runtime.onStartup.addListener(() => {
  connectAll();
});

/**
 * Trigger an auto-discovery when a tab finishes loading.
 *
 * Covers the scenario where "extension is installed first, HaijunBot page is opened/logged in later": at cold start the page is not yet logged in,
 * so no gateway can be probed; after the user opens and logs in to the HaijunBot page, this can automatically add that gateway to the list and connect.
 * autoDiscoverGateways is idempotent (configured gateways only refresh Token and reuse connections),
 * so triggering once per page load is safe.
 */
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") return;
  if (!/^https?:/i.test(tab && tab.url ? tab.url : "")) return;
  autoDiscoverGateways().catch((e) =>
    console.warn("[HaijunBot] auto discover on tab update failed", e),
  );
});

chrome.runtime.onInstalled.addListener(() => {
  connectAll();
});

// Also attempt connection on service worker cold start
updateActionIcon(); // Set icon to offline state on cold start; setState will switch it after successful connection
connectAll();
