// Command router: maps gateway-dispatched actions to corresponding executors and returns results.
//
// Command envelope (gateway -> extension):
//   { id, type: "command", action: "dom.click", params: {...}, timeout_ms: 15000 }
// Result envelope (extension -> gateway):
//   { id, type: "result", success: true, data: {...}, error: null }

import { TabExecutor } from "./executors/tab_executor.js";
import { DomExecutor } from "./executors/dom_executor.js";
import { CaptureExecutor } from "./executors/capture_executor.js";
import { DebugExecutor } from "./executors/debug_executor.js";
import { ScriptExecutor } from "./executors/script_executor.js";
import { ClipboardExecutor } from "./executors/clipboard_executor.js";
import { BookmarksExecutor } from "./executors/bookmarks_executor.js";
import { HistoryExecutor } from "./executors/history_executor.js";
import { DownloadsExecutor } from "./executors/downloads_executor.js";
import { SessionsExecutor } from "./executors/sessions_executor.js";
import { TopSitesExecutor } from "./executors/top_sites_executor.js";
import { ReadingListExecutor } from "./executors/reading_list_executor.js";
import { ContextMenusExecutor } from "./executors/context_menus_executor.js";
import { AlarmsExecutor } from "./executors/alarms_executor.js";
import { NotificationsExecutor } from "./executors/notifications_executor.js";
import { SearchExecutor } from "./executors/search_executor.js";
import { IdleExecutor } from "./executors/idle_executor.js";
import { FaviconExecutor } from "./executors/favicon_executor.js";
import { WebNavigationExecutor } from "./executors/web_navigation_executor.js";
import { TabGroupsExecutor } from "./executors/tab_groups_executor.js";
import { CookiesExecutor } from "./executors/cookies_executor.js";
import { WebRequestExecutor } from "./executors/web_request_executor.js";
import { ManagementExecutor } from "./executors/management_executor.js";
import { NativeMessagingExecutor } from "./executors/native_messaging_executor.js";
import { ProxyExecutor } from "./executors/proxy_executor.js";
import { PrivacyExecutor } from "./executors/privacy_executor.js";
import { BrowsingDataExecutor } from "./executors/browsing_data_executor.js";
import { ContentSettingsExecutor } from "./executors/content_settings_executor.js";

