# Browser Extension Plan: Allow the Agent to Operate the User's Real Browser

> Status: Design draft
> Goal: Let the Agent operate **any web page** in the user's **local real browser** (reusing login state, cookies, and already-open tabs)
> Related modules: `haijunbot_web_gateway`, `haijunbot_browser`, `haijunbot_tools`

---

## 1. Background and Problem

### 1.1 Current State

HaijunBot's existing browser capability is provided by `haijunbot-browser` (CLI name `hb`), implemented in `src/haijunbot/haijunbot_browser/eli.py`.

Key facts (verified):

- `eli.py:1788` uses `_playwright_context.chromium.launch(headless=headless)` to start a **brand-new standalone Chromium instance**.
- `eli.py:1798` only calls `browser.new_context()` — **no** `user_data_dir`, **no** `launch_persistent_context`, **no** `storage_state`.
- `eli.py:837-848` the daemon detaches from the terminal via a double fork (`os.fork()` + `os.setsid()`) and runs in the **server-side background**.
- The entire codebase has **no** CDP / `connect_over_cdp` / extension communication mechanism at all.

### 1.2 Fundamental Limitation

`hb` operates "**a browser spawned out of nowhere on the server**":

- It has **nothing to do** with the browser on the user's desktop;
- It does not share the user's login state, cookies, bookmarks, or already-open tabs;
- The so-called "UI mode" merely opens a window **on the machine running the Agent**; the user may be across a network and can neither see nor touch it.

Therefore `hb` **cannot satisfy** the requirement of "operating the user's own web pages".

### 1.3 Goals

| Item           | Requirement                                                  |
| -------------- | ----------------------------------------------------------- |
| Target         | **Any currently open tab** in the user's local real browser |
| Login state    | Directly reuse the user's existing Cookie / Session, no re-login needed |
| Coverage       | Any `http(s)` web page                                      |
| Trigger        | The Agent issues commands via tools; the user sees live operations in the browser |
| Security       | The user explicitly installs and authorizes; commands are auditable; sensitive operations are controllable |

### 1.4 Non-Goals

- Not a replacement for `hb`: `hb` remains suited to "no-login, server-side batch scraping/testing" scenarios.
- No attempt to operate browser-protected pages such as `chrome://*` or extension store pages.
- No silent installation or bypassing user authorization.

---

## 2. Solution Overview

### 2.1 Core Idea

Replace the **execution engine** from "server-side Playwright" with "**an extension inside the user's browser**":

```text
┌──────────────────────────────── Server (HaijunBot Gateway) ────────────────────────────────┐
│  Agent (code agent / chat agent)                                                       │
│     │  invokes tool browser_ext_*                                                      │
│     ▼                                                                                  │
│  BrowserExtensionManager  ── session registry / command routing / result return        │
│     │                                                                                  │
│  WebSocket endpoint  /api/browser-ext/ws                                               │
└─────┼───────────────────────────────────────────────────────────────────────────────────┘
      │  WebSocket (wss/ws)
      │  The user's browser initiates the outbound connection (NAT-friendly; no public port needed)
      ▼
┌────────────────────────────────── User's local browser ─────────────────────────────────┐
│  Chrome/Edge extension (Manifest V3)                                                     │
│   ├─ background service worker  ← message bridge + command executor                      │
│   ├─ content script (on-demand injection)  ← DOM reading / event dispatch               │
│   └─ popup / options            ← connection config, authorization, session state       │
│                                                                                          │
│  chrome.tabs / chrome.scripting / chrome.debugger  →  user's real tabs                    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Why This Works

1. **The extension runs inside the user's browser process**, naturally possessing the current login state, cookies, and all tabs.
2. `chrome.tabs` + `chrome.scripting.executeScript` can read/write the DOM and dispatch events on any `http(s)` page.
3. The gateway already has mature WebSocket infrastructure (`app.py:2896` `/ws`, `app.py:2904` `/ws/node`); adding one extension-specific endpoint can reuse the same auth and connection-management patterns.
4. The browser **connects outbound** to the gateway, so the user side needs no open ports or public IP.

### 2.3 Comparison with `hb`

| Dimension         | `hb` (Playwright)          | Browser extension (this plan)        |
| ----------------- | -------------------------- | ------------------------------------ |
| Browser instance  | Fresh, created on server   | User's real browser                  |
| Login state/Cookie| None                       | Reused directly                      |
| Tabs              | New blank page             | User's current tabs                  |
| User visibility   | Server-side window, usually invisible to the user | Visible live in front of the user    |
| Coverage          | Any web page               | Any `http(s)` page (except protected pages) |
| Install cost      | Already available          | Requires development + manual install |
| Multi-user        | Shared server environment  | Naturally isolated per user          |

---

## 3. Component Design

### 3.1 Browser Extension (Client)

#### 3.1.1 Directory Structure

```text
browser_extension/
├── manifest.json
├── background/
│   ├── service_worker.js      # entry: connection management + command dispatch
│   ├── ws_client.js           # WebSocket connection, heartbeat, reconnect
│   ├── command_router.js      # command → executor mapping
│   └── executors/
│       ├── tab_executor.js    # tab related (list/activate/close/navigate)
│       ├── dom_executor.js    # DOM related (query/click/type/getText)
│       ├── script_executor.js # arbitrary JS execution
│       └── capture_executor.js# screenshot / capture
├── content/
│   └── content_script.js      # in-page DOM operations (injected on demand)
├── popup/
│   ├── popup.html             # connection config, status display, authorization switch
│   └── popup.js
└── icons/
```

#### 3.1.2 manifest.json Key Points

```json
{
  "manifest_version": 3,
  "name": "HaijunBot Browser Bridge",
  "version": "0.1.0",
  "permissions": ["tabs", "scripting", "activeTab", "storage", "debugger"],
  "host_permissions": ["<all_urls>"],
  "background": {
    "service_worker": "background/service_worker.js",
    "type": "module"
  },
  "action": { "default_popup": "popup/popup.html" },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content/content_script.js"],
      "run_at": "document_idle",
      "all_frames": false
    }
  ]
}
```

Notes:

- `host_permissions: <all_urls>` is a prerequisite for covering any web page; the user will see a clear authorization prompt during installation.
- The `debugger` permission is an **optional enhancement**: once enabled, `chrome.debugger` (CDP) enables lower-level operations (real mouse trajectories, network interception, cross-origin iframes). It is disabled by default and available as a later-phase capability.
- `content_scripts` can also be changed to **on-demand injection** (`chrome.scripting.executeScript`) to reduce interference with the user's browsing; at implementation time, choose one of the two approaches or keep both.

#### 3.1.3 Connection Management (ws_client.js)

- The user fills in the gateway address (e.g. `wss://hjb-ai.cn`) and token in the popup.
- Connection URL: `{gateway}/api/browser-ext/ws`.
- Auth reuses the existing subprotocol pattern (see `app.py:7649` `_extract_auth_from_headers`):
  `new WebSocket(url, ['haijunbot-ext', 'haijunbot-token.<urlencoded-token>'])`.
