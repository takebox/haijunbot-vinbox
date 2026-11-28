// Downloads executor: wraps chrome.downloads operations.
import { cmdError } from "../command_router.js";

export class DownloadsExecutor {
  /** Query download items. Optional query (search keyword), limit (default 50). */
  async list({ query, limit } = {}) {
    const items = await chrome.downloads.search({
      query: query ? [String(query)] : undefined,
      limit: limit != null ? Number(limit) : 50,
      orderBy: ["-startTime"],
    });
    return items.map((d) => this._toItem(d));
  }

  /** Search download items by filename/URL. */
  async search({ query, limit } = {}) {
    if (!query) throw cmdError("EXEC_ERROR", "query is required");
    const items = await chrome.downloads.search({
      query: [String(query)],
      limit: limit != null ? Number(limit) : 50,
      orderBy: ["-startTime"],
    });
    return items.map((d) => this._toItem(d));
  }

  /** Start a download. */
  async download({ url, filename, save_as } = {}) {
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    const options = { url: String(url) };
    if (filename) options.filename = String(filename);
    if (save_as) options.saveAs = true;
    const downloadId = await chrome.downloads.download(options);
    return { ok: true, download_id: downloadId };
  }

  /** Pause a download. */
  async pause({ download_id } = {}) {
    const id = this._requireId(download_id);
    await chrome.downloads.pause(id);
    return { ok: true, download_id: id };
  }

  /** Resume a download. */
  async resume({ download_id } = {}) {
    const id = this._requireId(download_id);
    await chrome.downloads.resume(id);
    return { ok: true, download_id: id };
  }

  /** Cancel a download. */
  async cancel({ download_id } = {}) {
    const id = this._requireId(download_id);
    await chrome.downloads.cancel(id);
    return { ok: true, download_id: id };
  }

  /** Remove a record from the download list (irreversible; also deletes the local file when delete_file is true). */
  async erase({ download_id, delete_file } = {}) {
    const id = this._requireId(download_id);
    await chrome.downloads.erase({ id });
    if (delete_file) {
      await chrome.downloads.removeFile(id);
    }
    return { ok: true, download_id: id, file_removed: Boolean(delete_file) };
  }

  /** Open a downloaded file. */
  async open({ download_id } = {}) {
    const id = this._requireId(download_id);
    await chrome.downloads.open(id);
    return { ok: true, download_id: id };
  }

  /** Validate and return the download item ID. */
  _requireId(download_id) {
    if (download_id == null) {
      throw cmdError("NO_ID", "download_id is required");
    }
    return Number(download_id);
  }

  /** Convert a chrome download item to the external structure. */
  _toItem(item) {
    return {
      id: item.id ?? null,
      filename: item.filename ?? "",
      url: item.url ?? "",
      final_url: item.finalUrl ?? "",
      state: item.state ?? "",
      bytes_received: item.bytesReceived ?? 0,
      total_bytes: item.totalBytes ?? 0,
      paused: Boolean(item.paused),
      error: item.error ?? null,
      start_time: item.startTime ?? null,
      end_time: item.endTime ?? null,
      mime: item.mime ?? "",
      exists: item.exists ?? null,
    };
  }
}