export class CommandRouter {
  constructor() {
    this.tabExecutor = new TabExecutor();
    this.domExecutor = new DomExecutor();
    this.captureExecutor = new CaptureExecutor();
    this.debugExecutor = new DebugExecutor();
    this.scriptExecutor = new ScriptExecutor();
    this.clipboardExecutor = new ClipboardExecutor();
    this.bookmarksExecutor = new BookmarksExecutor();
    this.historyExecutor = new HistoryExecutor();
    this.downloadsExecutor = new DownloadsExecutor();
    this.sessionsExecutor = new SessionsExecutor();
    this.topSitesExecutor = new TopSitesExecutor();
    this.readingListExecutor = new ReadingListExecutor();
    this.contextMenusExecutor = new ContextMenusExecutor();
    this.alarmsExecutor = new AlarmsExecutor();
    this.notificationsExecutor = new NotificationsExecutor();
    this.searchExecutor = new SearchExecutor();
    this.idleExecutor = new IdleExecutor();
    this.faviconExecutor = new FaviconExecutor();
    this.webNavigationExecutor = new WebNavigationExecutor();
    this.tabGroupsExecutor = new TabGroupsExecutor();
    this.cookiesExecutor = new CookiesExecutor();
    this.webRequestExecutor = new WebRequestExecutor();
    this.managementExecutor = new ManagementExecutor();
    this.nativeMessagingExecutor = new NativeMessagingExecutor();
    this.proxyExecutor = new ProxyExecutor();
    this.privacyExecutor = new PrivacyExecutor();
    this.browsingDataExecutor = new BrowsingDataExecutor();
    this.contentSettingsExecutor = new ContentSettingsExecutor();

    // action -> handler(params) => Promise<data>
    this.routes = {
      // Tab category
      "tab.list": (p) => this.tabExecutor.list(p),
      "tab.activate": (p) => this.tabExecutor.activate(p),
      "tab.close": (p) => this.tabExecutor.close(p),
      "tab.create": (p) => this.tabExecutor.create(p),
      // Navigation category
      "page.navigate": (p) => this.tabExecutor.navigate(p),
      "page.reload": (p) => this.tabExecutor.reload(p),
      "page.back": (p) => this.tabExecutor.back(p),
      "page.forward": (p) => this.tabExecutor.forward(p),
      "page.get_info": (p) => this.tabExecutor.getInfo(p),
      // DOM category
      "dom.query": (p) => this.domExecutor.query(p),
      "dom.get_text": (p) => this.domExecutor.getText(p),
      "dom.get_html": (p) => this.domExecutor.getHtml(p),
      "dom.get_computed_style": (p) => this.domExecutor.getComputedStyle(p),
      "dom.click": (p) => this.domExecutor.click(p),
      "dom.type": (p) => this.domExecutor.type(p),
      "dom.hover": (p) => this.domExecutor.hover(p),
      "dom.select": (p) => this.domExecutor.select(p),
      "dom.wait_for": (p) => this.domExecutor.waitFor(p),
      "dom.press_key": (p) => this.domExecutor.pressKey(p),
      "dom.scroll": (p) => this.domExecutor.scroll(p),
      "dom.upload_file": (p) => this.domExecutor.uploadFile(p),
      "script.execute": (p) => this.domExecutor.execute(p),
      // Script management category (Tampermonkey-like: install / manage / execute custom page scripts)
      "script.list": (p) => this.scriptExecutor.list(p),
      "script.get": (p) => this.scriptExecutor.get(p),
      "script.install": (p) => this.scriptExecutor.install(p),
      "script.install_from_url": (p) => this.scriptExecutor.installFromUrl(p),
      "script.uninstall": (p) => this.scriptExecutor.uninstall(p),
      "script.export": (p) => this.scriptExecutor.exportScript(p),
      "script.set_enabled": (p) => this.scriptExecutor.setEnabled(p),
      "script.run": (p) => this.scriptExecutor.run(p),
      // Clipboard category (write gateway static files or given content to front-end clipboard)
      "clipboard.write_from_url": (p) => this.clipboardExecutor.writeFromUrl(p),
      "clipboard.write": (p) => this.clipboardExecutor.write(p),
      // Debug category
      "console.get_logs": (p) => this.debugExecutor.getLogs(p),
      "debugger.evaluate": (p) => this.debugExecutor.evaluate(p),
      "debugger.send_command": (p) => this.debugExecutor.sendCommand(p),
      "network.get_requests": (p) => this.debugExecutor.getRequests(p),
      // Capture category
      "capture.screenshot": (p) => this.captureExecutor.screenshot(p, ctx),
      // Bookmarks category
      "bookmark.list": (p) => this.bookmarksExecutor.list(p),
      "bookmark.search": (p) => this.bookmarksExecutor.search(p),
      "bookmark.create": (p) => this.bookmarksExecutor.create(p),
      "bookmark.remove": (p) => this.bookmarksExecutor.remove(p),
      "bookmark.remove_tree": (p) => this.bookmarksExecutor.removeTree(p),
      // History category
      "history.search": (p) => this.historyExecutor.search(p),
      "history.recent": (p) => this.historyExecutor.recent(p),
      "history.remove": (p) => this.historyExecutor.remove(p),
      "history.remove_range": (p) => this.historyExecutor.removeRange(p),
      // Downloads category
      "download.list": (p) => this.downloadsExecutor.list(p),
      "download.search": (p) => this.downloadsExecutor.search(p),
      "download.start": (p) => this.downloadsExecutor.download(p),
      "download.pause": (p) => this.downloadsExecutor.pause(p),
      "download.resume": (p) => this.downloadsExecutor.resume(p),
      "download.cancel": (p) => this.downloadsExecutor.cancel(p),
      "download.erase": (p) => this.downloadsExecutor.erase(p),
      "download.open": (p) => this.downloadsExecutor.open(p),
      // Sessions category
      "session.recent": (p) => this.sessionsExecutor.recent(p),
      "session.restore": (p) => this.sessionsExecutor.restore(p),
      // Top sites category
      "topsite.list": (p) => this.topSitesExecutor.list(p),
      // Reading list category
      "readinglist.list": (p) => this.readingListExecutor.list(p),
      "readinglist.add": (p) => this.readingListExecutor.add(p),
      "readinglist.remove": (p) => this.readingListExecutor.remove(p),
      "readinglist.update": (p) => this.readingListExecutor.update(p),
      // Context menus category
      "contextmenu.create": (p) => this.contextMenusExecutor.create(p),
      "contextmenu.remove": (p) => this.contextMenusExecutor.remove(p),
      "contextmenu.remove_all": (p) => this.contextMenusExecutor.removeAll(p),
      "contextmenu.list": (p) => this.contextMenusExecutor.list(p),
      // Alarms category
      "alarm.create": (p) => this.alarmsExecutor.create(p),
      "alarm.list": (p) => this.alarmsExecutor.list(p),
      "alarm.clear": (p) => this.alarmsExecutor.clear(p),
      "alarm.clear_all": (p) => this.alarmsExecutor.clearAll(p),
      // Notifications category
      "notification.create": (p) => this.notificationsExecutor.create(p),
      "notification.clear": (p) => this.notificationsExecutor.clear(p),
      "notification.clear_all": (p) => this.notificationsExecutor.clearAll(p),
      "notification.list": (p) => this.notificationsExecutor.getAll(p),
      // Search category
      "search.query": (p) => this.searchExecutor.query(p),
      // Idle state category
      "idle.query_state": (p) => this.idleExecutor.queryState(p),
      "idle.set_interval": (p) => this.idleExecutor.setInterval(p),
      "idle.get_interval": (p) => this.idleExecutor.getInterval(p),
      // Favicon category
      "favicon.get_url": (p) => this.faviconExecutor.getUrl(p),
      // Web navigation events category
      "webnav.get_all_frames": (p) =>
        this.webNavigationExecutor.getAllFrames(p),
      "webnav.get_frame": (p) => this.webNavigationExecutor.getFrame(p),
      // Tab groups category
      "tabgroup.list": (p) => this.tabGroupsExecutor.list(p),
      "tabgroup.get": (p) => this.tabGroupsExecutor.get(p),
      "tabgroup.query": (p) => this.tabGroupsExecutor.query(p),
      "tabgroup.update": (p) => this.tabGroupsExecutor.update(p),
// ===== The following are high-sensitivity capabilities, user confirmation required before calling =====
// Cookie category (highly sensitive)
      "cookie.get": (p) => this.cookiesExecutor.get(p),
      "cookie.get_all": (p) => this.cookiesExecutor.getAll(p),
      "cookie.set": (p) => this.cookiesExecutor.set(p),
      "cookie.remove": (p) => this.cookiesExecutor.remove(p),
      // Network request rules category (highly sensitive, based on declarativeNetRequest)
      "netrule.list": (p) => this.webRequestExecutor.listRules(p),
      "netrule.register": (p) => this.webRequestExecutor.registerRule(p),
      "netrule.unregister": (p) => this.webRequestExecutor.unregisterRule(p),
      // Extension and app management category (highly sensitive, uninstall/disable is irreversible)
      "extmgr.list": (p) => this.managementExecutor.list(p),
      "extmgr.get": (p) => this.managementExecutor.get(p),
      "extmgr.launch_app": (p) => this.managementExecutor.launchApp(p),
      "extmgr.set_enabled": (p) => this.managementExecutor.setEnabled(p),
      "extmgr.uninstall": (p) => this.managementExecutor.uninstall(p),
      // Native messaging category (highly sensitive, requires registered native host)
      "native.send": (p) => this.nativeMessagingExecutor.send(p),
      // Proxy category (highly sensitive, affects all network traffic)
      "proxy.get_settings": (p) => this.proxyExecutor.getSettings(p),
      "proxy.set_settings": (p) => this.proxyExecutor.setSettings(p),
      "proxy.clear_settings": (p) => this.proxyExecutor.clearSettings(p),
      // Privacy settings category (highly sensitive)
      "privacy.get": (p) => this.privacyExecutor.get(p),
      "privacy.set": (p) => this.privacyExecutor.set(p),
      // Browsing data category (highly sensitive, remove is irreversible)
      "browsingdata.settings": (p) => this.browsingDataExecutor.settings(p),
      "browsingdata.remove": (p) => this.browsingDataExecutor.remove(p),
      // Content settings category (highly sensitive)
      "contentsettings.get": (p) => this.contentSettingsExecutor.get(p),
      "contentsettings.set": (p) => this.contentSettingsExecutor.set(p),
      "contentsettings.clear": (p) => this.contentSettingsExecutor.clear(p),
    };
  }