- Heartbeat: send `{"type":"ping"}` every 20s; the server replies with `{"type":"pong"}`; reconnect after 2 missed responses.
- Reconnect: exponential backoff (1s → 2s → 4s … capped at 30s).
- On auth failure (`onclose` receiving `4401` Unauthorized / `4403` Forbidden) **do not enter exponential-backoff reconnect**:
  the current token is already invalid, and reconnecting with the same token is guaranteed to be rejected again, which would form an infinite "disconnect–reconnect" loop.
  Instead, hand off to `handleAuthError()`: clear the cached token for that gateway, drop the old connection, and re-probe the page for a token once.
  If a new token is found, reconnect; otherwise stop auto-reconnect and prompt the user to log in again.
- Commands are not buffered while disconnected (to avoid stale commands performing accidental operations); the Agent side perceives the failure.

#### 3.1.4 Command Execution (command_router.js)

Unified message envelope:

```json
{
  "id": "req-<uuid>",
  "type": "command",
  "action": "dom.click",
  "params": { "selector": "#submit", "tab_id": 123 },
  "timeout_ms": 15000
}
```

Response envelope:

```json
{
  "id": "req-<uuid>",
  "type": "result",
  "success": true,
  "data": { "ok": true },
  "error": null
}
```

### 3.2 Gateway Side (Server)

#### 3.2.1 New Module `browser_extension_manager.py`

Responsibilities:

- Maintain the extension connection registry: `session_id → {websocket, user_id, client_id, tabs_meta, connected_at}`
- Command routing: `send_command(session_id, action, params) → result` (with timeout)
- Result return: match responses by `id` via `asyncio.Future`
- Session lifecycle: connect/disconnect events, heartbeat-timeout cleanup

Core interface (pseudocode):

```python
class BrowserExtensionManager:
    async def handle_extension_websocket(self, websocket: WebSocket) -> None: ...
    async def send_command(self, session_id: str, action: str,
                           params: dict, timeout: float = 15.0) -> dict: ...
    def list_sessions(self, user_id: str | None = None) -> list[dict]: ...
    async def disconnect(self, session_id: str) -> None: ...
```

#### 3.2.2 New WebSocket Endpoint

In `app.py`, add it following the style of `app.py:2904` `/ws/node`:

```python
@app.websocket("/api/browser-ext/ws")
async def browser_ext_websocket_endpoint(websocket: WebSocket) -> None:
    await browser_extension_manager.handle_extension_websocket(websocket)
```

The auth flow reuses `_extract_auth_from_headers` (`app.py:7649`) + `gateway._check_auth` (`gateway.py:63`), staying consistent with `/api/agent/{agent_id}/ws` at `app.py:2927-2937`.

#### 3.2.3 New Agent Tools

Add a new tool module `src/haijunbot/haijunbot_tools/browser_ext.py` and register it in `registry.py`. Suggested toolset:

| Tool name                   | Purpose                              | Key parameters                          |
| --------------------------- | ------------------------------------ | --------------------------------------- |
| `browser_ext_list_sessions` | List currently available user-browser sessions | None                          |
| `browser_ext_list_tabs`     | List tabs of a target session        | `session_id`                            |
| `browser_ext_navigate`      | Navigate to a URL                    | `session_id`, `tab_id`, `url`           |
| `browser_ext_get_text`      | Read element text                    | `session_id`, `tab_id`, `selector`      |
| `browser_ext_click`         | Click an element                     | `session_id`, `tab_id`, `selector`      |
| `browser_ext_type`          | Type text                            | `session_id`, `tab_id`, `selector`, `text` |
| `browser_ext_execute_js`    | Execute arbitrary JS in the page     | `session_id`, `tab_id`, `code`          |
| `browser_ext_screenshot`    | Take a screenshot                    | `session_id`, `tab_id`                  |
| `browser_ext_wait_for`      | Wait for an element/condition        | `session_id`, `tab_id`, `selector`      |

Internally the tools dispatch commands through the global `browser_extension_manager` instance.

#### 3.2.4 Permission Design

**No permission checks are introduced.** Decision: browser-control capabilities are not permission-controlled.

- No new `browser:*` permission resource, no changes to `permission_manager.py` or the frontend permission matrix.
- Tool calls do not go through `check_permission`, consistent with the current "open when nobody checks" state of chat features.
- The security boundary is carried by the **extension side**: the extension requires manual installation plus authorization of `<all_urls>`, and the connection must carry a valid gateway token (see 3.1.3 and section 6).

> Note: if tightening is needed later, a `browser:control` permission can be added following the existing `resource:action` model — an incremental change that does not affect the rest of this design.

---

## 4. Message Protocol

### 4.1 Transport Layer

- Protocol: WebSocket (text frames, JSON)
- Endpoint: `/api/browser-ext/ws`
- Auth: subprotocols `haijunbot-ext` + `haijunbot-token.<token>`
- Heartbeat: `ping` / `pong`

### 4.2 Message Types

| type            | Direction        | Description                                        |
| --------------- | ---------------- | --------------------------------------------------- |
| `hello`         | extension → gateway | First frame after connecting; reports extension version, browser info, current tab snapshot |
| `hello_ack`     | gateway → extension | Confirmation; returns `session_id`              |
| `command`       | gateway → extension | Issue a command                                |
| `result`        | extension → gateway | Command execution result                       |
| `event`         | extension → gateway | Unsolicited reports (tab changes, page navigation, etc.) |
| `ping` / `pong` | both             | Heartbeat                                          |

### 4.3 Command Action List (action)

