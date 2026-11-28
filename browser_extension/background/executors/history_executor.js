// History executor: wraps chrome.history operations.
import { cmdError } from "../command_router.js";

export class HistoryExecutor {
  /**
   * Query history records.
   * Parameters: query (keyword, optional), start_time / end_time (millisecond timestamps, optional),
   *             max_results (default 100).
   */
  async search({ query, start_time, end_time, max_results } = {}) {
    const detail = {
      text: query ? String(query) : "",
      startTime: start_time != null ? Number(start_time) : 0,
      endTime: end_time != null ? Number(end_time) : Date.now(),
      maxResults: max_results != null ? Number(max_results) : 100,
    };
    const items = await chrome.history.search(detail);
    return items.map((h) => this._toItem(h));
  }

  /** Retrieve the most recent history entries in descending order of visit time. */
  async recent({ max_results } = {}) {
    const items = await chrome.history.search({
      text: "",
      startTime: 0,
      endTime: Date.now(),
      maxResults: max_results != null ? Number(max_results) : 50,
    });
    items.sort((a, b) => (b.lastVisitTime || 0) - (a.lastVisitTime || 0));
    return items.map((h) => this._toItem(h));
  }

  /** Delete all history records for a specific URL (irreversible). */
  async remove({ url } = {}) {
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    await chrome.history.deleteUrl({ url: String(url) });
    return { ok: true, url: String(url) };
  }

  /** Delete history records within a time range (irreversible); clears all history if no time range is provided. */
  async removeRange({ start_time, end_time } = {}) {
    const range = {
      startTime: start_time != null ? Number(start_time) : 0,
      endTime: end_time != null ? Number(end_time) : Date.now(),
    };
    await chrome.history.deleteRange(range);
    return { ok: true, ...range };
  }

  /** Convert a chrome history item to the external structure. */
  _toItem(item) {
    return {
      id: item.id ?? null,
      url: item.url ?? null,
      title: item.title ?? "",
      last_visit_time: item.lastVisitTime ?? null,
      visit_count: item.visitCount ?? 0,
      typed_count: item.typedCount ?? 0,
    };
  }
}
