// Script repository (Tampermonkey-like): manages user-installed custom page scripts.
//
// Script definition: a piece of JS that can be executed in the page's "main world"; after evaluation it should yield a script object:
//   {
//     name: "mysite",
//     description: "Site-specific document operations",
//     version: "1.0.0",
//     match: ["example.com"],           // Applicable domains (hint only, no enforcement)
//     actions: {
//       getEditor: { desc: "Get editor instance", run: () => {...} },
//       deleteRange: { desc: "Delete text", params: {start:"number",end:"number"},
//                      run: ({start,end}) => {...} },
//     },
//   }
//
// Compatible with two export styles:
//   (a) Define variables at top level then `module.exports = {...}` or `globalThis.__HAIJUNBOT_SCRIPT__ = {...}`;
//   (b) Directly `globalThis.__HAIJUNBOT_SCRIPT__ = {...}`.
//
// This module only handles "storage + lightweight static validation" and does not execute any scripts (see script_executor.js for execution).

import { cmdError } from "./command_router.js";
import { isAllowedScriptUrl, deriveNameFromUrl } from "./url_guard.js";

/** Key name for storing the script list in chrome.storage.local. */
const STORAGE_KEY = "scripts";

/** Size limit (in bytes) for fetching script source from URL. */
const MAX_SOURCE_BYTES = 1024 * 1024;

/** Timeout (in milliseconds) for fetching script source from URL. */
const FETCH_TIMEOUT_MS = 15000;

export class ScriptManager {
  /**
   * List metadata of installed scripts (excluding source to avoid oversized responses).
   * @returns {Promise<Array<object>>}
   */
  async list() {
    const scripts = await this._load();
    return scripts.map((s) => this._toMeta(s));
  }

  /**
   * Read a single script (including source).
   * @param {string} id Script ID
   * @returns {Promise<object>} Complete script object
   */
  async get(id) {
    if (!id) throw cmdError("SCRIPT_INVALID", "id is required");
    const scripts = await this._load();
    const found = scripts.find((s) => s.id === id);
    if (!found) throw cmdError("SCRIPT_NOT_FOUND", `script not found: ${id}`);
    return found;
  }

  /**
   * Install (or update) a script. When a script with the same name exists, overwrite it, preserving the original id and installed_at.
   * @param {object} payload { name, source, description, match, version }
   * @returns {Promise<Object>} Installed script metadata
   */
  async install({ name, source, description, match, version }) {
    const scriptName = String(name || "").trim();
    if (!scriptName) {
      throw cmdError("SCRIPT_INVALID", "name is required");
    }
    const src = typeof source === "string" ? source : "";
    if (!src.trim()) {
      throw cmdError("SCRIPT_INVALID", "source is required");
    }
    const reason = validateSource(src);
    if (reason) {
      throw cmdError("SCRIPT_INVALID", reason);
    }

    const scripts = await this._load();
    const idx = scripts.findIndex((s) => s.name === scriptName);
    const now = new Date().toISOString();
    const record = {
      id: idx >= 0 ? scripts[idx].id : genId(),
      name: scriptName,
      description: String(description || "").trim(),
      match: normalizeMatch(match),
      version: String(version || "0.0.0").trim(),
      enabled: idx >= 0 ? scripts[idx].enabled !== false : true,
      installed_at: idx >= 0 ? scripts[idx].installed_at : now,
      updated_at: now,
      source: src,
    };

    if (idx >= 0) {
      scripts[idx] = record;
    } else {
      scripts.push(record);
    }
    await this._save(scripts);
    return this._toMeta(record);
  }

  /**
   * Download script source from URL and install.
   *
   * Flow: validate URL (anti-SSRF) -> fetch text (with timeout and size limit) -> reuse validateSource for weak validation
   * -> reuse install() to persist. Downloaded content is only stored as a "source code string" and is never evaluated here.
   *
   * @param {object} payload { url, name, description, match, version }
   * @returns {Promise<Object>} Installed script metadata
   */
  async installFromUrl({ url, name, description, match, version }) {
    const raw = String(url || "").trim();
    if (!raw) {
      throw cmdError("SCRIPT_INVALID", "url is required");
    }

    const check = isAllowedScriptUrl(raw);
    if (!check.ok) {
      throw cmdError("SCRIPT_INVALID", check.reason);
    }

    const scriptName = String(name || "").trim() || deriveNameFromUrl(raw);
    if (!scriptName) {
      throw cmdError(
        "SCRIPT_INVALID",
        "cannot derive script name from url, please provide 'name'",
      );
    }

    const src = await this._fetchSource(raw);
    const reason = validateSource(src);
    if (reason) {
      throw cmdError("SCRIPT_INVALID", reason);
    }

    return this.install({
      name: scriptName,
      source: src,
      description,
      match,
      version,
    });
  }