#### Tab Actions

- `tab.list` → `[{tab_id, url, title, active, window_id}]`
- `tab.activate` `{tab_id}`
- `tab.close` `{tab_id}`
- `tab.create` `{url, active, new_window}` (`new_window` defaults to `true`: prefer creating the tab in a window that does **not contain a HaijunBot frontend page**; only open a new window when every window contains a HaijunBot page. Pass `false` to create in the current window)

#### Navigation Actions

- `page.navigate` `{tab_id, url, wait_until, new_window}` (when `tab_id` is omitted, reuse the `tab.create` window-selection strategy)
- `page.reload` `{tab_id}`
- `page.back` / `page.forward` `{tab_id}`

**DOM Actions** (via content script or `chrome.scripting`)

- `dom.query` `{tab_id, selector, all}` → element info
- `dom.get_text` `{tab_id, selector}`
- `dom.get_html` `{tab_id, selector}`
- `dom.click` `{tab_id, selector}`
- `dom.type` `{tab_id, selector, text, clear}`
- `dom.hover` `{tab_id, selector}`
- `dom.select` `{tab_id, selector, value}`
- `dom.wait_for` `{tab_id, selector, state, timeout_ms}`

#### Script Actions

- `script.execute` `{tab_id, code, world}` → return value (`world`: `MAIN` | `ISOLATED`)

#### Script Library Actions (Tampermonkey-like script management)

- `script.list` → list of installed scripts
- `script.get` `{script_id}` → content of a single script
- `script.install` `{name, code, ...}` → install a script (enabled by default)
- `script.uninstall` `{script_id}` → uninstall a script (**irreversible**)
- `script.export` `{script_id}` → export the script text for backup
- `script.set_enabled` `{script_id, enabled}` → enable/disable; when disabled, `script.run` returns `SCRIPT_DISABLED`
- `script.run` `{script_id, tab_id}` → run an installed script in the specified tab

#### Clipboard Actions

- `clipboard.write` `{text}` → write text/base64 into the **frontend page's** system clipboard (the page must have focus)
- `clipboard.write_from_url` `{url, ...}` → the background `fetch` reads a file from the gateway static directory first, then injects it into the page and writes it to the clipboard

#### Debug Actions (F12-equivalent)

- `console.get_logs` `{tab_id, limit, clear}` → `{logs, count}`; hook `console.*` / `window.onerror` / `unhandledrejection` in the MAIN world, ring buffer of 500 entries
- `dom.get_computed_style` `{tab_id, selector, props}` → `{selector, styles}`; when `props` is omitted, return 22 common properties
- `page.get_info` `{tab_id}` → `{url, title, ready_state, viewport, scroll, document}`
- `debugger.evaluate` `{tab_id, expression, await_promise}` → `{ok, result, type}`; goes through CDP `Runtime.evaluate`, **not subject to page CSP**
- `debugger.send_command` `{tab_id, method, cdp_params}` → pass through any CDP command (e.g. `Page.addScriptToEvaluateOnNewDocument`)
- `network.get_requests` `{tab_id, duration_ms, limit, filter}` → `{requests, count, duration_ms}`; uses the CDP `Network` domain, recording requests/responses/latency within the collection window

#### Capture Actions

- `capture.screenshot` `{tab_id, full_page}` → base64 PNG; `full_page` is implemented by scrolling screenshot per screen + `OffscreenCanvas` stitching

#### Bookmark Actions (requires `bookmarks` permission)

- `bookmark.list` `{parent_id}` → the bookmark tree, or child nodes of a specified folder; when `parent_id` is omitted, return the whole tree
- `bookmark.search` `{query, max_results}` → list of bookmarks matching title or URL
- `bookmark.create` `{title, url, parent_id}` → `{ok, bookmark}`; when `parent_id` is omitted, place in "Other bookmarks"
- `bookmark.remove` `{id}` → `{ok}` (**irreversible**)
- `bookmark.remove_tree` `{id}` → `{ok}`, removes the folder and all its child nodes (**irreversible**)

#### History Actions (requires `history` permission)

- `history.search` `{query, start_time, end_time, max_results}` → list of history entries (times are millisecond timestamps)
- `history.recent` `{max_results}` → recent entries sorted by visit time descending
- `history.remove` `{url}` → delete all history for that URL (**irreversible**)
- `history.remove_range` `{start_time, end_time}` → delete history within the time range (**irreversible**); omitting times clears all history

#### Session Actions

- `session.recent` `{max_results}` → recently closed tab/window sessions
- `session.restore` `{session_id}` → restore the specified session

#### Download Actions (requires `downloads` permission)

- `download.list` `{query, limit}` → download records list
- `download.search` `{query, limit}` → search download records by filename/URL
- `download.start` `{url, filename, save_as}` → create a new download task
- `download.pause` / `download.resume` / `download.cancel` `{download_id}` → control downloads
- `download.erase` `{download_id, delete_file}` → remove a record from the download list (**irreversible**; `delete_file=true` also deletes the file from disk)
- `download.open` `{download_id}` → open the downloaded file with the system default program

#### Top Sites / Reading List Actions (require `topSites` / `readingList` permissions)

- `topsite.list` → most visited sites
- `readinglist.list` / `readinglist.add` `{url, title, has_been_read}` / `readinglist.remove` `{url}` / `readinglist.update` `{url, has_been_read, title}`

#### Context Menu / Alarm / Notification Actions (require `contextMenus` / `alarms` / `notifications` permissions)

- `contextmenu.create` `{menu_id, title, contexts, url_patterns}` / `contextmenu.remove` `{menu_id}` / `contextmenu.remove_all` / `contextmenu.list`
- `alarm.create` `{name, delay_minutes, period_minutes}` / `alarm.list` / `alarm.clear` `{name}` / `alarm.clear_all`
- `notification.create` `{notification_id, title, message, icon_url}` / `notification.clear` `{notification_id}` / `notification.clear_all` / `notification.list`

#### Search / Idle / Icon / Frame / Tab-group Actions

