// Clipboard executor: writes "gateway static files" or "directly provided content" to the system clipboard of the front-end page.
//
// Why read and write are in two separate places:
// - Read file: fetch in background (service worker), which supports cross-origin requests and the extension's host_permissions;
// - Write clipboard: navigator.clipboard is unavailable in service workers; it must be injected into the **page context** to execute,
//   and requires the document to actually have focus (user gesture / real focus), otherwise it throws NotAllowedError: Document is not focused.
//
// Therefore, this executor's flow is: background fetches bytes -> injects into page to write clipboard.
//
// Note: The injected functions (writeFromUrlFn / writeFn) must be self-contained and cannot reference any variables from this module's scope.

import { cmdError } from "../command_router.js";

// Path prefix for the gateway static files directory (used when validating relative path completion).
const UPLOADS_PATH = "/uploads/";

export class ClipboardExecutor {
  /**
   * Read file content from a URL and write it to the page clipboard (general interface).
   *
   * Topology note: the Agent may run on the master or any sub-node, so **which address to read is decided by the caller**.
   * Simply pass a full absolute URL (e.g. "https://<node-gateway>/uploads/xxx.png"),
   * and it works for both master/sub-node scenarios; the extension does not guess addresses.
   *
   * @param {object} p
   *   url      Required, file address. Supports two forms:
   *              - Absolute URL (recommended), e.g. "https://<gateway>/uploads/xxx.png";
   *              - Relative path, e.g. "/uploads/xxx.png" — completed using the currently connected gateway (or the first configured one if not connected).
   *   as       Optional, 'blob' (default, binary, suitable for images) | 'text' (text)
   *   mime     Optional, overrides the MIME type when as='blob' (defaults to the response content-type)
   *   tab_id   Optional, target tab (defaults to the current active tab)
   * @returns {Promise<{ok:boolean, url:string, mime:string|null, size:number, mode:string}>}
   */
  async writeFromUrl({ url, as, mime, tab_id }) {
    const raw = String(url || "").trim();
    if (!raw) throw cmdError("CLIPBOARD_INVALID", "url is required");

    const target = await this._resolveUrl(raw);
    const mode = as === "text" ? "text" : "blob";

    let resp;
    try {
      resp = await fetch(target, { credentials: "omit" });
    } catch (e) {
      throw cmdError(
        "CLIPBOARD_FETCH_FAILED",
        e && e.message ? e.message : String(e),
      );
    }
    if (!resp.ok) {
      throw cmdError(
        "CLIPBOARD_FETCH_FAILED",
        `HTTP ${resp.status} for ${target}`,
      );
    }

    const contentType = mime || resp.headers.get("content-type") || "";
    const buf = await resp.arrayBuffer();
    const bytes = new Uint8Array(buf);

    // Convert to base64 to pass to the page (although ArrayBuffer is structured-cloneable, base64 is more robust and consistent across injection).
    let b64 = "";
    const CHUNK = 0x8000;
    for (let i = 0; i < bytes.length; i += CHUNK) {
      b64 += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
    }
    b64 = btoa(b64);

    const tab = await this._resolveTab(tab_id);

    let results;
    try {
      results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        world: "MAIN",
        func: writeFromUrlFn,
        args: [b64, contentType, mode],
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
      const reason = (out && out.error) || "clipboard write failed";
      throw cmdError("CLIPBOARD_WRITE_FAILED", reason);
    }

    return {
      ok: true,
      url: target,
      mime: contentType || null,
      size: bytes.length,
      mode,
      tab_id: tab.id,
    };
  }

