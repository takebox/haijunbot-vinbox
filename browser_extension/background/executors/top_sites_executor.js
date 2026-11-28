// Top sites executor: wraps chrome.topSites operations.
import { cmdError } from "../command_router.js";

export class TopSitesExecutor {
  /** List the user's most frequently visited sites. */
  async list() {
    if (!chrome.topSites) {
      throw cmdError("NOT_SUPPORTED", "chrome.topSites is not available");
    }
    const sites = await chrome.topSites.get();
    return sites.map((s) => ({ title: s.title ?? "", url: s.url ?? "" }));
  }
}