- `search.query` `{query, tab_id, disposition}` → search with the browser's default search engine (requires `search` permission)
- `idle.query_state` `{detection_interval_seconds}` / `idle.set_interval` `{detection_interval_seconds}` / `idle.get_interval` (requires `idle` permission)
- `favicon.get_url` `{page_url, size}` → site icon URL (requires `favicon` permission)
- `webnav.get_all_frames` `{tab_id}` / `webnav.get_frame` `{tab_id, frame_id}` (requires `webNavigation` permission)
- `tabgroup.list` / `tabgroup.get` `{group_id}` / `tabgroup.query` `{title, color, window_id}` / `tabgroup.update` `{group_id, title, color, collapsed}` (requires `tabGroups` permission)

#### Highly Sensitive Actions (require the corresponding high-sensitivity permission; must confirm with the user before calling)

**Cookie Actions (require `cookies` permission)**

- `cookie.get` `{url, name}` / `cookie.get_all` `{url, domain}` → read cookies (**including login credentials**)
- `cookie.set` `{url, name, value, domain, path, secure, http_only, same_site, expiration_date}` → write/modify cookies
- `cookie.remove` `{url, name}` → delete cookies

**Network Request Rule Actions (require `webRequest` permission; implemented on top of `declarativeNetRequest`)**

- `netrule.list` → list registered rules
- `netrule.register` `{rule_id, url_filter, action_type, redirect_url, priority}` → register a rule; can block or redirect requests
- `netrule.unregister` `{rule_id}` → unregister a rule

> Under MV3, `chrome.webRequest` can only observe, not block; therefore blocking/redirect is implemented
> via `declarativeNetRequest`, while the `webRequest` permission is kept for observation and compatibility.

**Extension & App Management Actions (require `management` permission)**

- `extmgr.list` / `extmgr.get` `{extension_id}` → list/query installed extensions and apps
- `extmgr.launch_app` `{extension_id}` → launch an installed app
- `extmgr.set_enabled` `{extension_id, enabled}` → enable/disable an extension
- `extmgr.uninstall` `{extension_id}` → uninstall an extension (**irreversible**)

**Native Messaging Actions (require `nativeMessaging` permission)**

- `native.send` `{native_host, message}` → send a message to a registered native messaging host

**Proxy Actions (require `proxy` permission)**

- `proxy.get_settings` → read proxy configuration
- `proxy.set_settings` `{mode, pac_url, rules}` → set proxy (**affects all network traffic**)
- `proxy.clear_settings` → clear proxy configuration

**Privacy Settings Actions (require `privacy` permission)**

- `privacy.get` `{area, name}` / `privacy.set` `{area, name, value}` (`area` ∈ network/services/websites)

**Browsing Data Actions (require `browsingData` permission)**

- `browsingdata.settings` → query which data types can be cleared
- `browsingdata.remove` `{data_types, since}` → clear browsing data (**irreversible**; may include history/cookies/cache/passwords)

**Content Settings Actions (require `contentSettings` permission)**

- `contentsettings.get` `{content_type, primary_url, secondary_url}` / `contentsettings.set` `{content_type, setting, primary_pattern, secondary_pattern}` / `contentsettings.clear` `{content_type}`

### 4.4 Error Codes

| code                | meaning                                       |
| ------------------- | --------------------------------------------- |
| `NO_SESSION`        | session does not exist or is disconnected     |
| `NO_TAB`            | tab does not exist                            |
| `ELEMENT_NOT_FOUND` | selector did not match                        |
| `TIMEOUT`           | execution timed out                           |
| `PROTECTED_PAGE`    | target is a protected page and cannot be operated |
| `EXEC_ERROR`        | exception during page script execution        |
| `NOT_SUPPORTED`     | the current browser does not support this API |

---

## 5. Key Flows

### 5.1 Connection Establishment

```text
Extension starts → read config (gateway address/token) → connect to /api/browser-ext/ws
        → gateway validates token → register session → reply hello_ack(session_id)
        → extension sends hello (tab snapshot) → ready
```

### 5.2 Agent Operating a Web Page

```text
Agent → browser_ext_click(session_id, tab_id, "#submit")
      → BrowserExtensionManager.send_command(...)
      → send over WS {action:"dom.click", params:{...}}
      → extension background receives it → locate tab → inject/call content script to execute
      → reply {type:"result", success:true}
      → Manager matches id → return result to Agent
```

### 5.3 Disconnection Handling

- Extension side: reconnect with exponential backoff; after reconnecting, send `hello` again, and the gateway reuses or creates the session by `client_id`.
- Gateway side: clean up sessions on heartbeat timeout (60s); fail in-flight commands with `NO_SESSION`.

#### 5.3.1 Auth Failure (4401/4403) Self-Healing

**Background**: when the gateway has no `HAIJUNBOT_JWT_SECRET` set, the signing key is randomly generated at each startup
(`src/haijunbot/haijunbot_web_gateway/jwt_utils.py`). After a gateway restart, the old JWT cached in the browser page
`localStorage` is immediately invalid; if the extension keeps reconnecting with the old token, the gateway closes it
with `4401 Unauthorized`, leading to a permanent "disconnect–reconnect" loop.

**Extension-side self-healing flow** (does not depend on gateway-side changes):

```text
ws.onclose(code=4401/4403) → do not retry with exponential backoff
  → handleAuthError(gateway)
      1. tokens.delete(gatewayKey)          # clear cached invalid token
      2. close and remove the old WsClient  # avoid reusing an invalid token
      3. setState(disconnected)             # popup shows disconnected
      4. requestTokenFromPages(gateway)     # re-detect the page login state
         ├─ token found → tokens.set → connect(force=true) to reconnect
         └─ not found  → stop reconnecting and prompt the user to log in to HaijunBot again
```

**Loop prevention**: after consecutive auth failures for the same gateway exceed `AUTH_ERROR_MAX_RETRIES` (3), auto-reconnect stops;
the counter resets on `hello_ack` (successful handshake), manual "Connect" (`connect(force=true)`), or `disconnect()`.

**Refresh the token on disconnect**: `disconnect()` first clears the token cache for that gateway (so the next connection
does not reuse a possibly-invalid old token), then asynchronously re-probes the page login state and writes it back to the cache;
probing itself does not establish a connection — the real link is created only when the user clicks "Connect". When removing a gateway
(`haijunbot_remove_gateway`), call `disconnect(g, true)` to skip probing, avoiding writing back a token for a removed gateway.