  /**
   * Returns the list of capabilities supported by this extension (for hello to report to gateway, gateway passes to front-end capability list display).
   * Each capability corresponds one-to-one with an action in routes; platform is fixed as "browser".
   * @returns {Array<{name:string, description:string, parameters:object, platform:string}>}
   */
  getCapabilities() {
    return CAPABILITIES;
  }

  /**
   * Execute a command and return the result envelope.
   * @param {object} msg Command message
   * @param {object} [ctx] Execution context (command source gateway and login Token), for screenshot upload and similar capabilities
   * @returns {Promise<object>} Result envelope
   */
  async handle(msg, ctx = {}) {
    const id = msg?.id;
    const action = msg?.action;
    const params = msg?.params || {};

    const handler = this.routes[action];
    if (!handler) {
      return {
        id,
        type: "result",
        success: false,
        data: null,
        error: `unknown action: ${action}`,
      };
    }

    try {
      const data = await handler(params);
      return {
        id,
        type: "result",
        success: true,
        data: data ?? null,
        error: null,
      };
    } catch (e) {
      const code = e && e.code ? e.code : "EXEC_ERROR";
      const message = e && e.message ? e.message : String(e);
      return {
        id,
        type: "result",
        success: false,
        data: null,
        error: `${code}: ${message}`,
      };
    }
  }
}

