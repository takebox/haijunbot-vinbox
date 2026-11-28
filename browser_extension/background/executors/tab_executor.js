// Tabs and navigation executor: wraps chrome.tabs operations.

import { cmdError } from "../command_router.js";

export class TabExecutor {
  /** List all tabs. */
  async list() {
    const tabs = await chrome.tabs.query({});
    return tabs.map((t) => ({
      tab_id: t.id,
      url: t.url,
      title: t.title,
      active: t.active,
      window_id: t.windowId,
    }));
  }

  /** Activate a specified tab. */
  async activate({ tab_id }) {
    if (tab_id == null) throw cmdError("NO_TAB", "tab_id is required");
    const tab = await this._getTab(tab_id);
    await chrome.tabs.update(tab.id, { active: true });
    if (tab.windowId != null) {
      try {
        await chrome.windows.update(tab.windowId, { focused: true });
      } catch (e) {
        // Some environments do not allow focusing windows; ignore
      }
    }
    return { ok: true, tab_id: tab.id };
  }

  /** Close a specified tab. */
  async close({ tab_id }) {
    if (tab_id == null) throw cmdError("NO_TAB", "tab_id is required");
    await this._getTab(tab_id);
    await chrome.tabs.remove(tab_id);
    return { ok: true, tab_id };
  }

  /**
   * Create a new tab.
   * When new_window is true (default), prefer creating the tab in a window that "does not contain the HaijunBot front-end page"
   * to avoid mixing automation-opened pages into the window where the user views HaijunBot;
   * only open a new window when all windows contain the HaijunBot front-end page (nowhere else to put it).
   * When new_window is false, fall back to creating the tab in the current window.
   */
  async create({ url, active, new_window }) {
    const target = url || "about:blank";
    if (new_window !== false) {
      const windowId = await this._pickTargetWindowId();
      if (windowId != null) {
        const tab = await chrome.tabs.create({
          url: target,
          active: active !== false,
          windowId,
        });
        return {
          ok: true,
          tab_id: tab.id,
          window_id: tab.windowId,
          url: tab.url,
          new_window: false,
        };
      }
      const win = await chrome.windows.create({
        url: target,
        focused: active !== false,
      });
      const tab = win && win.tabs && win.tabs.length ? win.tabs[0] : null;
      return {
        ok: true,
        tab_id: tab ? tab.id : null,
        window_id: win ? win.id : null,
        url: tab ? tab.url : target,
        new_window: true,
      };
    }
    const tab = await chrome.tabs.create({
      url: target,
      active: active !== false,
    });
    return {
      ok: true,
      tab_id: tab.id,
      window_id: tab.windowId,
      url: tab.url,
      new_window: false,
    };
  }

  /** Navigate to a specified URL. */
  async navigate({ tab_id, url, wait_until, new_window }) {
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    let tabId = tab_id;
    if (tabId == null) {
      // When tab_id is not specified, reuse the create logic (prefer creating a tab in a non-HaijunBot window)
      const created = await this.create({ url, new_window });
      tabId = created.tab_id;
      if (tabId != null && wait_until !== "none") {
        await this._waitForComplete(tabId);
      }
      return { ok: true, tab_id: tabId, url, new_window: created.new_window };
    }
    await this._getTab(tabId);
    await chrome.tabs.update(tabId, { url });
    if (wait_until !== "none") {
      await this._waitForComplete(tabId);
    }
    const tab = await chrome.tabs.get(tabId);
    return { ok: true, tab_id: tabId, url: tab.url, title: tab.title };
  }

  /** Reload a tab. */
  async reload({ tab_id }) {
    const tab = await this._resolveTab(tab_id);
    await chrome.tabs.reload(tab.id);
    await this._waitForComplete(tab.id);
    return { ok: true, tab_id: tab.id };
  }

  /** Go back. */
  async back({ tab_id }) {
    const tab = await this._resolveTab(tab_id);
    await chrome.tabs.goBack(tab.id);
    return { ok: true, tab_id: tab.id };
  }

  /** Go forward. */
  async forward({ tab_id }) {
    const tab = await this._resolveTab(tab_id);
    await chrome.tabs.goForward(tab.id);
    return { ok: true, tab_id: tab.id };
  }