**Known limitation**: if the token cached by the page itself is also invalid (the user has not logged in again), the extension cannot obtain
a valid token out of thin air; it can only stop reconnecting and prompt the user to **log in to the HaijunBot page once more**.

---

## 6. Security Design

| Risk                          | Countermeasure                                                             |
| ----------------------------- | -------------------------------------------------------------------------- |
| Unauthorized browser control  | Extension requires manual install + explicit `<all_urls>` authorization; connection requires a valid gateway token |
| Token leakage                | Reuse the gateway token system; recommend wss encryption; store the token only in `chrome.storage.local` |
| Malicious commands (e.g. cookie theft) | Action whitelist (only the actions in the table above); log the entire connection and commands |
| Accidental operations on real pages | **Second confirmation for high-risk actions**: confirmation lives in the extension popup (see strategy below) |
| Multi-user privilege escalation | Sessions are bound to `user_id`; `list_sessions` returns only the user's own sessions; admins can see all |
| Missing audit                 | All commands and results are logged (including `user_id`, `session_id`, `action`, timestamp) |

**Security policy (confirmed)**:

- `script.execute` is **open by default**, no per-use enabling required.
- **Second confirmation for high-risk actions**: actions that could have irreversible consequences (e.g. form submission, deletion, payment-type clicks) trigger a confirmation in the **extension popup**; the action executes only after the user approves.
- The confirmation UI lives **on the extension side**, not passing through the HaijunBot frontend — ensuring the user sees and decides directly in their own browser.
- In multi-user scenarios, **one user may have multiple browser sessions online simultaneously**, each with its own independent `session_id`.

---

## 7. Phased Implementation

### Phase 1: Minimal Loop (MVP)

- Extension: connection, `tab.list`, `page.navigate`, `dom.get_text`, `dom.click`, `dom.type`, `capture.screenshot`
- Gateway: `/api/browser-ext/ws` endpoint + `BrowserExtensionManager` (registry/routing/return)
- Tools: `browser_ext_list_sessions` / `list_tabs` / `navigate` / `get_text` / `click` / `type` / `screenshot`
- Validation: the Agent can open a specified page, read content, click buttons, and type text

### Phase 2: Capability Enhancement

- `script.execute` (arbitrary JS, open by default)
- `dom.wait_for`, `dom.select`, `dom.hover`
- Tab event reporting (`event`)
- Second confirmation for high-risk actions (extension popup)
- Audit logs

### Phase 3: Advanced Capabilities (optional)

- `chrome.debugger` (CDP): real mouse trajectories, network interception, cross-origin iframes
- Multiple browser / multiple window session management (parallel sessions for one user)
- Operation recording and replay

---

## 8. Risks and Limitations

1. **Protected pages cannot be operated**: `chrome://*`, extension store, other extension pages, and some PDF viewers.
2. **Cross-origin iframes are limited**: under the same-origin policy, content scripts cannot directly enter cross-origin iframes (requires `all_frames` + `match_about_blank`, or CDP).
3. **Page CSP / sandbox**: `chrome.scripting` via extension privileges can usually bypass the page CSP, but some strongly sandboxed pages may still fail.
4. **Manifest V3 service worker lifecycle**: the SW can be suspended by the browser; use `chrome.alarms` or keep the WS connection alive to stay active (the WS connection itself can extend the lifecycle, but that is not an absolute guarantee).
5. **Browser compatibility**: Chrome/Edge share the same origin (Chromium) and work; Firefox requires adapting `browser.*` APIs and manifest differences.
6. **User authorization cannot be bypassed**: manual installation is required; silent deployment is impossible.

---

## 9. Design Decisions (Confirmed)

| #   | Question                       | Decision                                      |
| --- | ------------------------------ | --------------------------------------------- |
| 1   | Permission granularity         | **No permission control**; no `browser:*` resources introduced |
| 2   | Is `script.execute` open by default | **Open by default**                       |
| 3   | Where the high-risk second confirmation lives | **Extension popup**             |
| 4   | One user with multiple browser sessions | **Allowed**, each with its own independent `session_id` |
| 5   | Extension distribution method  | **Load as unpacked (developer mode)** (not published to the store) |

### Distribution Notes (Developer Mode)

- The extension ships as source code in the repository (the `browser_extension/` directory); users install it via `chrome://extensions` → enable "Developer mode" → "Load unpacked".
- No store review needed, enabling rapid iteration.
- Cost: users must operate manually; Chrome may show a "Disable developer mode extensions" prompt at startup, which is expected behavior.

---

## 10. Appendix: List of Files Changed

| Location                                                      | Change                                                                       |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `src/haijunbot/haijunbot_web_gateway/browser_extension_manager.py` | **New**: connection management, command routing, result return                |
| `src/haijunbot/haijunbot_web_gateway/app.py`                       | **New** `/api/browser-ext/ws` endpoint; initialize `browser_extension_manager` |
| `src/haijunbot/haijunbot_tools/browser_ext.py`                     | **New**: Agent toolset                                                        |
| `src/haijunbot/haijunbot_tools/registry.py`                        | **No change needed**: `register_tool_by_file` auto-scans `haijunbot_tools/*.py`  |
| `browser_extension/` (new directory)                         | **New**: Chrome extension project (loaded in developer mode)                  |

> Permission-related files (`permission_manager.py`, `AdminPanel.vue`) are **not changed** — this plan does no permission control.

---

## 11. Phase 1 Implementation Notes (MVP)

> This section records the **actual landing** of the Phase 1 MVP; where it differs from the design above, this section prevails.

### 11.1 Deliverables

#### Gateway Side (Python)

| File                                                          | Description                                                            |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `src/haijunbot/haijunbot_web_gateway/browser_extension_manager.py` | New: `BrowserExtensionManager` singleton, connection management / command routing / result return |
| `src/haijunbot/haijunbot_web_gateway/app.py`                       | New: WS endpoint `/api/browser-ext/ws`; HTTP API `/api/browser-ext/*`  |
| `src/haijunbot/haijunbot_tools/browser_ext.py`                     | New: Agent tool `browser_ext` (single tool + `action` parameter pattern) |

#### Extension Side (Chrome MV3)

