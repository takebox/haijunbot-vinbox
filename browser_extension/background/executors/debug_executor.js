// Debug executor: reads page console output (equivalent to the F12 Console panel),
// and provides CSP-unrestricted script evaluation and network request capture via chrome.debugger (CDP).
//
// Key point: console is an object in the page's main world; it must be injected into the MAIN world to hook
// the page's own console calls (the ISOLATED world sees a separate console object).
// The hook is designed to be idempotent and can be injected repeatedly without double-wrapping.
//
// CDP-related capabilities (debugger.evaluate / network.get_requests) go through chrome.debugger,
// do not depend on page CSP, and can execute arbitrary expressions (including sites where unsafe-eval is blocked).

import { cmdError } from "../command_router.js";

// Global state for network request capture: tabId -> { records, attachedByUs, timer }
const networkState = new Map();

export class DebugExecutor {
  /**
   * Read page console logs.
   * @param {object} p
   * @param {number} [p.tab_id] Target tab, defaults to the current active tab
   * @param {number} [p.limit] How many recent entries to return, default 100
   * @param {boolean} [p.clear] Whether to clear the cache after reading
   */
  async getLogs({ tab_id, limit, clear }) {
    const tab = await this._resolveTab(tab_id);
    const max =
      typeof limit === "number" && limit > 0 ? Math.floor(limit) : 100;

    // 1. Ensure the hook is installed (idempotent; repeated injection has no side effects)
    await this._execInWorld(tab.id, consoleHookFn, [], "MAIN");

    // 2. Read the cached snapshot
    const result = await this._execInWorld(
      tab.id,
      readLogsFn,
      [max, !!clear],
      "MAIN",
    );
    if (!result || !result.ok) {
      const reason = (result && result.error) || "failed to read console logs";
      throw cmdError("EXEC_ERROR", reason);
    }
    return { logs: result.logs, count: result.count };
  }

  /**
   * Evaluate an arbitrary expression in the page via CDP (unrestricted by the page CSP's unsafe-eval).
   * Equivalent to typing an expression directly in the F12 Console.
   * @param {object} p
   * @param {number} [p.tab_id] Target tab
   * @param {string} p.expression The expression/statement to execute
   * @param {boolean} [p.await_promise] Whether to await the Promise result, default true
   */
  async evaluate({ tab_id, expression, await_promise }) {
    const tab = await this._resolveTab(tab_id);
    if (!expression || !String(expression).trim()) {
      throw cmdError("EXEC_ERROR", "expression is required");
    }
    const target = { tabId: tab.id };
    const attachedByUs = await this._attach(target);
    try {
      await chrome.debugger.sendCommand(target, "Runtime.enable");
      const res = await chrome.debugger.sendCommand(
        target,
        "Runtime.evaluate",
        {
          expression: String(expression),
          returnByValue: true,
          awaitPromise: await_promise !== false,
          allowUnsafeEvalBlockedByCSP: true,
          userGesture: true,
        },
      );
      if (res && res.exceptionDetails) {
        const d = res.exceptionDetails;
        const msg =
          (d.exception && (d.exception.description || d.exception.value)) ||
          d.text ||
          "evaluation failed";
        throw cmdError("EXEC_ERROR", String(msg));
      }
      return {
        ok: true,
        result: res && res.result ? res.result.value : null,
        type: res && res.result ? res.result.type : null,
      };
    } finally {
      if (attachedByUs) await this._detach(target);
    }
  }

  /**
   * Pass through any CDP command (equivalent to using the DevTools Protocol directly).
   * Used for scenarios outside the Runtime/DOM domains, such as Page.addScriptToEvaluateOnNewDocument
   * (injects a script before the document is created; can hook the page's own rendering/network behavior).
   * @param {object} p
   * @param {number} [p.tab_id] Target tab
   * @param {string} p.method CDP method name, e.g. "Page.addScriptToEvaluateOnNewDocument"
   * @param {object} [p.params] CDP method parameters
   */
  async sendCommand({ tab_id, method, params }) {
    const tab = await this._resolveTab(tab_id);
    const cmd = String(method || "").trim();
    if (!cmd) {
      throw cmdError("EXEC_ERROR", "method is required");
    }
    const target = { tabId: tab.id };
    const attachedByUs = await this._attach(target);
    try {
      const res = await chrome.debugger.sendCommand(
        target,
        cmd,
        params && typeof params === "object" ? params : {},
      );
      return { ok: true, result: res === undefined ? null : res };
    } finally {
      if (attachedByUs) await this._detach(target);
    }
  }

