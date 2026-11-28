// Proxy executor: wraps chrome.proxy operations.
//
// ⚠️ Highly sensitive permission: can modify the browser's global proxy settings, effectively hijacking all of the user's network traffic.
// set/clear actually changes the user's internet configuration, making it a high-risk operation. Always confirm with the user before calling.
import { cmdError } from "../command_router.js";

export class ProxyExecutor {
  /** Read the current proxy configuration. */
  async getSettings() {
    this._ensureSupported();
    const config = await chrome.proxy.settings.get({});
    return {
      level_of_control: config.levelOfControl ?? "",
      value: config.value ?? null,
    };
  }

  /**
   * Set proxy (highly sensitive).
   * Requires mode (direct/auto_detect/pac_script/system/fixed_servers);
   * when mode is pac_script, pac_url is required; when fixed_servers, rules are required.
   */
  async setSettings({ mode, pac_url, rules } = {}) {
    this._ensureSupported();
    if (!mode) throw cmdError("EXEC_ERROR", "mode is required");
    const value = { mode: String(mode) };
    if (mode === "pac_script") {
      if (!pac_url)
        throw cmdError("EXEC_ERROR", "pac_url is required for pac_script mode");
      value.pacScript = { url: String(pac_url) };
    }
    if (mode === "fixed_servers") {
      if (!rules)
        throw cmdError(
          "EXEC_ERROR",
          "rules is required for fixed_servers mode",
        );
      value.rules = rules;
    }
    await chrome.proxy.settings.set({ value, scope: "regular" });
    return { ok: true, mode: String(mode) };
  }

  /** Clear proxy configuration and restore system defaults. */
  async clearSettings() {
    this._ensureSupported();
    await chrome.proxy.settings.clear({ scope: "regular" });
    return { ok: true };
  }

  /** Check if the API is available. */
  _ensureSupported() {
    if (!chrome.proxy) {
      throw cmdError("NOT_SUPPORTED", "chrome.proxy is not available");
    }
  }
}
