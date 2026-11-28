// Privacy settings executor: wraps chrome.privacy operations.
//
// ⚠️ Highly sensitive permission: can modify browser privacy-related toggles (such as whether third-party cookies are allowed,
// whether Safe Browsing is enabled, whether statistics can be sent, etc.). set actually changes the user's privacy configuration,
// making it a high-risk operation. Always confirm with the user before calling.
import { cmdError } from "../command_router.js";

export class PrivacyExecutor {
  /**
   * Read privacy settings.
   * Requires area (network/services/websites) and name (setting name, e.g. networkPredictionEnabled).
   */
  async get({ area, name } = {}) {
    const setting = this._resolveSetting(area, name);
    const result = await setting.get({});
    return {
      area: String(area),
      name: String(name),
      value: result.value ?? null,
      level_of_control: result.levelOfControl ?? "",
    };
  }

  /** Modify privacy settings (highly sensitive). */
  async set({ area, name, value } = {}) {
    const setting = this._resolveSetting(area, name);
    if (value === undefined) throw cmdError("EXEC_ERROR", "value is required");
    await setting.set({ value, scope: "regular" });
    return { ok: true, area: String(area), name: String(name), value };
  }

  /** Resolve the chrome.privacy setting object for the given area/name. */
  _resolveSetting(area, name) {
    if (!chrome.privacy) {
      throw cmdError("NOT_SUPPORTED", "chrome.privacy is not available");
    }
    if (!area) throw cmdError("EXEC_ERROR", "area is required");
    if (!name) throw cmdError("EXEC_ERROR", "name is required");
    const group = chrome.privacy[String(area)];
    if (!group) {
      throw cmdError("EXEC_ERROR", `unknown privacy area: ${area}`);
    }
    const setting = group[String(name)];
    if (!setting || typeof setting.set !== "function") {
      throw cmdError("EXEC_ERROR", `unknown privacy setting: ${area}.${name}`);
    }
    return setting;
  }
}
