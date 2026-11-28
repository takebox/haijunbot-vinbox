# HaijunBot Browser Bridge

Allows HaijunBot Agent to operate web pages in the user's **real browser** (reusing login sessions and Cookies).

Unlike `haijunbot-browser` (`hb`, where the server-side Playwright launches a separate browser), this extension runs inside the user's browser,
actively connecting out to the HaijunBot gateway via WebSocket, so no public IP or open ports are needed.

## Installation (Developer Mode)

1. Open Chrome/Edge and navigate to `chrome://extensions`
2. Enable "Developer mode" in the top-right corner
3. Click "Load unpacked extension" and select this directory (`browser_extension/`)
4. Log in to the HaijunBot web page in the browser (the extension automatically reuses its login session; **no need to manually fill in a Token**)
5. Click the extension icon in the toolbar and fill in "Add gateway address":
   - **Gateway address**: e.g. `https://hjb-ai.cn` or `http://127.0.0.1:8000`
6. Click "Add and Connect"; when the gateway status shows "Connected" in the list, it succeeded
7. To connect multiple gateways, repeat steps 5~6 (each gateway has an independent connection and session)

## Login Session Reuse Mechanism

The extension does not require the user to log in separately or manually fill in a Token; instead, it **automatically reuses the login session from the HaijunBot web page already logged into in the browser**:

```text
HaijunBot web page (logged in)
  |  window.__haijunbotAuthBridge.getToken()  <- read-only interface exposed by front-end
  |  window.postMessage('haijunbot_token_changed')  <- Token change broadcast
  v
content_script.js (isolated world)
  |  Inject main world script to read Token, forward to background
  v
service_worker.js
  |  Token change -> reconnect; Token empty (not logged in/logged out) -> disconnect
  v
Gateway WebSocket (carrying haijunbot-token.<token> subprotocol)
```

Key points:

- **Naturally consistent identity**: the Token used by the extension is the same as the web page login user's Token; there is no "extension account vs web account mismatch" problem
- **Automatic Token change tracking**: when the user switches accounts or logs out on the web page, the extension automatically reconnects or disconnects
- **Automatic acquisition on cold start**: the extension actively requests a Token from already-open HaijunBot pages on startup
- The front-end must expose `window.__haijunbotAuthBridge.getToken()` (see the "Browser Extension Login Session Bridge" section in `App.vue`)

## Multi-Gateway Support

The same browser can **connect to multiple HaijunBot gateways simultaneously** (e.g. local `http://127.0.0.1:8000` and production `https://hjb-ai.cn`):

- Each gateway maintains an independent WebSocket connection, independent `session_id`, and independent login session Token
- The popup lists all added gateways; you can "Connect / Disconnect / Remove" individual gateways
- Gateway list is persisted in `chrome.storage.local.gateways`; Token is only stored in memory, not on disk
- Auto-reconnect for all configured gateways on cold start (extension start / browser start)

**Trade-off: all gateways share the same set of browser tabs.** The extension's `chrome.tabs` is browser-global,
so tabs cannot be isolated per gateway; isolation would require the user to manually use different browser windows/profiles, which is impractical.
Therefore, when multiple Agents operate simultaneously, they may affect the same set of tabs; avoid concurrent operations on the same page.

## Directory Structure