| File                                                          | Description                                        |
| ------------------------------------------------------------- | -------------------------------------------------- |
| `browser_extension/manifest.json`                            | MV3 config, `background.type: module`              |
| `browser_extension/background/ws_client.js`                  | WebSocket connection, heartbeat (20s), exponential-backoff reconnect |
| `browser_extension/background/command_router.js`             | `action` → executor mapping table                  |
| `browser_extension/background/service_worker.js`             | Entry: connection orchestration, hello handshake, status broadcast |
| `browser_extension/background/executors/tab_executor.js`     | tabs / navigation                                 |
| `browser_extension/background/executors/dom_executor.js`     | DOM read/write                                    |
| `browser_extension/background/executors/capture_executor.js` | screenshot                                        |
| `browser_extension/background/executors/debug_executor.js`   | debugging: console logs, CDP evaluation, network request collection |
| `browser_extension/content/content_script.js`                | supplementary in-page script                      |
| `browser_extension/popup/popup.html` / `popup.js`            | connection config / status / high-risk-confirmation UI placeholder |
| `browser_extension/README.md`                                | installation and usage notes                      |

### 11.2 Gateway Interfaces

#### WebSocket

- Path: `/api/browser-ext/ws`
- Auth: reuse `_extract_auth_from_headers`, extract `haijunbot-token.<token>` from `sec-websocket-protocol`, then validate via `gateway._check_auth`
- Auth failure: after `accept(subprotocol="haijunbot-ext")`, send an error frame and `close(4401)`

**HTTP API** (all require `Depends(verify_token)`)

| Method   | Path                        | Description                            |
| -------- | --------------------------- | -------------------------------------- |
| `GET`    | `/api/browser-ext/sessions` | List currently online sessions         |
| `POST`   | `/api/browser-ext/command`  | Dispatch a command to a session and wait for the result |

### 11.3 Agent Tool `browser_ext`

- Class name `BrowserExtTool`, `name = "browser_ext"` (consistent with the filename, satisfying the `register_tool_by_file` requirement)
- `check()`: available when `jglobals.agent_id is not None`
- The tool runs in the Agent subprocess and **accesses the gateway over HTTP**, without directly touching gateway in-memory objects
- Mapping between tool actions and extension actions:

| Tool action           | Extension action         | Required parameters                          |
| --------------------- | ------------------------ | -------------------------------------------- |
| `list_sessions`       | (queried directly over HTTP) | None                                    |
| `list_tabs`           | `tab.list`               | `session_id`                                 |
| `navigate`            | `page.navigate`          | `session_id`, `url`                          |
| `get_text`            | `dom.get_text`           | `session_id`, `selector`                     |
| `click`               | `dom.click`              | `session_id`, `selector`                     |
| `type`                | `dom.type`               | `session_id`, `selector`, `text`             |
| `screenshot`          | `capture.screenshot`     | `session_id`                                 |
| `activate_tab`        | `tab.activate`           | `session_id`, `tab_id`                       |
| `close_tab`           | `tab.close`              | `session_id`, `tab_id`                       |
| `new_tab`             | `tab.create`             | `session_id`                                 |
| `reload`              | `page.reload`            | `session_id`                                 |
| `back`                | `page.back`              | `session_id`                                 |
| `forward`             | `page.forward`           | `session_id`                                 |
| `query`               | `dom.query`              | `session_id`, `selector`                     |
| `get_html`            | `dom.get_html`           | `session_id`, `selector`                     |
| `hover`               | `dom.hover`              | `session_id`, `selector`                     |
| `select`              | `dom.select`             | `session_id`, `selector`, `value`            |
| `wait_for`            | `dom.wait_for`           | `session_id`, `selector`                     |
| `press_key`           | `dom.press_key`          | `session_id`, `key`                          |
| `scroll`              | `dom.scroll`             | `session_id` (selector or x/y — at least one)|
| `execute_script`      | `script.execute`         | `session_id`, `code`                         |
| `upload_file`         | `dom.upload_file`        | `session_id`, `selector`, `file_path`        |
| `get_computed_style`  | `dom.get_computed_style` | `session_id`, `selector`                     |
| `get_page_info`       | `page.get_info`          | `session_id`                                 |
| `get_console_logs`    | `console.get_logs`       | `session_id`                                 |
| `evaluate`            | `debugger.evaluate`      | `session_id`, `expression`                   |
| `get_network_requests`| `network.get_requests`   | `session_id`                                 |

- Returns a unified envelope: `{"success": bool, "stdout": str, "stderr": str}`
- The screenshot base64 is written to a temp PNG on the tool side (`/tmp/haijunbot_browser_ext_<ts>.png`);
  `stdout` only returns `{path, width, height, full_page, bytes}` to avoid oversized base64 blowing up the context

### 11.4 Browser Debugging Capabilities (F12-equivalent)

Phase 2 adds 5 debug actions covering the main F12 panels:

| F12 panel      | Corresponding action       | Implementation                                                                                          |
| -------------- | -------------------------- | ------------------------------------------------------------------------------------------------------- |
| Console        | `console.get_logs`         | Hook `console.*` + `window.onerror` + `unhandledrejection` in the MAIN world, ring buffer of 500        |
| Computed       | `dom.get_computed_style`   | `getComputedStyle(el).getPropertyValue(prop)`, 22 common properties by default                          |
| Overview       | `page.get_info`            | Read `location` / `document` / `innerWidth` / `scrollX` etc. via injection                              |
| Console eval   | `debugger.evaluate`        | CDP `Runtime.evaluate` (`allowUnsafeEvalBlockedByCSP: true`), **not subject to page CSP**                |
| Network        | `network.get_requests`     | CDP `Network` domain event collection (`requestWillBeSent` / `responseReceived` / `loadingFinished` / `loadingFailed`) |

**Key technical points**:

1. **The console hook must be injected into the MAIN world** — the ISOLATED world sees a different `console` object and cannot hook the page's own calls.
2. **The hook is idempotent** — use a `window.__haijunbotConsoleHooked` flag to avoid double-wrapping on repeated injection; `console.get_logs` attempts to install the hook on every call.
3. **CDP is not subject to page CSP** — `script.execute` (`new Function`) can still fail on strict-CSP sites, while `debugger.evaluate` completely bypasses it via CDP.
4. **Debugger attach is reused** — `_attach()` first checks `chrome.debugger.getTargets()`; if already attached, reuse the attachment (no detach), avoiding seizing a DevTools connection the user already has open.
5. **Network collection is an async window** — `network.get_requests` blocks for `duration_ms` (default 3000ms) of collection; the tool layer automatically relaxes its HTTP timeout (`duration_ms/1000 + 5s`).
6. **The `debugger` permission is already declared in the manifest**; no new permission is needed.

