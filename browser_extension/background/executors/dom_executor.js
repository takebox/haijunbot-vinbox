// DOM executor: reads and writes the DOM in the page via content script.
//
// Uses chrome.scripting.executeScript to inject functions, avoiding reliance on a persistent content script.

import { cmdError } from "../command_router.js";

// Set of common properties returned by get_computed_style when props are not explicitly provided.
const DEFAULT_STYLE_PROPS = [
  "display",
  "position",
  "width",
  "height",
  "color",
  "background-color",
  "font-size",
  "font-family",
  "font-weight",
  "margin",
  "padding",
  "border",
  "z-index",
  "opacity",
  "visibility",
  "overflow",
  "flex-direction",
  "justify-content",
  "align-items",
  "box-sizing",
  "line-height",
  "text-align",
];

export class DomExecutor {
  /** Query element information. */
  async query({ tab_id, selector, all }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const result = await this._exec(tab.id, queryFn, [selector, !!all]);
    return result;
  }

  /** Read element text. */
  async getText({ tab_id, selector }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const result = await this._exec(tab.id, getTextFn, [selector]);
    if (result == null) {
      throw cmdError("ELEMENT_NOT_FOUND", `element not found: ${selector}`);
    }
    return { text: result };
  }

  /** Read element HTML. */
  async getHtml({ tab_id, selector }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const result = await this._exec(tab.id, getHtmlFn, [selector]);
    if (result == null) {
      throw cmdError("ELEMENT_NOT_FOUND", `element not found: ${selector}`);
    }
    return { html: result };
  }

  /** Click an element. */
  async click({ tab_id, selector }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const ok = await this._exec(tab.id, clickFn, [selector]);
    if (!ok) {
      throw cmdError("ELEMENT_NOT_FOUND", `element not found: ${selector}`);
    }
    return { ok: true };
  }

  /** Type text (focus, clear, then set value and dispatch events). */
  async type({ tab_id, selector, text, clear }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const ok = await this._exec(tab.id, typeFn, [
      selector,
      text ?? "",
      clear !== false,
    ]);
    if (!ok) {
      throw cmdError("ELEMENT_NOT_FOUND", `element not found: ${selector}`);
    }
    return { ok: true };
  }

  /** Hover over an element. */
  async hover({ tab_id, selector }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const ok = await this._exec(tab.id, hoverFn, [selector]);
    if (!ok) {
      throw cmdError("ELEMENT_NOT_FOUND", `element not found: ${selector}`);
    }
    return { ok: true };
  }

  /** Select a dropdown item. */
  async select({ tab_id, selector, value }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const ok = await this._exec(tab.id, selectFn, [selector, value]);
    if (!ok) {
      throw cmdError("ELEMENT_NOT_FOUND", `element not found: ${selector}`);
    }
    return { ok: true };
  }

  /** Wait for an element to appear/disappear. */
  async waitFor({ tab_id, selector, state, timeout_ms }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const timeout = typeof timeout_ms === "number" ? timeout_ms : 15000;
    const targetState = state || "visible";
    const ok = await this._exec(tab.id, waitForFn, [
      selector,
      targetState,
      timeout,
    ]);
    if (!ok) {
      throw cmdError(
        "TIMEOUT",
        `wait_for timeout: ${selector} (${targetState})`,
      );
    }
    return { ok: true };
  }

  /** Press a keyboard key (optionally focus a specified element first, otherwise acts on the currently focused element). */
  async pressKey({ tab_id, selector, key }) {
    const tab = await this._resolveTab(tab_id);
    if (!key || !String(key).trim()) {
      throw cmdError("EXEC_ERROR", "key is required");
    }
    const result = await this._exec(tab.id, pressKeyFn, [
      selector || "",
      String(key),
    ]);
    if (!result || !result.ok) {
      const reason = (result && result.error) || "press_key failed";
      throw cmdError(
        reason === "element not found" ? "ELEMENT_NOT_FOUND" : "EXEC_ERROR",
        reason,
      );
    }
    return { ok: true, key: result.key, target: result.target };
  }

  /** Scroll the page: scrolls to the element if a selector is specified, otherwise scrolls by x/y pixels. */
  async scroll({ tab_id, selector, x, y, behavior }) {
    const tab = await this._resolveTab(tab_id);
    const result = await this._exec(tab.id, scrollFn, [
      selector || "",
      typeof x === "number" ? x : 0,
      typeof y === "number" ? y : 0,
      behavior === "smooth" ? "smooth" : "auto",
    ]);
    if (!result || !result.ok) {
      const reason = (result && result.error) || "scroll failed";
      throw cmdError(
        reason === "element not found" ? "ELEMENT_NOT_FOUND" : "EXEC_ERROR",
        reason,
      );
    }
    return result;
  }