/** Construct an exception with error code. */
export function cmdError(code, message) {
  const err = new Error(message);
  err.code = code;
  return err;
}

/**
 * Capability list exposed by this extension (dynamically reported to gateway).
 * Each item corresponds to an action in CommandRouter.routes, name is the action name;
 * Gateway/front-end uses this to display "what capabilities this plugin has", aligned with daemon capability list format.
 */
const CAPABILITIES = [
  {
    name: "tab.list",
    description: "List currently open browser tabs",
    parameters: {},
    platform: "browser",
  },
  {
    name: "tab.create",
    description: "Create new tab (can specify URL and whether new window)",
    parameters: { url: "string", new_window: "boolean" },
    platform: "browser",
  },
  {
    name: "tab.close",
    description: "Close specified tab",
    parameters: { tab_id: "number" },
    platform: "browser",
  },
  {
    name: "tab.activate",
    description: "Switch to specified tab",
    parameters: { tab_id: "number" },
    platform: "browser",
  },
  {
    name: "page.navigate",
    description: "Navigate to specified URL",
    parameters: { url: "string", tab_id: "number" },
    platform: "browser",
  },
  {
    name: "page.reload",
    description: "Reload current page",
    parameters: { tab_id: "number" },
    platform: "browser",
  },
  {
    name: "page.get_info",
    description: "Read page basic info (URL/title/ready state etc.)",
    parameters: {},
    platform: "browser",
  },
  {
    name: "dom.query",
    description: "Query page element info",
    parameters: { selector: "string", all: "boolean" },
    platform: "browser",
  },
  {
    name: "dom.get_text",
    description: "Read element text",
    parameters: { selector: "string" },
    platform: "browser",
  },
  {
    name: "dom.click",
    description: "Click page element",
    parameters: { selector: "string" },
    platform: "browser",
  },
  {
    name: "dom.type",
    description: "Type text into input field",
    parameters: { selector: "string", text: "string" },
    platform: "browser",
  },
  {
    name: "dom.press_key",
    description: "Press keyboard key",
    parameters: { key: "string" },
    platform: "browser",
  },
  {
    name: "script.execute",
    description: "Execute arbitrary JS script in page (main world)",
    parameters: { code: "string" },
    platform: "browser",
  },
  {
    name: "script.run",
    description: "Run installed custom page script in extension",
    parameters: { id: "string", action: "string", args: "object" },
    platform: "browser",
  },
  {
    name: "script.install",
    description: "Install custom page script (Tampermonkey-like)",
    parameters: { name: "string", source: "string" },
    platform: "browser",
  },
  {
    name: "script.list",
    description: "List installed custom page scripts",
    parameters: {},
    platform: "browser",
  },
  {
    name: "capture.screenshot",
    description: "Take screenshot of page",
    parameters: { full_page: "boolean" },
    platform: "browser",
  },
  {
    name: "debugger.evaluate",
    description: "Evaluate arbitrary expression via CDP (not restricted by page CSP)",
    parameters: { expression: "string" },
    platform: "browser",
  },
  {
    name: "console.get_logs",
    description: "Read page console logs",
    parameters: { limit: "number" },
    platform: "browser",
  },
  {
    name: "network.get_requests",
    description: "Capture page network requests",
    parameters: { duration_ms: "number", filter: "string" },
    platform: "browser",
  },
  {
    name: "search.query",
    description: "Search with default search engine",
    parameters: { query: "string" },
    platform: "browser",
  },
  {
    name: "clipboard.write",
    description: "Write text or image to system clipboard",
    parameters: { text: "string" },
    platform: "browser",
  },
  {
    name: "bookmark.list",
    description: "List bookmarks",
    parameters: {},
    platform: "browser",
  },
  {
    name: "history.search",
    description: "Query browsing history",
    parameters: { query: "string" },
    platform: "browser",
  },
  {
    name: "download.list",
    description: "List download records",
    parameters: {},
    platform: "browser",
  },
  {
    name: "download.start",
    description: "Start download task",
    parameters: { url: "string" },
    platform: "browser",
  },
  {
    name: "notification.create",
    description: "Show system notification",
    parameters: { title: "string", message: "string" },
    platform: "browser",
  },
  {
    name: "alarm.create",
    description: "Create timer",
    parameters: { name: "string", delay_minutes: "number" },
    platform: "browser",
  },
  {
    name: "session.recent",
    description: "List recently closed tabs/windows",
    parameters: {},
    platform: "browser",
  },
  {
    name: "cookie.get",
    description: "Read site cookies (highly sensitive, involves login credentials)",
    parameters: { url: "string", name: "string" },
    platform: "browser",
  },
  {
    name: "cookie.set",
    description: "Write/modify cookies (highly sensitive)",
    parameters: { url: "string", name: "string", value: "string" },
    platform: "browser",
  },
  {
    name: "extmgr.list",
    description: "List installed extensions (highly sensitive)",
    parameters: {},
    platform: "browser",
  },
  {
    name: "proxy.get_settings",
    description: "Read browser proxy configuration (highly sensitive)",
    parameters: {},
    platform: "browser",
  },
  {
    name: "browsingdata.remove",
    description: "Clear browsing data (highly sensitive, irreversible)",
    parameters: { data_types: "array" },
    platform: "browser",
  },
];
