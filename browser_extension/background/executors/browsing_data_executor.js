// Browsing data executor: wraps chrome.browsingData operations.
//
// ⚠️ Highly sensitive permission: can clear the user's browsing history, cache, cookies, passwords, form data, etc.
// remove is an irreversible operation; once executed, data cannot be recovered. Always confirm with the user before calling.
import { cmdError } from "../command_router.js";

export class BrowsingDataExecutor {
  /** Query removable data types (whether each type has data). */
  async settings() {
    this._ensureSupported();
    const result = await chrome.browsingData.settings();
    return {
      options: result.options ?? {},
      data_to_remove: result.dataToRemove ?? {},
      data_removal_permitted: Boolean(result.dataRemovalPermitted),
    };
  }

  /**
   * Clear browsing data (highly sensitive, irreversible).
   * Requires data_types (array, e.g. ["cache","cookies","history","downloads","formData",
   * "passwords","serviceWorkers","localStorage"]);
   * Optional since (millisecond timestamp; if omitted, all data is cleared).
   */
  async remove({ data_types, since } = {}) {
    this._ensureSupported();
    if (!Array.isArray(data_types) || !data_types.length) {
      throw cmdError("EXEC_ERROR", "data_types is required (non-empty array)");
    }
    const options = {};
    data_types.forEach((t) => {
      options[String(t)] = true;
    });
    const removalOptions = {};
    if (since != null) removalOptions.since = Number(since);
    await chrome.browsingData.remove(removalOptions, options);
    return {
      ok: true,
      data_types: data_types.map(String),
      since: since ?? null,
    };
  }

  /** Check if the API is available. */
  _ensureSupported() {
    if (!chrome.browsingData) {
      throw cmdError("NOT_SUPPORTED", "chrome.browsingData is not available");
    }
  }
}