  /** Execute arbitrary JS code in the page (fallback capability, high risk). */
  async execute({ tab_id, code, world }) {
    const tab = await this._resolveTab(tab_id);
    if (!code || !String(code).trim()) {
      throw cmdError("EXEC_ERROR", "code is required");
    }
    // Execute in the MAIN world by default: new Function in the ISOLATED world is blocked by the page CSP's
    // unsafe-eval (most sites have this restriction), causing execution to inevitably fail.
    // When world: "ISOLATED" is explicitly passed, still execute as the user requested.
    const targetWorld = world === "ISOLATED" ? "ISOLATED" : "MAIN";
    const result = await this._execInWorld(
      tab.id,
      executeFn,
      [String(code)],
      targetWorld,
    );
    if (!result || !result.ok) {
      const reason = (result && result.error) || "script execution failed";
      throw cmdError("EXEC_ERROR", reason);
    }
    return { ok: true, result: result.value };
  }

  /**
   * Read the computed style of an element (equivalent to the F12 Computed panel).
   * Returns a set of common properties when props are not provided; returns only the specified properties when props are provided.
   */
  async getComputedStyle({ tab_id, selector, props }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    const wanted =
      Array.isArray(props) && props.length
        ? props.map((p) => String(p))
        : DEFAULT_STYLE_PROPS;
    const result = await this._exec(tab.id, getComputedStyleFn, [
      selector,
      wanted,
    ]);
    if (result == null) {
      throw cmdError("ELEMENT_NOT_FOUND", `element not found: ${selector}`);
    }
    return { selector, styles: result };
  }

  /**
   * Upload a local file to a file input.
   * Uses chrome.debugger's DOM.setFileInputFiles to set a real file path,
   * which is the only way for the extension to actually upload a local file (local file content cannot be read within the sandbox).
   */
  async uploadFile({ tab_id, selector, file_path }) {
    const tab = await this._resolveTab(tab_id);
    this._requireSelector(selector);
    if (!file_path || !String(file_path).trim()) {
      throw cmdError("EXEC_ERROR", "file_path is required");
    }
    if (!chrome.debugger) {
      throw cmdError(
        "EXEC_ERROR",
        'chrome.debugger API unavailable (requires "debugger" permission)',
      );
    }

    // 1. Find the backendNodeId of the file input
    const target = { tabId: tab.id };
    let attached = false;
    try {
      await chrome.debugger.attach(target, "1.3");
      attached = true;
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      // Cannot attach when already occupied by another debugger
      throw cmdError("EXEC_ERROR", `failed to attach debugger: ${msg}`);
    }

    try {
      await chrome.debugger.sendCommand(target, "DOM.enable");
      const doc = await chrome.debugger.sendCommand(target, "DOM.getDocument", {
        depth: -1,
        pierce: true,
      });
      const node = await chrome.debugger.sendCommand(
        target,
        "DOM.querySelector",
        {
          nodeId: doc.root.nodeId,
          selector: String(selector),
        },
      );
      if (!node || !node.nodeId) {
        throw cmdError("ELEMENT_NOT_FOUND", `element not found: ${selector}`);
      }
      await chrome.debugger.sendCommand(target, "DOM.setFileInputFiles", {
        files: [String(file_path)],
        nodeId: node.nodeId,
      });
      return { ok: true, selector, file_path };
    } finally {
      if (attached) {
        try {
          await chrome.debugger.detach(target);
        } catch (e) {
          // Ignore detach failure
        }
      }
    }
  }

  // ---------------- Internal utilities ----------------

  _requireSelector(selector) {
    if (!selector || !String(selector).trim()) {
      throw cmdError("EXEC_ERROR", "selector is required");
    }
  }

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

