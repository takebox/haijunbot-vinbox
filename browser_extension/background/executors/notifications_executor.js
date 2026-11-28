// Notifications executor: wraps chrome.notifications operations.
import { cmdError } from "../command_router.js";

export class NotificationsExecutor {
  /** Create a system notification. */
  async create({ notification_id, title, message, icon_url } = {}) {
    if (!notification_id)
      throw cmdError("NO_ID", "notification_id is required");
    if (!title) throw cmdError("EXEC_ERROR", "title is required");
    const options = {
      type: "basic",
      title: String(title),
      message: message ? String(message) : "",
      iconUrl: icon_url || "icons/icon128.png",
    };
    const id = await chrome.notifications.create(
      String(notification_id),
      options,
    );
    return { ok: true, notification_id: id };
  }

  /** Clear a specific notification. */
  async clear({ notification_id } = {}) {
    if (!notification_id)
      throw cmdError("NO_ID", "notification_id is required");
    const cleared = await chrome.notifications.clear(String(notification_id));
    return { ok: true, notification_id: String(notification_id), cleared };
  }

  /** Clear all notifications. */
  async clearAll() {
    await chrome.notifications.getAll().then(async (all) => {
      await Promise.all(
        Object.keys(all || {}).map((id) => chrome.notifications.clear(id)),
      );
    });
    return { ok: true };
  }

  /** List currently displayed notifications. */
  async getAll() {
    const all = await chrome.notifications.getAll();
    return Object.entries(all || {}).map(([id, options]) => ({
      notification_id: id,
      title: options?.title ?? "",
      message: options?.message ?? "",
      type: options?.type ?? "",
    }));
  }
}