  /**
   * Fetch script source text with timeout and size limit.
   * @param {string} url URL that has passed security validation
   * @returns {Promise<string>} Source code text
   */
  async _fetchSource(url) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    let resp;
    try {
      resp = await fetch(url, {
        credentials: "omit",
        redirect: "follow",
        signal: controller.signal,
      });
    } catch (e) {
      const msg =
        e && e.name === "AbortError" ? "request timeout" : e && e.message;
      throw cmdError("SCRIPT_FETCH_ERROR", msg || String(e));
    } finally {
      clearTimeout(timer);
    }

    if (!resp.ok) {
      throw cmdError("SCRIPT_FETCH_ERROR", `HTTP ${resp.status} for ${url}`);
    }

    // Pre-check by Content-Length to avoid downloading oversized response bodies
    const declared = Number(resp.headers.get("content-length") || 0);
    if (declared > MAX_SOURCE_BYTES) {
      throw cmdError(
        "SCRIPT_TOO_LARGE",
        `script source too large: ${declared} bytes (limit ${MAX_SOURCE_BYTES})`,
      );
    }

    const text = await resp.text();
    if (text.length > MAX_SOURCE_BYTES) {
      throw cmdError(
        "SCRIPT_TOO_LARGE",
        `script source too large: ${text.length} bytes (limit ${MAX_SOURCE_BYTES})`,
      );
    }
    if (!text.trim()) {
      throw cmdError("SCRIPT_FETCH_ERROR", `empty response body from ${url}`);
    }
    return text;
  }

  /**
   * Export a script as a shareable standalone file content.
   *
   * The produced text can be saved directly as a `.js` file and shared with others, who can install it
   * via "import from local file" or by pasting into the source box (fully consistent with the install entry format).
   *
   * File structure: metadata comment block at the top (for human reading), followed by the original script source.
   * The comment block uses `//` line comments and does not affect script evaluation.
   *
   * @param {string} id Script ID
   * @returns {Promise<object>} { filename, name, version, content }
   */
  async exportScript(id) {
    const script = await this.get(id);
    const name = String(script.name || "script").trim() || "script";
    const version = String(script.version || "0.0.0").trim();
    const description = String(script.description || "").trim();
    const match = Array.isArray(script.match) ? script.match : [];

    const headerLines = [
      "// ===== HaijunBot Script Export =====",
      `// name: ${name}`,
      `// version: ${version}`,
    ];
    if (description) headerLines.push(`// description: ${description}`);
    if (match.length) headerLines.push(`// match: ${match.join(", ")}`);
    if (script.updated_at)
      headerLines.push(`// exported_at: ${new Date().toISOString()}`);
    headerLines.push(
      "// Install: extension popup -> \"Script Management\" -> paste this file content or import from local file.",
    );
    headerLines.push("// ===========================");

    const content =
      headerLines.join("\n") + "\n\n" + String(script.source || "");
    return {
      filename: `${name}.js`,
      name,
      version,
      content,
    };
  }

  /**
   * Uninstall a script.
   * @param {string} id Script ID
   * @returns {Promise<object>} { ok: true, id }
   */
  async uninstall(id) {
    if (!id) throw cmdError("SCRIPT_INVALID", "id is required");
    const scripts = await this._load();
    const next = scripts.filter((s) => s.id !== id);
    if (next.length === scripts.length) {
      throw cmdError("SCRIPT_NOT_FOUND", `script not found: ${id}`);
    }
    await this._save(next);
    return { ok: true, id };
  }

  /**
   * Enable / disable a script.
   * @param {string} id Script ID
   * @param {boolean} enabled Whether to enable
   * @returns {Promise<object>} Updated script metadata
   */
  async setEnabled(id, enabled) {
    if (!id) throw cmdError("SCRIPT_INVALID", "id is required");
    const scripts = await this._load();
    const found = scripts.find((s) => s.id === id);
    if (!found) throw cmdError("SCRIPT_NOT_FOUND", `script not found: ${id}`);
    found.enabled = enabled !== false;
    found.updated_at = new Date().toISOString();
    await this._save(scripts);
    return this._toMeta(found);
  }

  // ---------------- Internal utilities ----------------

  /** Read script list; returns empty array when storage is corrupted. */
  async _load() {
    const cfg = await chrome.storage.local.get([STORAGE_KEY]);
    const list = cfg[STORAGE_KEY];
    return Array.isArray(list) ? list : [];
  }

  /** Write back the script list. */
  async _save(list) {
    await chrome.storage.local.set({ [STORAGE_KEY]: list });
  }

  /** Convert to metadata (strip source, keep source_size). */
  _toMeta(s) {
    return {
      id: s.id,
      name: s.name,
      description: s.description || "",
      match: Array.isArray(s.match) ? s.match : [],
      version: s.version || "0.0.0",
      enabled: s.enabled !== false,
      installed_at: s.installed_at || null,
      updated_at: s.updated_at || null,
      source_size: typeof s.source === "string" ? s.source.length : 0,
    };
  }
}