  async _exec(tabId, func, args) {
    return this._execInWorld(tabId, func, args, "ISOLATED");
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

function queryFn(selector, all) {
  const toInfo = (el) => ({
    tag: el.tagName ? el.tagName.toLowerCase() : null,
    text: (el.innerText || el.textContent || "").trim().slice(0, 500),
    value: el.value ?? null,
    id: el.id || null,
    class: el.className || null,
  });
  if (all) {
    const nodes = Array.from(document.querySelectorAll(selector));
    return { count: nodes.length, items: nodes.map(toInfo) };
  }
  const el = document.querySelector(selector);
  return el ? toInfo(el) : null;
}

function getTextFn(selector) {
  const el = document.querySelector(selector);
  if (!el) return null;
  return (el.innerText || el.textContent || "").trim();
}

function getHtmlFn(selector) {
  const el = document.querySelector(selector);
  if (!el) return null;
  return el.innerHTML;
}

function clickFn(selector) {
  const el = document.querySelector(selector);
  if (!el) return false;
  el.scrollIntoView({ block: "center" });
  el.click();
  return true;
}

function typeFn(selector, text, clear) {
  const el = document.querySelector(selector);
  if (!el) return false;
  el.focus();
  if (clear) {
    el.value = "";
  }
  // Compatible with React/Vue and other controlled components: use the native setter and then dispatch an input event
  const proto =
    el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (setter) {
    setter.call(el, clear ? text : (el.value || "") + text);
  } else {
    el.value = clear ? text : (el.value || "") + text;
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function hoverFn(selector) {
  const el = document.querySelector(selector);
  if (!el) return false;
  el.scrollIntoView({ block: "center" });
  const rect = el.getBoundingClientRect();
  const opts = {
    bubbles: true,
    cancelable: true,
    clientX: rect.left + rect.width / 2,
    clientY: rect.top + rect.height / 2,
  };
  el.dispatchEvent(new MouseEvent("mouseover", opts));
  el.dispatchEvent(new MouseEvent("mouseenter", opts));
  el.dispatchEvent(new MouseEvent("mousemove", opts));
  return true;
}

function selectFn(selector, value) {
  const el = document.querySelector(selector);
  if (!el) return false;
  el.value = value;
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

async function waitForFn(selector, state, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  const check = () => {
    const el = document.querySelector(selector);
    if (state === "hidden") return !el || !isVisible(el);
    if (state === "attached") return !!el;
    return !!el && isVisible(el);
  };
  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return (
      rect.width > 0 &&
      rect.height > 0 &&
      style.visibility !== "hidden" &&
      style.display !== "none"
    );
  };
  while (Date.now() < deadline) {
    if (check()) return true;
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
}

function pressKeyFn(selector, key) {
  let el = null;
  if (selector) {
    el = document.querySelector(selector);
    if (!el) return { ok: false, error: "element not found" };
    el.focus();
  } else {
    el = document.activeElement || document.body;
  }

  const target = el || document.body;
  const opts = {
    key,
    code: key,
    bubbles: true,
    cancelable: true,
  };
  // keyCode/which for common keys, compatible with pages that rely on legacy properties
  const legacy = {
    Enter: 13,
    Escape: 27,
    Tab: 9,
    Backspace: 8,
    Delete: 46,
    ArrowUp: 38,
    ArrowDown: 40,
    ArrowLeft: 37,
    ArrowRight: 39,
    " ": 32,
  };
  if (legacy[key] != null) {
    opts.keyCode = legacy[key];
    opts.which = legacy[key];
  }

  const down = new KeyboardEvent("keydown", opts);
  const press = new KeyboardEvent("keypress", opts);
  const up = new KeyboardEvent("keyup", opts);
  target.dispatchEvent(down);
  target.dispatchEvent(press);
  target.dispatchEvent(up);

  // When Enter is inside a form input, try to submit the form (the browser default behavior is not triggered by synthetic events)
  if (
    key === "Enter" &&
    el &&
    el.form &&
    typeof el.form.requestSubmit === "function"
  ) {
    try {
      el.form.requestSubmit();
    } catch (e) {
      // Ignore: some forms do not support requestSubmit
    }
  }

  return {
    ok: true,
    key,
    target: target.tagName ? target.tagName.toLowerCase() : null,
  };
}

function scrollFn(selector, x, y, behavior) {
  if (selector) {
    const el = document.querySelector(selector);
    if (!el) return { ok: false, error: "element not found" };
    el.scrollIntoView({ behavior, block: "center" });
  } else {
    window.scrollBy({ left: x, top: y, behavior });
  }
  return {
    ok: true,
    scroll_x: window.scrollX,
    scroll_y: window.scrollY,
    page_height: document.documentElement.scrollHeight,
    viewport_height: window.innerHeight,
  };
}

function getComputedStyleFn(selector, props) {
  const el = document.querySelector(selector);
  if (!el) return null;
  const cs = window.getComputedStyle(el);
  const out = {};
  for (const prop of props) {
    out[prop] = cs.getPropertyValue(prop);
  }
  return out;
}

function executeFn(code) {
  try {
    // Note: new Function in the page context is restricted by the page CSP's unsafe-eval,
    // so script.execute executes in the MAIN world by default (see execute()).
    // Supports three forms: expression (e.g. "1+1"), statement block (e.g. "const x=1; return x;"),
    // and a statement block with return — all wrapped in an async function, allowing await.
    const src = String(code);
    const fn = new Function(
      '"use strict";return (async () => {' + src + "\n})();",
    );
    let value;
    try {
      value = fn();
    } catch (e) {
      // When statement block parsing fails, fall back to evaluating as an expression
      const exprFn = new Function('"use strict";return (' + src + ");");
      value = exprFn();
    }
    return Promise.resolve(value)
      .then((v) => ({ ok: true, value: safeSerialize(v) }))
      .catch((e) => ({ ok: false, error: (e && e.message) || String(e) }));
  } catch (e) {
    return { ok: false, error: (e && e.message) || String(e) };
  }

  function safeSerialize(v) {
    if (v === undefined) return null;
    if (v === null) return null;
    const t = typeof v;
    if (t === "string" || t === "number" || t === "boolean") return v;
    try {
      return JSON.parse(JSON.stringify(v));
    } catch (e) {
      return String(v);
    }
  }
}
