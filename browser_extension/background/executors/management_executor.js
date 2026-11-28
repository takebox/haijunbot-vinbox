// Extension management executor: wraps chrome.management operations.
//
// ⚠️ Highly sensitive permission: can enumerate, enable/disable, or even uninstall other extensions installed by the user.
// setEnabled/uninstall actually changes the user's browser environment, making it a high-risk operation. Always confirm with the user before calling.
import { cmdError } from "../command_router.js";

export class ManagementExecutor {
  /** List all installed extensions and apps. */
  async list() {
    this._ensureSupported();
    const items = await chrome.management.getAll();
    return items.map((i) => this._toItem(i));
  }

  /** Get detailed information about a specific extension. */
  async get({ extension_id } = {}) {
    this._ensureSupported();
    if (!extension_id) throw cmdError("NO_ID", "extension_id is required");
    const item = await chrome.management.get(String(extension_id));
    return this._toItem(item);
  }

  /** Launch a specified app (only effective for types such as hosted_app). */
  async launchApp({ extension_id } = {}) {
    this._ensureSupported();
    if (!extension_id) throw cmdError("NO_ID", "extension_id is required");
    await chrome.management.launchApp(String(extension_id));
    return { ok: true, extension_id: String(extension_id) };
  }

  /** Enable/disable a specified extension (highly sensitive). */
  async setEnabled({ extension_id, enabled } = {}) {
    this._ensureSupported();
    if (!extension_id) throw cmdError("NO_ID", "extension_id is required");
    await chrome.management.setEnabled(String(extension_id), Boolean(enabled));
    return {
      ok: true,
      extension_id: String(extension_id),
      enabled: Boolean(enabled),
    };
  }

  /** Uninstall a specified extension (highly sensitive, irreversible). */
  async uninstall({ extension_id } = {}) {
    this._ensureSupported();
    if (!extension_id) throw cmdError("NO_ID", "extension_id is required");
    await chrome.management.uninstall(String(extension_id));
    return { ok: true, extension_id: String(extension_id) };
  }

  /** Check if the API is available. */
  _ensureSupported() {
    if (!chrome.management) {
      throw cmdError("NOT_SUPPORTED", "chrome.management is not available");
    }
  }

  /** Convert a chrome extension info to the external structure. */
  _toItem(item) {
    return {
      id: item.id ?? "",
      name: item.name ?? "",
      version: item.version ?? "",
      description: item.description ?? "",
      enabled: Boolean(item.enabled),
      type: item.type ?? "",
      may_disable: Boolean(item.mayDisable),
      install_type: item.installType ?? "",
      homepage_url: item.homepageUrl ?? null,
    };
  }
}
