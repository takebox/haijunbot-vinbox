// Script executor: manages installed scripts (Tampermonkey-like) and runs specified actions of scripts in the page's "main world".
//
// Two types of responsibilities:
// 1. Metadata (list/get/install/uninstall/setEnabled) — directly forwarded to ScriptManager;
// 2. Execution (run) — takes the script source code, injects it via chrome.scripting.executeScript({ world: "MAIN" })
//    to execute in the page, so it can access the page's own JS objects (e.g. site-provided editor instances).
//
// Note: The injected function runScriptFn must be self-contained (cannot reference any variables from this module's scope).

import { cmdError } from "../command_router.js";
import { ScriptManager } from "../script_manager.js";

export class ScriptExecutor {
  constructor() {
    this.manager = new ScriptManager();
  }

  /** List metadata of installed scripts. */
  async list() {
    return this.manager.list();
  }

  /** Read a single script (including source). */
  async get({ id }) {
    return this.manager.get(id);
  }

  /** Install (or update) a script. */
  async install({ name, source, description, match, version }) {
    return this.manager.install({ name, source, description, match, version });
  }

  /** Download script source from URL and install. */
  async installFromUrl({ url, name, description, match, version }) {
    return this.manager.installFromUrl({
      url,
      name,
      description,
      match,
      version,
    });
  }

  /** Uninstall a script. */
  async uninstall({ id }) {
    return this.manager.uninstall(id);
  }

  /** Export a script as a shareable standalone file content. */
  async exportScript({ id }) {
    return this.manager.exportScript(id);
  }

  /** Enable / disable a script. */
  async setEnabled({ id, enabled }) {
    return this.manager.setEnabled(id, enabled);
  }

  /**
   * Execute the specified action of a script in the main world of the target tab.
   * @param {object} p { id, action, args, tab_id }
   * @returns {Promise<object>} { ok, action, result }
   */
  async run({ id, action, args, tab_id }) {
    if (!id) {
      throw cmdError("SCRIPT_INVALID", "id is required");
    }
    if (!action || !String(action).trim()) {
      throw cmdError("SCRIPT_INVALID", "action is required");
    }

    const script = await this.manager.get(id);
    if (script.enabled === false) {
      throw cmdError("SCRIPT_DISABLED", `script disabled: ${id}`);
    }

    const tab = await this._resolveTab(tab_id);

    let results;
    try {
      results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        world: "MAIN",
        func: runScriptFn,
        args: [script.source, String(action), args ?? null],
      });
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      if (/Cannot access|chrome:\/\/|extension/i.test(msg)) {
        throw cmdError("PROTECTED_PAGE", msg);
      }
      throw cmdError("EXEC_ERROR", msg);
    }

    const out = results && results.length ? results[0].result : null;
    if (!out || !out.ok) {
      const reason = (out && out.error) || "script run failed";
      throw cmdError("SCRIPT_RUN_ERROR", reason);
    }
    return { ok: true, action: String(action), result: out.value };
  }

  // ---------------- Internal utilities ----------------

  /** Resolve the target tab: use the current window's active tab if not specified. */
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
}

/**
 * Function injected into the page's main world (must be self-contained, cannot reference external variables).
 *
 * Logic: evaluate the script source to get the script object → take actions[actionName] → call its run(args).
 *
 * @param {string} source Script source code
 * @param {string} actionName The name of the action to invoke
 * @param {object|null} args Arguments to pass to the action
 * @returns {Promise<{ok:boolean, value?:any, error?:string}>}
 */
export async function runScriptFn(source, actionName, args) {
  try {
    const src = String(source);

    // 1) Evaluate the script source to get the script object.
    //    Compatible with two export styles:
    //      (a) globalThis.__HAIJUNBOT_SCRIPT__ = {...}
    //      (b) module.exports = {...}
    //    Note: new Function scope does not have module; it must be passed explicitly as a parameter.
    const dummyModule = { exports: {} };
    let scriptObj = null;
    // Clear any global export leftover from the previous execution to avoid reading a stale script object.
    try {
      delete globalThis.__HAIJUNBOT_SCRIPT__;
    } catch (e) {
      globalThis.__HAIJUNBOT_SCRIPT__ = undefined;
    }
    try {
      const factory = new Function("module", "exports", src);
      factory(dummyModule, dummyModule.exports);
    } catch (e) {
      return { ok: false, error: (e && e.message) || String(e) };
    }

    if (dummyModule.exports && Object.keys(dummyModule.exports).length) {
      scriptObj = dummyModule.exports;
    } else if (globalThis.__HAIJUNBOT_SCRIPT__) {
      scriptObj = globalThis.__HAIJUNBOT_SCRIPT__;
    }

    if (!scriptObj || typeof scriptObj !== "object") {
      return { ok: false, error: "script did not export an object" };
    }

    // 2) Get the action entry.
    const actions = scriptObj.actions;
    if (!actions || typeof actions !== "object") {
      return { ok: false, error: "script has no 'actions' map" };
    }
    const entry = actions[actionName];
    if (!entry) {
      return { ok: false, error: `action not found: ${actionName}` };
    }

    // 3) Compatible with two styles: entry.run(args) or entry itself is a function.
    const run = typeof entry === "function" ? entry : entry.run;
    if (typeof run !== "function") {
      return {
        ok: false,
        error: `action has no runnable function: ${actionName}`,
      };
    }

    const value = await run(args || {});
    return { ok: true, value: safeSerialize(value) };
  } catch (e) {
    return { ok: false, error: (e && e.message) || String(e) };
  }

  /** Convert the return value to a JSON-serializable form. */
  function safeSerialize(v) {
    if (v === undefined || v === null) return null;
    const t = typeof v;
    if (t === "string" || t === "number" || t === "boolean") return v;
    try {
      return JSON.parse(JSON.stringify(v));
    } catch (e) {
      return String(v);
    }
  }
}