/**
 * Lightweight static validation of script source code.
 *
 * Note: `new Function(src)` **cannot** be used for syntax parsing here.
 * MV3 extension pages (popup / service worker) have CSP `script-src 'self'`,
 * which does not allow `unsafe-eval`; `new Function` will throw a CSP error directly,
 * causing all legitimate scripts to be misjudged as "syntax error" and fail to install.
 * Therefore only pure string-level static checks are performed; real syntax errors will surface
 * when `script.run` is evaluated in the page's main world (runScriptFn has try/catch fallback).
 *
 * @param {string} source Script source code
 * @returns {string|null} Error reason; returns null when validation passes
 */
export function validateSource(source) {
  const src = String(source);
  // 1) Must export a script object
  if (!src.includes("__HAIJUNBOT_SCRIPT__") && !src.includes("module.exports")) {
    return "script must export an object via globalThis.__HAIJUNBOT_SCRIPT__ or module.exports";
  }
  // 2) Must define actions
  if (!/\bactions\b/.test(src)) {
    return "script must define an 'actions' map";
  }
  // 3) Basic bracket balance check (cheaply catches obviously truncated/incomplete source)
  const reason = checkBalanced(src);
  if (reason) return reason;
  return null;
}

/**
 * Bracket balance check: ignores brackets inside strings, template literals, comments, and regex literals.
 * Only performs coarse-grained checks to catch obviously incomplete source code; does not attempt full syntax analysis.
 * @param {string} src Source code
 * @returns {string|null} Error reason; returns null when validation passes
 */
function checkBalanced(src) {
  const pairs = { ")": "(", "]": "[", "}": "{" };
  const stack = [];
  let i = 0;
  let prevSignificant = ""; // Previous significant character, used to distinguish division from regex literal
  while (i < src.length) {
    const c = src[i];
    // Line comment
    if (c === "/" && src[i + 1] === "/") {
      const nl = src.indexOf("\n", i);
      i = nl === -1 ? src.length : nl + 1;
      continue;
    }
    // Block comment
    if (c === "/" && src[i + 1] === "*") {
      const end = src.indexOf("*/", i + 2);
      i = end === -1 ? src.length : end + 2;
      continue;
    }
    // String / template literal
    if (c === '"' || c === "'" || c === "`") {
      const quote = c;
      i++;
      while (i < src.length) {
        if (src[i] === "\\") {
          i += 2;
          continue;
        }
        if (src[i] === quote) break;
        i++;
      }
      if (i >= src.length) return "unterminated string literal";
      i++;
      prevSignificant = quote;
      continue;
    }
    // Regex literal (rough detection: treated as regex when preceded by operator/start)
    if (c === "/" && /(^|[=(,:[!&|?{};+\-*%<>~^])\s*$/.test(src.slice(0, i))) {
      i++;
      let inClass = false;
      while (i < src.length) {
        if (src[i] === "\\") {
          i += 2;
          continue;
        }
        if (src[i] === "[") inClass = true;
        else if (src[i] === "]") inClass = false;
        else if (src[i] === "/" && !inClass) break;
        else if (src[i] === "\n") return "unterminated regular expression";
        i++;
      }
      i++;
      prevSignificant = "/";
      continue;
    }
    if (c === "(" || c === "[" || c === "{") {
      stack.push(c);
      prevSignificant = c;
      i++;
      continue;
    }
    if (c === ")" || c === "]" || c === "}") {
      if (stack.pop() !== pairs[c]) {
        return `unbalanced '${c}' in script source`;
      }
      prevSignificant = c;
      i++;
      continue;
    }
    if (!/\s/.test(c)) prevSignificant = c;
    i++;
  }
  if (stack.length) {
    return `unclosed '${stack[stack.length - 1]}' in script source`;
  }
  return null;
}

/** Normalize match field to an array of strings. */
function normalizeMatch(match) {
  if (Array.isArray(match)) {
    return match.map((m) => String(m).trim()).filter(Boolean);
  }
  if (typeof match === "string" && match.trim()) {
    return match
      .split(",")
      .map((m) => m.trim())
      .filter(Boolean);
  }
  return [];
}

/** Generate script ID (refer to the getClientId approach in service_worker.js). */
function genId() {
  return "s-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}
