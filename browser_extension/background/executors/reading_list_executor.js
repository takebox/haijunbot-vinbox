// Reading list executor: wraps chrome.readingList operations.
import { cmdError } from "../command_router.js";

export class ReadingListExecutor {
  /** List reading list entries. */
  async list() {
    this._ensureSupported();
    const entries = await chrome.readingList.query({});
    return entries.map((e) => this._toItem(e));
  }

  /** Add an entry to the reading list. */
  async add({ url, title, has_been_read } = {}) {
    this._ensureSupported();
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    await chrome.readingList.addEntry({
      url: String(url),
      title: title || String(url),
      hasBeenRead: Boolean(has_been_read),
    });
    return { ok: true, url: String(url) };
  }

  /** Remove an entry from the reading list (irreversible). */
  async remove({ url } = {}) {
    this._ensureSupported();
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    await chrome.readingList.removeEntry({ url: String(url) });
    return { ok: true, url: String(url) };
  }

  /** Update an entry's read status or title. */
  async update({ url, has_been_read, title } = {}) {
    this._ensureSupported();
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    const info = { url: String(url) };
    if (has_been_read != null) info.hasBeenRead = Boolean(has_been_read);
    if (title) info.title = String(title);
    await chrome.readingList.updateEntry(info);
    return { ok: true, url: String(url) };
  }

  /** Check if the API is available (only supported in Chrome 120+). */
  _ensureSupported() {
    if (!chrome.readingList) {
      throw cmdError("NOT_SUPPORTED", "chrome.readingList is not available");
    }
  }

  /** Convert a reading list entry to the external structure. */
  _toItem(entry) {
    return {
      url: entry.url ?? "",
      title: entry.title ?? "",
      has_been_read: Boolean(entry.hasBeenRead),
      creation_time: entry.creationTime ?? null,
      last_update_time: entry.lastUpdateTime ?? null,
    };
  }
}