  /**
   * Read basic page information (URL, title, ready state, viewport/scroll/document dimensions).
   */
  async getInfo({ tab_id }) {
    const tab = await this._resolveTab(tab_id);
    let info = null;
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        world: "ISOLATED",
        func: pageInfoFn,
      });
      info = results && results.length ? results[0].result : null;
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      if (/Cannot access|chrome:\/\/|extension/i.test(msg)) {
        throw cmdError("PROTECTED_PAGE", msg);
      }
      throw cmdError("EXEC_ERROR", msg);
    }
    if (!info) {
      throw cmdError("EXEC_ERROR", "failed to read page info");
    }
    return {
      tab_id: tab.id,
      url: info.url,
      title: info.title,
      ready_state: info.ready_state,
      viewport: info.viewport,
      scroll: info.scroll,
      document: info.document,
    };
  }

  // ---------------- Internal utilities ----------------

  /**
   * Pick the window where a "new tab" should be placed, returning the window_id; returns null if there is nowhere to put it (a new window is needed).
   *
   * Rule: exclude all windows containing the HaijunBot front-end page (these windows are reserved for the user to view HaijunBot, not mixed with automation pages),
   * then prefer the most recently focused window among the remaining ones; return null if all windows contain the HaijunBot front-end page.
   */
  async _pickTargetWindowId() {
    // Overall timeout as a safety net: if any step (windows.getAll / executeScript / getLastFocused)
    // hangs, it should not block tab creation; on timeout, return null and let the caller open a new window.
    try {
      return await this._withTimeout(this._pickTargetWindowIdInner(), 3000);
    } catch (e) {
      // On probe timeout/failure, return null and let the caller open a new window, avoiding blocking tab creation
      return null;
    }
  }

  async _pickTargetWindowIdInner() {
    const windows = await chrome.windows.getAll({ populate: true });
    if (!windows.length) return null;
    // Probe each window in parallel for HaijunBot front-end pages (serial probing would degrade linearly with tab count)
    const haijunbotFlags = await Promise.all(
      windows.map((win) => this._windowHasHaijunBotPage(win)),
    );
    const candidates = windows.filter((_, i) => !haijunbotFlags[i]);
    if (!candidates.length) return null;
    // Prefer the most recently focused candidate window, matching user intuition
    try {
      const lastFocused = await chrome.windows.getLastFocused();
      if (lastFocused && candidates.some((w) => w.id === lastFocused.id)) {
        return lastFocused.id;
      }
    } catch (e) {
      // In some environments the last focused window cannot be obtained; fall back to the first candidate window
    }
    return candidates[0].id;
  }

  /** Determine whether a HaijunBot front-end page exists in a window (any tab in the window matching is sufficient). */
  async _windowHasHaijunBotPage(win) {
    const tabs = (win && win.tabs) || [];
    const flags = await Promise.all(tabs.map((tab) => this._isHaijunBotPage(tab)));
    return flags.some(Boolean);
  }

  /**
   * Determine whether a tab is a HaijunBot front-end page.
   * Based on window.__haijunbotAuthBridge exposed by the page's main world (consistent with how service_worker probes login state),
   * not URL patterns — the HaijunBot front-end and gateway may be on different domains, so URLs cannot reliably identify it.
   */
  async _isHaijunBotPage(tab) {
    if (!tab || tab.id == null) return false;
    if (!/^https?:/i.test(tab.url || "")) return false;
    try {
      // Injection may hang due to the target page's renderer being busy/frozen; add a timeout to avoid blocking the entire window-probing process
      const results = await this._withTimeout(
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: hasHaijunBotAuthBridgeFn,
          world: "MAIN",
        }),
        2000,
      );
      return Boolean(results && results[0] && results[0].result);
    } catch (e) {
      // Restricted pages (chrome://, extension pages, etc.) cannot be injected, or injection timed out; treat as non-HaijunBot page
      return false;
    }
  }

  /** Add a timeout to a Promise; rejects on timeout to avoid underlying calls hanging indefinitely. */
  async _withTimeout(promise, ms) {
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error("timeout")), ms);
    });
    try {
      return await Promise.race([promise, timeout]);
    } finally {
      clearTimeout(timer);
    }
  }

  async _getTab(tabId) {
    try {
      return await chrome.tabs.get(tabId);
    } catch (e) {
      throw cmdError("NO_TAB", `tab not found: ${tabId}`);
    }
  }

  /** Use the current active tab when tab_id is not specified. */
  async _resolveTab(tabId) {
    if (tabId != null) return this._getTab(tabId);
    const [active] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (!active) throw cmdError("NO_TAB", "no active tab");
    return active;
  }

  /** Wait for tab loading to complete (simple polling of status). */
  async _waitForComplete(tabId, timeoutMs = 15000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      try {
        const tab = await chrome.tabs.get(tabId);
        if (tab.status === "complete") return;
      } catch (e) {
        throw cmdError("NO_TAB", `tab not found: ${tabId}`);
      }
      await sleep(150);
    }
    // Timeout is not considered a fatal error; leave it to subsequent operations to decide
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Function injected into the page (must be self-contained, cannot reference external variables)
function hasHaijunBotAuthBridgeFn() {
  try {
    return Boolean(window.__haijunbotAuthBridge);
  } catch (e) {
    return false;
  }
}

// Function injected into the page (must be self-contained, cannot reference external variables)
function pageInfoFn() {
  const doc = document.documentElement;
  return {
    url: location.href,
    title: document.title,
    ready_state: document.readyState,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
    },
    scroll: {
      x: window.scrollX,
      y: window.scrollY,
    },
    document: {
      width: doc ? doc.scrollWidth : 0,
      height: doc ? doc.scrollHeight : 0,
    },
  };
}