  /**
   * Capture page network requests (equivalent to the F12 Network panel).
   * Listens via the CDP Network domain for duration_ms milliseconds before returning.
   * @param {object} p
   * @param {number} [p.tab_id] Target tab
   * @param {number} [p.duration_ms] Capture duration, default 3000
   * @param {number} [p.limit] Maximum number of entries to return, default 100
   * @param {string} [p.filter] Filter by URL substring
   */
  async getRequests({ tab_id, duration_ms, limit, filter }) {
    const tab = await this._resolveTab(tab_id);
    const duration =
      typeof duration_ms === "number" && duration_ms > 0 ? duration_ms : 3000;
    const max =
      typeof limit === "number" && limit > 0 ? Math.floor(limit) : 100;

    const target = { tabId: tab.id };
    const attachedByUs = await this._attach(target);
    const records = [];
    const byRequestId = new Map();

    const onEvent = (source, method, params) => {
      if (!source || source.tabId !== tab.id) return;
      if (method === "Network.requestWillBeSent") {
        const rec = {
          request_id: params.requestId,
          url: params.request.url,
          method: params.request.method,
          type: params.type || null,
          status: null,
          status_text: null,
          mime_type: null,
          encoded_data_length: null,
          started_at: Date.now(),
          duration_ms: null,
          failed: null,
        };
        byRequestId.set(params.requestId, rec);
        records.push(rec);
      } else if (method === "Network.responseReceived") {
        const rec = byRequestId.get(params.requestId);
        if (rec) {
          rec.status = params.response.status;
          rec.status_text = params.response.statusText;
          rec.mime_type = params.response.mimeType;
          rec.type = params.type || rec.type;
        }
      } else if (method === "Network.loadingFinished") {
        const rec = byRequestId.get(params.requestId);
        if (rec) {
          rec.encoded_data_length = params.encodedDataLength;
          rec.duration_ms = Date.now() - rec.started_at;
        }
      } else if (method === "Network.loadingFailed") {
        const rec = byRequestId.get(params.requestId);
        if (rec) {
          rec.failed = params.errorText || "failed";
          rec.duration_ms = Date.now() - rec.started_at;
        }
      }
    };

    chrome.debugger.onEvent.addListener(onEvent);
    try {
      await chrome.debugger.sendCommand(target, "Network.enable");
      await sleep(duration);
      try {
        await chrome.debugger.sendCommand(target, "Network.disable");
      } catch (e) {
        // Ignore: target may already be closed
      }
    } finally {
      chrome.debugger.onEvent.removeListener(onEvent);
      if (attachedByUs) await this._detach(target);
    }

    let out = records;
    if (filter) {
      const needle = String(filter);
      out = out.filter((r) => r.url && r.url.includes(needle));
    }
    const total = out.length;
    if (out.length > max) out = out.slice(-max);
    return { requests: out, count: total, duration_ms: duration };
  }

  // ---------------- Internal utilities ----------------

  async _resolveTab(tabId) {
    if (tabId != null) {
      try {
        return await chrome.tabs.get(tabId);
      } catch (e) {
        throw cmdError("NO_TAB", `tab not found: ${tabId}`);
      }
    }
    const [active] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (!active) throw cmdError("NO_TAB", "no active tab");
    return active;
  }

  /** Attach the debugger; returns whether it was attached by this call (to decide whether to detach). */
  async _attach(target) {
    if (!chrome.debugger) {
      throw cmdError(
        "EXEC_ERROR",
        'chrome.debugger API unavailable (requires "debugger" permission)',
      );
    }
    try {
      const targets = await chrome.debugger.getTargets();
      const existing = targets.find(
        (t) => t.tabId === target.tabId && t.attached,
      );
      if (existing) return false;
    } catch (e) {
      // When getTargets is unavailable, treat as not attached
    }
    try {
      await chrome.debugger.attach(target, "1.3");
      return true;
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      throw cmdError("EXEC_ERROR", `failed to attach debugger: ${msg}`);
    }
  }

  /** Detach the debugger (ignore failures). */
  async _detach(target) {
    try {
      await chrome.debugger.detach(target);
    } catch (e) {
      // Ignore detach failure
    }
  }

  async _execInWorld(tabId, func, args, world) {
    let results;
    try {
      results = await chrome.scripting.executeScript({
        target: { tabId },
        world,
        func,
        args,
      });
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      if (/Cannot access|chrome:\/\/|extension/i.test(msg)) {
        throw cmdError("PROTECTED_PAGE", msg);
      }
      throw cmdError("EXEC_ERROR", msg);
    }
    if (!results || !results.length) return null;
    return results[0].result;
  }
}

