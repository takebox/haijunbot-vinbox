// Search executor: wraps chrome.search operations.
import { cmdError } from "../command_router.js";

export class SearchExecutor {
  /**
   * Perform a search using the browser's default search engine.
   * Parameters: query (search term, required), tab_id (optional, opens in the specified tab), disposition (optional).
   */
  async query({ query, tab_id, disposition } = {}) {
    if (!chrome.search) {
      throw cmdError("NOT_SUPPORTED", "chrome.search is not available");
    }
    if (!query) throw cmdError("EXEC_ERROR", "query is required");
    const options = { text: String(query) };
    if (tab_id != null) options.tabId = Number(tab_id);
    if (disposition) options.disposition = String(disposition);
    await chrome.search.query(options);
    return { ok: true, query: String(query) };
  }
}