```text
browser_extension/
|-- manifest.json                  # Manifest V3 configuration
|-- background/
|   |-- service_worker.js          # Entry point: connection management + command dispatch + login session reception + script management forwarding
|   |-- ws_client.js               # WebSocket connection, heartbeat, reconnection
|   |-- command_router.js          # action -> executor mapping
|   |-- script_manager.js          # Script repository (Tampermonkey-like): install / list / enable-disable / uninstall
|   +-- executors/
|       |-- tab_executor.js        # Tabs / navigation
|       |-- dom_executor.js        # DOM read/write (executeScript injection)
|       |-- script_executor.js     # Custom script execution (main world injection)
|       |-- clipboard_executor.js  # Read gateway static files / write front-end clipboard
|       |-- capture_executor.js    # Screenshots
|       |-- bookmarks_executor.js  # Bookmarks (read / search / add-remove)
|       |-- history_executor.js    # History (query / delete)
|       |-- downloads_executor.js  # Downloads (list / search / control)
|       |-- sessions_executor.js   # Recently closed sessions (query / restore)
|       |-- top_sites_executor.js  # Frequently visited sites
|       |-- reading_list_executor.js  # Reading list
|       |-- context_menus_executor.js # Extension right-click menus
|       |-- alarms_executor.js     # Timers
|       |-- notifications_executor.js # System notifications
|       |-- search_executor.js     # Default search engine queries
|       |-- idle_executor.js       # Idle state detection
|       |-- favicon_executor.js    # Site favicon URL
|       |-- web_navigation_executor.js # Page frame information
|       |-- tab_groups_executor.js # Tab groups
|       |-- cookies_executor.js    # Cookies (highly sensitive)
|       |-- web_request_executor.js # Network request rules (highly sensitive, declarativeNetRequest)
|       |-- management_executor.js # Extension and app management (highly sensitive)
|       |-- native_messaging_executor.js # Native app messaging (highly sensitive)
|       |-- proxy_executor.js      # Proxy settings (highly sensitive)
|       |-- privacy_executor.js    # Privacy settings (highly sensitive)
|       |-- browsing_data_executor.js # Browsing data clearing (highly sensitive, irreversible)
|       +-- content_settings_executor.js # Site content settings (highly sensitive)
|-- content/
|   +-- content_script.js          # In-page script: login session bridging + page metadata
+-- popup/
    |-- popup.html                 # Connection config / status / high-risk confirmation / script management UI
    +-- popup.js
```

## Script Management (Tampermonkey-like)

The extension has a built-in **script repository**: users can install custom page scripts, and the Agent queries and invokes them via `script.*` commands.
Ideal for encapsulating "site-specific operations" into reusable capabilities (e.g. editor read/write for an online document site).

### Script Format

A script is a piece of JS that is evaluated in the **page's main world** and should export the following object:

```js
globalThis.__HAIJUNBOT_SCRIPT__ = {
  name: "mysite", // Script name (unique; duplicates treated as update)
  version: "1.0.0",
  description: "Site-specific document operations",
  match: ["example.com"], // Applicable domains (hint only, no enforcement)
  actions: {
    // entry can be { desc, params, run } or directly a function
    getText: { desc: "Read full text", run: () => ({ text: window.ze.getText() }) },
    insertText: {
      desc: "Insert text at specified offset (write operation)",
      params: { offset: "number", text: "string" },
      run: ({ offset, text }) => {
        window.ze.executeCommandAndMoveCursor({
          command: "addText",
          range: { startOffset: offset, endOffset: offset },
          data: text,
        });
        return { ok: true };
      },
    },
  },
};
```

Also compatible with `module.exports = {...}` style. Installation performs **lightweight static validation** (export keyword check + bracket balance check),
so validation is a "weak guarantee" -- **only install scripts you trust**.

> Validation does **not** use `new Function` / `eval`: MV3 extension pages have CSP `script-src 'self'` (no `unsafe-eval` allowed),
> dynamic evaluation is directly rejected by the browser. Real syntax errors surface when `script.run` is evaluated in the page's main world.

### Installation and Usage

1. Open the extension popup -> "Script Management (Tampermonkey-like)"
2. Choose one of three installation methods:
   - Paste script source into the "Script Source" box -> enter script name -> click "Install Script"
   - Click "Or import from local file" to select a `.js` file
   - Enter a script URL in "Or install from URL" -> click "Install from URL" (source is downloaded by the backend and not displayed in the UI)
3. In the list, you can "Enable / Disable", "View Source", "Export", "Uninstall" each script

On the Agent side, use `script.list` to query installed scripts, then `script.run` to invoke a specific action.

### Install from URL

