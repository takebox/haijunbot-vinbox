// Favicon executor: wraps chrome.favicon operations.
import { cmdError } from "../command_router.js";

export class FaviconExecutor {
  /** Get the favicon URL for a given page. */
  async getUrl({ page_url, size } = {}) {
    if (!chrome.favicon) {
      throw cmdError("NOT_SUPPORTED", "chrome.favicon is not available");
    }
    if (!page_url) throw cmdError("EXEC_ERROR", "page_url is required");
    const options = { pageUrl: String(page_url) };
    if (size != null) options.size = Number(size);
    const url = await chrome.favicon.getUrl(options);
    return { ok: true, favicon_url: url ?? null };
  }
}