// ---------------- Functions injected into the page (must be self-contained, cannot reference external variables) ----------------
/** Install console hook (idempotent). Injects into the MAIN world. */
function consoleHookFn() {
  if (window.__haijunbotConsoleHooked) return { ok: true, hooked: false };

  const MAX_LOGS = 500;
  const logs = [];
  window.__haijunbotConsoleLogs = logs;

  /** Safely serialize a single argument to avoid failures from circular references/Error/DOM nodes. */
  function serializeArg(v) {
    try {
      if (v === undefined) return "undefined";
      if (v === null) return "null";
      const t = typeof v;
      if (t === "string") return v;
      if (t === "number" || t === "boolean" || t === "bigint") return String(v);
      if (t === "function") {
        return `[Function ${v.name || "anonymous"}]`;
      }
      if (t === "symbol") return String(v);
      // Error object: preserve message and stack
      if (v instanceof Error) {
        return v.stack
          ? `${v.name}: ${v.message}\n${v.stack}`
          : `${v.name}: ${v.message}`;
      }
      // DOM node: convert to a brief description
      if (typeof Node !== "undefined" && v instanceof Node) {
        const tag = v.tagName ? v.tagName.toLowerCase() : v.nodeName;
        const id = v.id ? `#${v.id}` : "";
        const cls =
          v.className && typeof v.className === "string"
            ? `.${v.className.trim().split(/\s+/).join(".")}`
            : "";
        return `<${tag}${id}${cls}>`;
      }
      // Regular object: try JSON serialization, fall back to String() on failure
      const seen = new WeakSet();
      return JSON.stringify(v, (key, val) => {
        if (typeof val === "object" && val !== null) {
          if (seen.has(val)) return "[Circular]";
          seen.add(val);
        }
        if (typeof val === "function")
          return `[Function ${val.name || "anonymous"}]`;
        if (typeof val === "bigint") return String(val);
        return val;
      });
    } catch (e) {
      try {
        return String(v);
      } catch (e2) {
        return "[Unserializable]";
      }
    }
  }

  /** Append a log entry (ring buffer; oldest entries are discarded when the limit is exceeded). */
  function push(level, args) {
    try {
      logs.push({
        level,
        timestamp: Date.now(),
        args: Array.prototype.map.call(args, serializeArg),
      });
      while (logs.length > MAX_LOGS) logs.shift();
    } catch (e) {
      // Silently ignore failures in logging itself to avoid affecting the page
    }
  }

  // 1. Hook console methods
  const levels = ["log", "info", "warn", "error", "debug"];
  for (const level of levels) {
    const original = console[level];
    console[level] = function (...args) {
      push(level, args);
      if (typeof original === "function") {
        try {
          original.apply(console, args);
        } catch (e) {
          // Ignore exceptions from the original method
        }
      }
    };
  }

  // 2. Hook uncaught exceptions
  const originalOnError = window.onerror;
  window.onerror = function (message, source, lineno, colno, error) {
    const detail =
      error instanceof Error
        ? `${error.name}: ${error.message}`
        : String(message);
    push("error", [
      `${detail} (${source || "?"}:${lineno || 0}:${colno || 0})`,
    ]);
    if (typeof originalOnError === "function") {
      try {
        return originalOnError.apply(window, arguments);
      } catch (e) {
        // Ignore
      }
    }
    return false;
  };

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event && event.reason;
    const detail =
      reason instanceof Error
        ? `${reason.name}: ${reason.message}`
        : serializeArg(reason);
    push("error", [`UnhandledPromiseRejection: ${detail}`]);
  });

  window.__haijunbotConsoleHooked = true;
  return { ok: true, hooked: true };
}

/** Read the log cache snapshot, optionally clearing it. Injects into the MAIN world. */
function readLogsFn(limit, clear) {
  try {
    const logs = window.__haijunbotConsoleLogs;
    if (!Array.isArray(logs)) {
      return { ok: true, logs: [], count: 0 };
    }
    const count = logs.length;
    const slice = limit > 0 ? logs.slice(-limit) : logs.slice();
    if (clear) {
      logs.length = 0;
    }
    return { ok: true, logs: slice, count };
  } catch (e) {
    return { ok: false, error: (e && e.message) || String(e) };
  }
}

/** Simple delay. */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
