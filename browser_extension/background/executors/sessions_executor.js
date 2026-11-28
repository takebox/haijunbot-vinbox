// Sessions executor: wraps chrome.sessions operations (recently closed tabs/windows).
import { cmdError } from "../command_router.js";

export class SessionsExecutor {
  /** List recently closed tabs and windows. Optional max_results (default 25). */
  async recent({ max_results } = {}) {
    const sessions = await chrome.sessions.getRecentlyClosed({
      maxResults: max_results != null ? Number(max_results) : 25,
    });
    return sessions.map((s) => this._toItem(s));
  }

  /**
   * Restore a specified session item.
   * When session_id is empty, restores the most recently closed tab/window.
   */
  async restore({ session_id } = {}) {
    const session = await chrome.sessions.restore(
      session_id ? String(session_id) : undefined,
    );
    return { ok: true, session: this._toItem(session) };
  }

  /** Convert a chrome session item to the external structure. */
  _toItem(session) {
    if (!session) return null;
    const tab = session.tab
      ? {
          tab_id: session.tab.id ?? null,
          url: session.tab.url ?? "",
          title: session.tab.title ?? "",
        }
      : null;
    const win = session.window
      ? {
          window_id: session.window.id ?? null,
          tabs: session.window.tabs?.length ?? 0,
        }
      : null;
    return {
      session_id: session.tab?.sessionId ?? session.window?.sessionId ?? null,
      last_modified: session.lastModified ?? null,
      tab,
      window: win,
    };
  }
}