**Known limitations**:

- If the user already has DevTools debugging the same tab, `chrome.debugger.attach` fails (returns `EXEC_ERROR`).
- `network.get_requests` can only collect requests occurring during the call; past requests cannot be retrospected.
- `console.get_logs` can only collect logs after the hook is installed; early page logs cannot be retrospected.

### 11.5 Installation and Usage Steps

1. **Start the gateway** (must include `--master-url` for the Agent tools to access)
2. **Install the extension**: `chrome://extensions` → enable "Developer mode" → "Load unpacked" → select the `browser_extension/` directory in the repository
3. **Log in to the HaijunBot web page**: the extension automatically reuses the page login state (no need to manually fill in a Token; see 11.8)
4. **Configure the connection**: click the extension icon, fill in the gateway address (e.g. `https://hjb-ai.cn`), click "Connect"
5. **Verify connectivity**: once the status shows "Connected", call `browser_ext`'s `list_sessions` in an Agent session; it should return the session's `session_id`
6. **Perform operations**: after `list_tabs` returns a `tab_id`, run `navigate` / `get_text` / `click` / `type` / `screenshot`

### 11.5 Phase 1 Validation Results

Static and mock validation completed:

- Python: `ast.parse` all passed, `ruff check` all passed
- JavaScript: all 8 `.js` files passed `node --check` (ESM mode)
- `manifest.json`: validated with `python -m json.tool`
- Tool registration: `BrowserExtTool` has `name`/`description`/`parameters`/`execute`, and `name` matches the filename
- Endpoints exist: `/api/browser-ext/ws`, `/api/browser-ext/sessions`, `/api/browser-ext/command` are all defined
- Mock end-to-end: all 7 actions returned success; all 4 error paths (unknown action, missing `session_id`, missing `url`, empty action) produced correct errors
- Docs: `markdownlint` passed

**Not yet validated (constrained by the "no gateway restart" rule; requires the user to operate)**:

- The real WS handshake between gateway and extension
- Command round-trip and result return in a real browser

### 11.6 Phase 1 Known Simplifications

1. The high-risk-action second confirmation in the popup is only a UI placeholder; the background has not yet issued a real confirmation request (by design, this belongs to Phase 2)
2. The `browser_extension/icons/` directory was not created; `icons` in `manifest.json` is an empty object, which does not affect developer-mode loading
3. `content_scripts` has `all_frames: false`; element operations inside iframes are not yet supported

### 11.7 Phase 2 To-Do

- Expose the `script.execute` tool
- Toolify `dom.wait_for` / `dom.hover` / `dom.select`
- Real high-risk-action interception (wire the popup second confirmation into the background)
- Operation audit logs

### 11.8 Login State Reuse (Option B2)

#### 11.8.1 Problem

Phase 1 originally required the user to manually fill in the gateway Token (`HAIJUNBOT_AUTH_TOKEN`) in the popup. But the user cannot obtain that Token themselves:

- The gateway Token lives in the gateway process's environment variables — invisible to the user
- The JWT Token lives in the frontend's `localStorage['haijunbot_auth_token']`, and is **written only when the user enables the "login-free" switch** (otherwise it exists only in Vue memory)

So "filling in the Token manually" is not feasible for ordinary users.

#### 11.8.2 Option Selection

| Option                        | Description                                                 | Conclusion                                          |
| ----------------------------- | ----------------------------------------------------------- | --------------------------------------------------- |
| A. Independent login inside the extension | popup asks for account/password, extension calls `/api/auth/login` itself | Rejected: the user must log in twice, and the extension's login state may differ from the page's |
| B1. `externally_connectable`  | the page talks directly to the extension via `chrome.runtime.sendMessage` | Requires a fixed extension ID (`key` in the manifest), larger change |
| **B2. content script bridging** | the content script injects a main-world script that reads the token exposed by the page | **Adopted**: zero user effort, no fixed extension ID, no changes to frontend login logic |

#### 11.8.3 Implementation

**Frontend (`App.vue`)**: expose a read-only interface + broadcast token changes

```js
window.__haijunbotAuthBridge = {
  getToken: () => auth.value.token || null,
};
watch(
  () => auth.value.token,
  (newToken) => {
    window.postMessage(
      { type: "haijunbot_token_changed", token: newToken || null },
      "*",
    );
  },
);
```

Using `watch` uniformly covers every token-change point (login success, login-free restore, 401 invalidation, logout) without modifying each one.

**content script (`content_script.js`)**: inject the bridge into the main world

The content script runs in the isolated world and cannot access the page's JS variables, so it injects a main-world script:

- The main-world script calls `window.__haijunbotAuthBridge.getToken()` to read the token
- It communicates with the isolated world via `window.postMessage` (both directions validate `event.source === window`)
- The isolated world forwards the token to the background (`chrome.runtime.sendMessage`)
- Two trigger modes: the page proactively broadcasts `haijunbot_token_changed`; the background proactively requests via `haijunbot_request_token`

**background (`service_worker.js`)**: token-driven connection

- On `haijunbot_ext_token` / `haijunbot_ext_token_changed` → call `handleAuthToken`
- Token change → reconnect; token empty → disconnect
- On cold start with no token yet, proactively send `haijunbot_request_token` to all tabs to request one
- `haijunbot_get_status` adds a `has_token` field so the popup can show the login state

**popup**: remove the Token input box; show the login state instead (obtained / not obtained)

#### 11.8.4 Key Benefits

- **Identity is naturally consistent**: the token the extension uses is the token of the page's logged-in user — there is no "extension account differs from web account" problem
- **Zero configuration**: the user only logs into the HaijunBot web page; the extension follows automatically
- **Automatically tracks changes**: on account switch / logout / token expiry, the extension automatically reconnects or disconnects

#### 11.8.5 Known Trade-offs

The frontend exposes the token via `window.__haijunbotAuthBridge`, so **scripts on the same page could theoretically read it**. The current version accepts this risk in exchange for a zero-configuration experience. If strong isolation is needed later, upgrade to B1 (`externally_connectable` + fixed extension ID), after which only the designated extension can obtain the token.