"Install from URL" downloads script source via **background-side `fetch`**; the popup never touches the source content.
Ideal for hosting scripts on any HTTP static directory (e.g. the gateway's `/uploads/`) and distributing by URL, avoiding transmitting large source code in conversations.

URL validation is performed by `background/url_guard.js` (anti-SSRF):

- Only `http` / `https` allowed; `file:`, `data:`, `ftp:`, etc. are rejected
- Rejects loopback and internal addresses: `127.0.0.1`, `localhost`, `10.x`, `172.16-31.x`, `192.168.x`, `169.254.x`, `::1`, `fe80::`, etc.
- Therefore **local/internal gateways cannot use URL installation**; use "Gateway Directory Relay" below instead

Script name can be derived from the last URL segment (`.../my-script.js` -> `my-script`); when it cannot be derived, you must explicitly provide a script name.
Downloaded content is only stored as a **source code string**; the extension never evaluates it in the background.

### Gateway Directory Relay

The Agent can save scripts from the extension to the gateway data directory (`{data_dir}/browser_scripts/`),
then read them back from that directory for installation, **never transmitting the original script source**:

- `script_save`: extension -> gateway directory; only returns path and byte count
- `script_load_from_file`: gateway directory -> extension; only returns installation metadata

Script names may only contain `[A-Za-z0-9_.-]`; `/`, `\`, `..`, and names starting with `.` are forbidden to prevent directory traversal.

### Export and Sharing

The "Export" button in the list exports the script as a `<name>.js` file (browser download), with a metadata comment block at the top:

```js
// ===== HaijunBot Script Export =====
// name: mysite
// version: 1.0.1
// description: Online document editor read/write operations
// match: example.com
// Install: extension popup -> "Script Management" -> paste this file content or import from local file.
// ===========================

globalThis.__HAIJUNBOT_SCRIPT__ = { ... };
```

Send this file to others; they can install it via "Import from local file" or by pasting the source, with no format conversion needed.
On the Agent side, `script.export` can also retrieve the same text content (returns `{ filename, name, version, content }`).

### Execution Mechanism and Security Notes

`script.run` injects the script source into the target tab via `chrome.scripting.executeScript({ world: "MAIN" })`
for execution in the **main world**, so the script can access the page's own JS objects (e.g. site-provided editor instances like `window.editor`).
This is equivalent to executing arbitrary JS in the page -- the security boundary relies entirely on "only installing trusted scripts".

- Scripts are **enabled** by default; after disabling, `script.run` returns `SCRIPT_DISABLED`
- Scripts are evaluated in the page's main world; they can read/write the page's DOM and JS objects and may also make network requests
- Scripts can come from manual paste/local import, or be downloaded from a URL via `script.install_from_url`;
  remote downloads are limited to http(s) and reject internal addresses; **only install scripts you trust**

## Supported Commands (action)

| Category | action                                                                                                                                                                           |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tabs     | `tab.list` `tab.activate` `tab.close` `tab.create`                                                                                                                               |
| Navigation | `page.navigate` `page.reload` `page.back` `page.forward` `page.get_info`                                                                                                         |
| DOM      | `dom.query` `dom.get_text` `dom.get_html` `dom.click` `dom.type` `dom.hover` `dom.select` `dom.wait_for` `dom.press_key` `dom.scroll` `dom.upload_file` `dom.get_computed_style` |
| Debug    | `debugger.evaluate` `debugger.send_command` `console.get_logs` `network.get_requests` (via CDP, not restricted by page CSP)                                                       |
| Script   | `script.execute` (execute arbitrary JS code, high risk)                                                                                                                          |
| Script Library | `script.list` `script.get` `script.install` `script.install_from_url` `script.uninstall` `script.export` `script.set_enabled` `script.run` (Tampermonkey-like script management) |
| Clipboard | `clipboard.write_from_url` (read URL content and write to clipboard) `clipboard.write` (directly write text/base64)                                                              |
| Bookmarks | `bookmark.list` `bookmark.search` `bookmark.create` `bookmark.remove` `bookmark.remove_tree`                                                                                     |
| History  | `history.search` `history.recent` `history.remove` `history.remove_range`                                                                                                        |
| Downloads | `download.list` `download.search` `download.start` `download.pause` `download.resume` `download.cancel` `download.erase` `download.open`                                         |
| Sessions | `session.recent` `session.restore` (recently closed tabs/windows)                                                                                                                |
| Top Sites | `topsite.list`                                                                                                                                                                   |
| Reading List | `readinglist.list` `readinglist.add` `readinglist.remove` `readinglist.update`                                                                                                   |
| Context Menus | `contextmenu.create` `contextmenu.remove` `contextmenu.remove_all` `contextmenu.list`                                                                                            |
| Alarms   | `alarm.create` `alarm.list` `alarm.clear` `alarm.clear_all`                                                                                                                      |
| Notifications | `notification.create` `notification.clear` `notification.clear_all` `notification.list`                                                                                          |
| Search   | `search.query` (search with browser default search engine)                                                                                                                       |
| Idle State | `idle.query_state` `idle.set_interval` `idle.get_interval`                                                                                                                       |
| Favicon  | `favicon.get_url`                                                                                                                                                                |
| Page Frames | `webnav.get_all_frames` `webnav.get_frame`                                                                                                                                       |
| Tab Groups | `tabgroup.list` `tabgroup.get` `tabgroup.query` `tabgroup.update`                                                                                                                |
| Capture  | `capture.screenshot` (supports `full_page` full-page screenshots)                                                                                                                |

### High-Sensitivity Commands (User Confirmation Required Before Calling)

| Category | action                                                                                                           |
| -------- | ---------------------------------------------------------------------------------------------------------------- |
| Cookies  | `cookie.get` `cookie.get_all` `cookie.set` `cookie.remove` (involves login credentials)                          |
| Network Rules | `netrule.list` `netrule.register` `netrule.unregister` (can block/redirect requests, based on `declarativeNetRequest`) |
| Extension Management | `extmgr.list` `extmgr.get` `extmgr.launch_app` `extmgr.set_enabled` `extmgr.uninstall` (`uninstall` is **irreversible**) |
| Native Messaging | `native.send` (requires registered native messaging host)                                                       |
| Proxy    | `proxy.get_settings` `proxy.set_settings` `proxy.clear_settings` (affects all network traffic)                    |
| Privacy Settings | `privacy.get` `privacy.set`                                                                                      |
| Browsing Data | `browsingdata.settings` `browsingdata.remove` (`remove` is **irreversible**; can clear history/Cookies/cache/passwords) |
| Content Settings | `contentsettings.get` `contentsettings.set` `contentsettings.clear` (site-level Cookies/JS/popups/camera permissions) |

## Clipboard (Read Gateway Static Files -> Write Front-End Clipboard)

Reads file contents from the gateway static directory (`/uploads/`) and writes them to the **front-end page's system clipboard**,
for pasting within page editors (e.g. pasting images into a rich text editor).

Read and write are performed in two separate places; this is a hard constraint of the browser:

- **Read file**: `fetch` in background (service worker), which supports cross-origin;
- **Write clipboard**: `navigator.clipboard` is unavailable in service workers; it must be injected into the **page context** for execution,
  and requires the document to actually have focus, otherwise it throws `NotAllowedError: Document is not focused`.

### `clipboard.write_from_url`

| Parameter | Required | Description                                                                               |
| --------- | ---- | ---------------------------------------------------------------------------------- |
| `url`    | Yes   | File address. Absolute URL (recommended) or `/uploads/xxx.png` relative path (completed using the first configured gateway) |
| `as`     | No   | `blob` (default, binary, suitable for images) or `text` (written as text)                            |
| `mime`   | No   | Override MIME type when `as=blob` (defaults to response `content-type`)                                 |
| `tab_id` | No   | Target tab (defaults to current active tab)                                                     |

Returns `{ ok, url, mime, size, mode }`.

> **Node topology**: the Agent may run on the master or any sub-node; **the caller** decides which address to read.
> Please pass a full absolute URL (e.g. `https://<node-gateway>/uploads/xxx.png`); the extension does not guess addresses.

### `clipboard.write`

Directly writes given content without going through the gateway: `text` (text) or `base64` + `mime` (binary).

### Prerequisite: Document Must Have Focus

`tab.activate` only activates the tab and is **not sufficient** to make the clipboard writable (`document.hasFocus()` being true may still throw an error).
Before calling, dispatch a real mouse click first (e.g. CDP `Input.dispatchMouseEvent` with `mousePressed` + `mouseReleased`).

When pasting into a page editor, use CDP to send `Ctrl+V`, and you **must use the `rawKeyDown` type** (`keyDown` does not work):

```js
{ type: "rawKeyDown", modifiers: 2, key: "v", code: "KeyV",
  windowsVirtualKeyCode: 86, nativeVirtualKeyCode: 86, text: "", unmodifiedText: "" }
```

## Message Protocol

### Gateway -> Extension (Command)

```json
{
  "id": "req-<uuid>",
  "type": "command",
  "action": "dom.click",
  "params": { "selector": "#submit", "tab_id": 123 },
  "timeout_ms": 15000
}
```

### Extension -> Gateway (Result)

```json
{
  "id": "req-<uuid>",
  "type": "result",
  "success": true,
  "data": { "ok": true },
  "error": null
}
```

**Handshake**: after connection, the extension sends `hello` (including extension version, browser info, tab snapshot); gateway replies with `hello_ack`
(including `session_id` and `latest_extension_version`).

**Heartbeat**: the extension sends `{"type":"ping"}` every 20s; gateway replies with `{"type":"pong"}`.

## Version Update Notifications

The extension **does not auto-update** (not published to the store, and MV3 does not allow modifying its own installed files), but there are two proactive notifications:

1. **Extension side**: during handshake, the gateway sends `latest_extension_version` with `hello_ack`. The extension compares it with the local version;
   if outdated, a system notification is shown once (each new version is only notified once, recorded in `chrome.storage.local`'s
   `notified_extension_version`). **You receive the notification without needing to open the HaijunBot web page.**
2. **Web page side**: checked once upon entering the lobby, then re-checked every 5 minutes; when a new version is available, the "Install Browser Extension" button
   shows a red dot, and a popup displays the version comparison.

After receiving the notification, you must **manually** re-download the extension package and reload the extension -- the browser provides no API allowing the extension
to replace its own files or auto-reload; this step cannot be automated.

## Known Limitations

1. **Protected pages cannot be operated on**: `chrome://*`, extension store, other extension pages, etc.
2. **Cross-origin iframes are restricted**: cannot directly access cross-origin iframes under the same-origin policy (`all_frames: false`)
3. **MV3 service workers may sleep**: WebSocket connections extend lifetime, but it is not an absolute guarantee
4. **High-risk action secondary confirmation not yet integrated**: the popup has UI placeholders; real interception will be added in future versions
5. **File upload depends on the `debugger` permission**: `dom.upload_file` uses `chrome.debugger`'s
   `DOM.setFileInputFiles` to set a real local file path; this is the only feasible method within the extension sandbox.
   When attaching the debugger, the browser shows a "Debugging this browser" notification bar; if the tab is already occupied by DevTools
   attachment will fail.
6. **Full-page screenshots depend on scroll-stitching**: `capture.screenshot`'s `full_page` works by scrolling and capturing screen-by-screen
   then stitching on an `OffscreenCanvas`; extremely long pages (over 50 screens) are truncated; during capture the page
   scrolls briefly and returns to the original position afterward.
7. **`script.execute` is restricted by page CSP**: some sites block `eval`/`new Function`,
   causing execution to fail in those cases.
8. **Bookmarks and history are new permissions**: `bookmark.*` / `history.*` require `bookmarks`, `history`
   permissions; after installing or updating the extension, the browser will prompt for authorization again. `bookmark.remove` /
   `bookmark.remove_tree` / `history.remove` / `history.remove_range` are **irreversible**
   deletion operations; `history.remove_range` without time parameters clears all history -- please confirm before calling.
9. **The extension requests many permissions (including high-sensitivity ones)**: to support full browser automation capabilities,
   `manifest.json` requests 28 permissions, of which 8 are high-sensitivity:
   `cookies`, `webRequest`, `management`, `nativeMessaging`, `proxy`,
   `privacy`, `browsingData`, `contentSettings`. When installing or updating the extension, the browser
   will explicitly warn "Read and change all your data on the websites you visit"; please confirm before authorizing.
   The capabilities corresponding to high-sensitivity permissions are as follows:
   - `cookies`: read/write/delete site cookies (**includes login credentials**)
   - `webRequest`: register network request rules; can block or redirect requests
   - `management`: list/enable/disable/uninstall other extensions (`uninstall` is **irreversible**)
   - `nativeMessaging`: communicate with registered native applications
   - `proxy`: modify browser global proxy settings (**affects all network traffic**)
   - `privacy`: modify privacy-related toggles
   - `browsingData`: clear browsing data (**irreversible**; includes history/Cookies/cache/passwords)
   - `contentSettings`: modify site-level content permissions (Cookies/JS/popups/camera etc.)

   > :warning: **Risk warning**: these permissions give the extension the equivalent of "full control of the browser".
   > Only use this if you trust the gateway and Agent running the extension; delete/clear operations are irreversible.
   > If you do not need these capabilities, you can remove the corresponding entries from `manifest.json`'s `permissions`
   > (after removal, the corresponding actions will return `NOT_SUPPORTED` or `unknown action`).

## Troubleshooting

### Extension Keeps "Disconnecting-Reconnecting" After Gateway Restart

**Symptom**: after restarting the main HaijunBot gateway, the gateway's status in the popup repeatedly fluctuates between "Connecting / Disconnected",
and the console continuously prints `ws closed 4401 Unauthorized`.

**Cause**: when the gateway does not set `HAIJUNBOT_JWT_SECRET`, the JWT signing key is randomly generated on each start
(`src/haijunbot/haijunbot_web_gateway/jwt_utils.py`). After a gateway restart the key changes, and the old Token cached in the browser page's
`localStorage` immediately becomes invalid; the extension reconnecting with the old Token will inevitably be rejected.

**Extension-side handling** (v1.1+): when `ws_client.js` receives `4401` (Unauthorized) / `4403` (Forbidden)
close codes, it **no longer uses exponential backoff reconnection**; instead it delegates to `service_worker.js`'s `handleAuthError()`:

1. Clear that gateway's Token cache and close the old connection;
2. Re-probe the Token from the HaijunBot page once (`requestTokenFromPages`);
3. New Token found -> auto-reconnect; not found -> stop reconnecting and prompt to re-login.

After more than 3 consecutive failures (`AUTH_ERROR_MAX_RETRIES`), auto-reconnect stops to avoid infinite futile cycles;
the counter is reset on successful handshake, or when the user manually clicks "Connect" or "Disconnect".

**Token is also refreshed on disconnect**: clicking "Disconnect" clears that gateway's Token cache and re-probes the page once
to write the login session back to cache (probing does not establish a connection). So if you have already re-logged in on the page, disconnecting and reconnecting will use the new Token;
removing a gateway does not trigger probing.

**What you need to do**: **re-login once** to the HaijunBot page for that gateway in the browser (refresh and re-login),
so the page gets a new Token; then go back to the popup and click "Connect" once.

> The root fix is to set a fixed `HAIJUNBOT_JWT_SECRET` environment variable for the gateway, so the key remains unchanged across restarts.
> The extension-side self-healing is only a mitigation; it cannot revive an already-invalid Token.

## Security Notes

- This solution **does not enforce permission control** (design decision); the security boundary is borne by the extension side
- Connections must carry a valid gateway Token; the Token is automatically provided by the HaijunBot web page's login session
- **Token reuse risk (known trade-off)**: the front-end exposes the Token via `window.__haijunbotAuthBridge`,
  so same-page scripts can theoretically read it. The current version accepts this risk in exchange for a zero-configuration experience;
  this can later be upgraded to a strong isolation scheme using `externally_connectable` + a fixed extension ID
- Token is only cached in the service worker's memory and is not written to `chrome.storage`
- Using `wss://` encrypted connections is recommended
- **High-sensitivity permission risks**: `cookies` / `webRequest` / `management` / `nativeMessaging` /
  `proxy` / `privacy` / `browsingData` / `contentSettings` capabilities go beyond the scope of "operating web pages";
  they can read login credentials, alter network traffic, uninstall other extensions, and clear browsing data. This solution **does not enforce permission control**
  (design decision), so these capabilities are fully open to connected Agents. Please ensure:
  1. Only connect to gateways you trust (a Token leak is equivalent to the browser being fully compromised);
  2. High-sensitivity actions (especially `browsingdata.remove`, `extmgr.uninstall`, `cookie.remove`,
     `proxy.set_settings`) are clearly explained by the Agent and agreed to by you before invocation;
  3. Remove the corresponding permissions from `manifest.json` and reload the extension when not needed.