  /**
   * Directly write the given content to the page clipboard (without going through the gateway).
   *
   * @param {object} p
   *   text     Optional, the text to write (required when as='text')
   *   base64   Optional, the binary content to write (base64, required when as='blob')
   *   mime     Optional, the MIME type when as='blob' (default: image/png)
   *   as       Optional, 'text' | 'blob' (default: text if text is present, otherwise blob)
   *   tab_id   Optional, target tab (defaults to the current active tab)
   */
  async write({ text, base64, mime, as, tab_id }) {
    const mode =
      as === "text" || (as == null && text != null) ? "text" : "blob";

    if (mode === "text") {
      if (text == null)
        throw cmdError("CLIPBOARD_INVALID", "text is required when as='text'");
    } else if (!base64) {
      throw cmdError("CLIPBOARD_INVALID", "base64 is required when as='blob'");
    }

    const tab = await this._resolveTab(tab_id);
    const payload = mode === "text" ? String(text) : String(base64);
    const contentType = mime || "image/png";

    let results;
    try {
      results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        world: "MAIN",
        func: writeFromUrlFn,
        args: [payload, contentType, mode],
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
      throw cmdError(
        "CLIPBOARD_WRITE_FAILED",
        (out && out.error) || "clipboard write failed",
      );
    }

    return {
      ok: true,
      mode,
      mime: mode === "blob" ? contentType : null,
      tab_id: tab.id,
    };
  }

  /**
   * Resolve the file URL.
   * - Absolute URL: use directly (no host whitelist restriction; the caller is responsible for address trustworthiness);
   * - Relative path: complete using the first configured gateway.
   *
   * Note: Relative paths are just a convenient notation under a single gateway. When the Agent runs on a sub-node or similar scenario,
   * please pass the full absolute URL to avoid completing to an unintended gateway.
   */
  async _resolveUrl(raw) {
    if (raw.startsWith("/")) {
      if (!raw.startsWith(UPLOADS_PATH)) {
        throw cmdError(
          "CLIPBOARD_INVALID",
          `Relative paths only support the ${UPLOADS_PATH} prefix: ${raw}`,
        );
      }
      const gateways = await this._loadGateways();
      if (!gateways.length) {
        throw cmdError(
          "CLIPBOARD_NO_GATEWAY",
          "No gateway configured; cannot complete relative path. Please pass a full URL or configure a gateway in the extension first",
        );
      }
      return gateways[0] + raw;
    }

    if (!/^https?:\/\//i.test(raw)) {
      throw cmdError("CLIPBOARD_INVALID", `url must be an http/https address: ${raw}`);
    }
    return raw;
  }

/** Read the list of configured gateway addresses (normalized: strip trailing slashes). */
  async _loadGateways() {
    const cfg = await chrome.storage.local.get(["gateways"]);
    const list = Array.isArray(cfg.gateways) ? cfg.gateways : [];
    return list
      .map((g) =>
        String(g || "")
          .trim()
          .replace(/\/+$/, ""),
      )
      .filter((g) => /^https?:\/\//i.test(g));
  }

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
 * Function injected into the page's main world (must be self-contained).
 *
 * payload semantics vary by mode:
 *   mode='text' -> payload is the text to write
 *   mode='blob' -> payload is base64-encoded binary content, mime is its MIME type
 *
 * @param {string} payload
 * @param {string} mime
 * @param {string} mode 'text' | 'blob'
 * @returns {Promise<{ok:boolean, error?:string, size?:number}>}
 */
async function writeFromUrlFn(payload, mime, mode) {
  try {
    if (!navigator.clipboard) {
      return { ok: false, error: "navigator.clipboard is not available" };
    }
    if (!document.hasFocus()) {
      return {
        ok: false,
        error:
          "Document is not focused; please activate the tab and dispatch a real click before writing to the clipboard",
      };
    }

    if (mode === "text") {
      await navigator.clipboard.writeText(payload);
      return { ok: true, size: payload.length };
    }

    if (typeof ClipboardItem !== "function") {
      return { ok: false, error: "ClipboardItem is not available" };
    }

    const bin = atob(payload);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const blob = new Blob([bytes], {
      type: mime || "application/octet-stream",
    });

    await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
    return { ok: true, size: blob.size };
  } catch (e) {
    return { ok: false, error: e && e.message ? e.message : String(e) };
  }
}