### 11.9 Multi-Gateway Parallel Connections (Option B)

#### 11.9.1 Problem

Phase 1's extension supported only a single gateway (flat `gateway` / `token` / `session_id` keys in `chrome.storage.local`). But in practice users often need to connect to multiple HaijunBot gateways simultaneously (e.g. a local dev gateway + a production gateway). Under the single-gateway model, switching gateways requires repeatedly changing the config and reconnecting.

#### 11.9.2 Option Selection

| Option              | Description                                    | Conclusion                                       |
| ------------------- | ---------------------------------------------- | ------------------------------------------------ |
| A. Independent login inside the extension | the extension maintains its own account/password login, decoupled from the page login | Rejected: the user must log in twice, conflicting with B2's zero-configuration goal |
| B. Multi-gateway parallel connections | the same extension maintains multiple gateway connections at once, each independent | **Adopted**                                     |
| C. Single gateway + quick switch | keep one connection, popup offers switching  | Rejected: no parallelism, the Agent side would need repeated switching |

Chose B. Core judgment: **the gateway side needs no changes at all** — each gateway is an independent process, each maintaining its own `browser_extension_manager._sessions`; connecting to A registers with A, connecting to B registers with B, naturally isolated.

#### 11.9.3 Implementation

**service_worker.js**: change the singleton state into four `Map`s indexed by gateway:

```js
const clients = new Map(); // gateway -> WsClient
const tokens = new Map(); // gateway -> token
const sessions = new Map(); // gateway -> session_id
const states = new Map(); // gateway -> 'disconnected' | 'connecting' | 'connected'
```

- `normalizeGateway()`: normalize the gateway address (prepend `http://` if no protocol, strip trailing slash), used as the `Map` key
- `connect(gateway)`: create an independent `WsClient` instance per gateway, with `onMessage` closure bound to that gateway
- `handleMessage(gateway, msg)`: command results are only returned to `clients.get(gateway)`; no cross-gateway mixing
- `requestTokenFromPages(gateway)`: only accept responses whose `resp.gateway` matches the target gateway
- `handleAuthToken(gateway, token)`: reconnect/disconnect independently per gateway
- `listStatus()`: aggregate all gateway states; `haijunbot_get_status` returns `{ gateways: [...] }`
- New message type `haijunbot_remove_gateway`; `haijunbot_connect` / `haijunbot_disconnect` support a `gateway` parameter (disconnect without a parameter disconnects all)
- `connectAll()`: on cold start, iterate `chrome.storage.local.gateways` and connect one by one

**content_script.js**: both the main-world response and the isolated-world forwarding carry `gateway: location.origin`, so each token can be attributed to the correct gateway.

**popup**: becomes a gateway-list UI — the top input is for adding a gateway; the list area shows each gateway's address / connection status / login state / `session_id`, with "Connect / Disconnect / Remove" buttons per item.

**storage structure change**: flat `gateway` / `token` / `session_id` keys → `gateways: string[]` (storing only the address list; tokens move to in-memory `Map`s and are no longer persisted to storage — a security improvement).

**CommandRouter reuse**: executors are stateless and operate on the global `chrome.tabs`, independent of gateway, so all gateways share the same router instance.

#### 11.9.4 Key Trade-offs

**All gateways share the same set of browser tabs.** `chrome.tabs` is global to the browser; the extension architecture cannot isolate tabs per gateway. Isolating them would require users to manually use different browser windows/profiles, which is unrealistic. Therefore, when multiple Agents operate concurrently, they may affect the same page — concurrent operations on the same tab should be avoided.

#### 11.9.5 Compatibility

The single-gateway behavior is unchanged: adding just one gateway behaves exactly like Phase 1 (connection, status display, and login-state reuse are identical), except the UI changes from a "status area" to a "single list item".

### 11.10 Capability Fill-in (Second Round)

On top of Phase 1's 17 actions, 5 capability gaps are filled; the extension actions grow to 21, with a one-to-one mapping to tools.

#### 11.10.1 New Actions

| Extension action                  | Tool action                  | Description                                                                                             |
| --------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------- |
| `dom.press_key`                   | `press_key`                  | Dispatch `keydown`/`keypress`/`keyup` including a `keyCode`/`which` compatibility table; on `Enter`, try `form.requestSubmit()` |
| `dom.scroll`                      | `scroll`                     | If a `selector` is given, `scrollIntoView`; otherwise `window.scrollBy(x, y)`; returns scroll position and page size |
| `script.execute`                  | `execute_script`             | `new Function`: first evaluate as an expression, fall back to statement execution on failure; results go through `safeSerialize` |
| `dom.upload_file`                 | `upload_file`                | Use `chrome.debugger`'s `DOM.setFileInputFiles` to set the real local file path                          |
| `capture.screenshot` (`full_page`)| `screenshot` (`full_page`)   | Scrolling screenshot per screen + `OffscreenCanvas` stitching for a true full-page screenshot            |

#### 11.10.2 Screenshot-to-Disk Refactor

The original implementation stuffed base64 directly into `stdout`, which the Agent could not actually use. Now changed to:

- The extension returns `{image, width, height, full_page}` (full page) or a base64 string (viewport)
- The tool-side `_screenshot_to_file()` decodes the base64 and writes `/tmp/haijunbot_browser_ext_<ts>.png`
- `stdout` only returns `{path, width, height, full_page, bytes}`

#### 11.10.3 File Upload Technical Constraints

The extension runs in a sandbox and **cannot directly read local file contents**. The only way to genuinely upload a local file is
`chrome.debugger` + `DOM.setFileInputFiles` (passing the file path, which the browser process reads).
Therefore `manifest.json` adds the `debugger` permission. Cost: while a debugger is attached, the browser shows a "is being debugged by this browser" banner;
if the tab is already occupied by DevTools, the attach fails.

#### 11.10.4 Validation Results

- The extension action registration set (21) and the tool `_send_command` mapping set (21) have **zero difference**
- All `.js` passed `node --check`; `manifest.json` is valid JSON
- Python `ast.parse` + `ruff check` passed
- Mock tests: the normal paths and error paths (missing required params) of the 4 new actions all behaved as expected; screenshot-to-disk path and dimensions are correct
- Regression: the mapping behavior of the original 15 actions is unchanged