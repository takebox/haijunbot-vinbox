// Capture executor: screenshots, etc.

import { cmdError } from "../command_router.js";

export class CaptureExecutor {
  /**
   * Capture a specified tab.
   * - Normal screenshot: captures the current viewport as PNG, uploads to the command's origin gateway, and returns the full accessible URL.
   * - Full-page screenshot: stitches by scrolling, then uploads and returns { url, width, height, full_page }.
   *
   * Design rationale: if screenshot base64 is returned directly to the Agent, it would bloat the LLM context. Therefore, the extension
   * uploads the screenshot to "the gateway where the Agent that invoked this command resides" (= command origin gateway, see ctx),
   * which saves it and returns a URL path. The Agent then loads the image via add_images.
   */
  async screenshot({ tab_id, full_page }, ctx = {}) {
    const tab = await this._resolveTab(tab_id);
    try {
      if (full_page) {
        const shot = await this._captureFullPage(tab);
        const url = await this._uploadToGateway(shot.image, ctx);
        return { url, width: shot.width, height: shot.height, full_page: true };
      }
      const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, {
        format: "png",
      });
      const image = this._strip(dataUrl);
      return await this._uploadToGateway(image, ctx);
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      if (/Cannot access|chrome:\/\//i.test(msg)) {
        throw cmdError("PROTECTED_PAGE", msg);
      }
      throw cmdError("EXEC_ERROR", msg);
    }
  }
  /**
   * Upload screenshot base64 to the /upload endpoint of the command's origin gateway, returning the full accessible URL.
   *
   * Reuses the gateway's existing /upload endpoint (_handle_file_upload): receives { file_name, file_data },
   * automatically generates a unique filename, saves it to the gateway's uploads directory, and returns a relative URL /uploads/xxx.png.
   * The extension then prepends the command's origin gateway address to get a full URL that is always reachable by the Agent.
   *
   * @param {string} imageBase64 Base64 of the PNG (without the data: prefix)
   * @param {object} ctx Execution context, containing gateway and token
   * @returns {Promise<string>} Full accessible image URL
   */
  async _uploadToGateway(imageBase64, ctx = {}) {
    const gateway = String(ctx.gateway || "").trim();
    if (!gateway) {
      throw cmdError(
        "NO_GATEWAY",
        "Missing command origin gateway address; unable to upload screenshot. Please issue capture.screenshot via the gateway.",
      );
    }
    const token = String(ctx.token || "").trim();
    const url = `${gateway}/api/node/master/upload`;
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({
        file_name: "screenshot.png",
        file_data: imageBase64,
      }),
    });
    let body = null;
    try {
      body = await resp.json();
    } catch (e) {
      body = null;
    }
    if (!resp.ok || !body || !body.success) {
      const errMsg =
        (body && (body.error || body.detail)) ||
        `HTTP ${resp.status}`;
      throw cmdError(
        "UPLOAD_FAILED",
        `Failed to upload screenshot to gateway (${gateway}): ${
          typeof errMsg === "string" ? errMsg : JSON.stringify(errMsg)
        }`,
      );
    }
    const fileUrl = body.data && body.data.file_url;
    if (!fileUrl) {
      throw cmdError("UPLOAD_FAILED", "Gateway did not return screenshot URL");
    }
    // /upload returns a relative URL (/uploads/xxx.png); prepend the command origin gateway to get the full URL.
    // The gateway is the Agent's master_url gateway, which the Agent accesses via this address, so the URL is always reachable.
    return `${gateway}${String(fileUrl).startsWith("/") ? "" : "/"}${fileUrl}`;
  }

  /**
   * Full-page screenshot: captures the viewport screen by screen via scrolling, then stitches them on an offscreen canvas.
   * The tab must be active (captureVisibleTab can only capture the currently visible tab).
   */
  async _captureFullPage(tab) {
    const tabId = tab.id;

    // 1. Read page dimensions and current scroll position
    const metrics = await this._exec(tabId, () => {
      const doc = document.documentElement;
      const body = document.body;
      const width = Math.max(
        doc ? doc.scrollWidth : 0,
        body ? body.scrollWidth : 0,
        doc ? doc.clientWidth : 0,
      );
      const height = Math.max(
        doc ? doc.scrollHeight : 0,
        body ? body.scrollHeight : 0,
        doc ? doc.clientHeight : 0,
      );
      return {
        width,
        height,
        viewport_width: window.innerWidth,
        viewport_height: window.innerHeight,
        scroll_x: window.scrollX,
        scroll_y: window.scrollY,
      };
    });

    const pageWidth = Math.max(1, Math.floor(metrics.width));
    const pageHeight = Math.max(1, Math.floor(metrics.height));
    const viewportWidth = Math.max(1, Math.floor(metrics.viewport_width));
    const viewportHeight = Math.max(1, Math.floor(metrics.viewport_height));

    // If the page fits in a single screen, just capture once
    if (pageHeight <= viewportHeight) {
      const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, {
        format: "png",
      });
      return {
        image: this._strip(dataUrl),
        width: viewportWidth,
        height: viewportHeight,
        full_page: true,
      };
    }

    // 2. Scroll and capture screen by screen
    const shots = [];
    const maxShots = 50; // Safety cap to avoid infinite loops on extremely long pages
    let y = 0;
    let guard = 0;
    while (y < pageHeight && guard < maxShots) {
      guard += 1;
      await this._exec(
        tabId,
        (top) => {
          window.scrollTo(0, top);
        },
        [y],
      );
      // Wait for rendering to stabilize
      await new Promise((r) => setTimeout(r, 120));
      const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, {
        format: "png",
      });
      shots.push({ y, image: this._strip(dataUrl) });
      y += viewportHeight;
    }

    // 3. Restore original scroll position
    await this._exec(
      tabId,
      (pos) => {
        window.scrollTo(pos.x, pos.y);
      },
      [{ x: metrics.scroll_x, y: metrics.scroll_y }],
    );

    // 4. Stitch (using OffscreenCanvas in the extension page context)
    const merged = await this._stitch(
      shots,
      pageWidth,
      pageHeight,
      viewportWidth,
    );
    return {
      image: merged,
      width: pageWidth,
      height: pageHeight,
      full_page: true,
    };
  }

  /** Stitch multiple PNGs using OffscreenCanvas in the extension context. */
  async _stitch(shots, pageWidth, pageHeight, viewportWidth) {
    const canvas = new OffscreenCanvas(pageWidth, pageHeight);
    const ctx = canvas.getContext("2d");
    for (const shot of shots) {
      const blob = await (
        await fetch(`data:image/png;base64,${shot.image}`)
      ).blob();
      const bitmap = await createImageBitmap(blob);
      const drawWidth = Math.min(viewportWidth, pageWidth);
      ctx.drawImage(
        bitmap,
        0,
        0,
        drawWidth,
        bitmap.height,
        0,
        shot.y,
        drawWidth,
        bitmap.height,
      );
      bitmap.close();
    }
    const outBlob = await canvas.convertToBlob({ type: "image/png" });
    const buf = await outBlob.arrayBuffer();
    return this._bytesToBase64(new Uint8Array(buf));
  }

  /** Execute a function in the main world of the specified tab and return the result. */
  async _exec(tabId, func, args = []) {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func,
      args,
      world: "MAIN",
    });
    return results && results[0] ? results[0].result : null;
  }

  _bytesToBase64(bytes) {
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  _strip(dataUrl) {
    if (typeof dataUrl !== "string") return null;
    const idx = dataUrl.indexOf(",");
    return idx >= 0 ? dataUrl.slice(idx + 1) : dataUrl;
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
}
