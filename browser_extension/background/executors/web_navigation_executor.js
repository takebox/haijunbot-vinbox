// Web navigation executor: wraps chrome.webNavigation operations (read-only queries, no interception).
import { cmdError } from "../command_router.js";

export class WebNavigationExecutor {
  /** List all frames of a specified tab. */
  async getAllFrames({ tab_id } = {}) {
    if (tab_id == null) throw cmdError("NO_TAB", "tab_id is required");
    const frames = await chrome.webNavigation.getAllFrames({
      tabId: Number(tab_id),
    });
    return (frames || []).map((f) => this._toFrame(f));
  }

  /** Get information about a specified frame. */
  async getFrame({ tab_id, frame_id } = {}) {
    if (tab_id == null) throw cmdError("NO_TAB", "tab_id is required");
    if (frame_id == null) throw cmdError("NO_ID", "frame_id is required");
    const frame = await chrome.webNavigation.getFrame({
      tabId: Number(tab_id),
      frameId: Number(frame_id),
    });
    return this._toFrame(frame);
  }

  /** Convert a chrome frame to the external structure. */
  _toFrame(frame) {
    if (!frame) return null;
    return {
      frame_id: frame.frameId ?? null,
      parent_frame_id: frame.parentFrameId ?? null,
      url: frame.url ?? "",
      document_id: frame.documentId ?? null,
      error_occurred: Boolean(frame.errorOccurred),
    };
  }
}
