// Content settings executor: wraps chrome.contentSettings operations.
//
// ⚠️ Highly sensitive permission: can modify site-level content permissions (cookies, JavaScript, images, popups,
// geolocation, camera/microphone, etc.). set actually changes the user's security and privacy settings,
// making it a high-risk operation. Always confirm with the user before calling.
import { cmdError } from "../command_router.js";

export class ContentSettingsExecutor {
  /**
   * Read content settings.
   * Requires content_type (e.g. cookies/javascript/images/popups/geolocation);
   * Optional primary_url, secondary_url (if omitted, returns the global default).
   */
  async get({ content_type, primary_url, secondary_url } = {}) {
    const setting = this._resolveSetting(content_type);
    const details = {};
    if (primary_url) details.primaryUrl = String(primary_url);
    if (secondary_url) details.secondaryUrl = String(secondary_url);
    const result = await setting.get(details);
    return {
      content_type: String(content_type),
      setting: result.setting ?? null,
      primary_pattern: result.primaryPattern ?? null,
      secondary_pattern: result.secondaryPattern ?? null,
    };
  }

  /** Modify content settings (highly sensitive). Requires content_type and setting (e.g. allow/block/ask). */
  async set({
    content_type,
    setting: value,
    primary_pattern,
    secondary_pattern,
  } = {}) {
    const setting = this._resolveSetting(content_type);
    if (value === undefined)
      throw cmdError("EXEC_ERROR", "setting is required");
    const details = { setting: value };
    if (primary_pattern) details.primaryPattern = String(primary_pattern);
    if (secondary_pattern) details.secondaryPattern = String(secondary_pattern);
    await setting.set(details);
    return { ok: true, content_type: String(content_type), setting: value };
  }

  /** Clear content settings and restore defaults. Requires content_type. */
  async clear({ content_type } = {}) {
    const setting = this._resolveSetting(content_type);
    await setting.clear({});
    return { ok: true, content_type: String(content_type) };
  }

  /** Resolve the chrome.contentSettings setting object for the given content_type. */
  _resolveSetting(content_type) {
    if (!chrome.contentSettings) {
      throw cmdError(
        "NOT_SUPPORTED",
        "chrome.contentSettings is not available",
      );
    }
    if (!content_type) throw cmdError("EXEC_ERROR", "content_type is required");
    const setting = chrome.contentSettings[String(content_type)];
    if (!setting || typeof setting.set !== "function") {
      throw cmdError("EXEC_ERROR", `unknown content setting: ${content_type}`);
    }
    return setting;
  }
}
