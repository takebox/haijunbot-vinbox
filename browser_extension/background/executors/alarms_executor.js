// Alarms executor: wraps chrome.alarms operations.
import { cmdError } from "../command_router.js";

export class AlarmsExecutor {
  /**
   * Create a scheduled task.
   * Supports delay_minutes (one-time delayed trigger) or period_minutes (periodic trigger); at least one is required.
   */
  async create({ name, delay_minutes, period_minutes } = {}) {
    if (!name) throw cmdError("EXEC_ERROR", "name is required");
    if (delay_minutes == null && period_minutes == null) {
      throw cmdError(
        "EXEC_ERROR",
        "delay_minutes or period_minutes is required",
      );
    }
    const info = { name: String(name) };
    if (delay_minutes != null) info.delayInMinutes = Number(delay_minutes);
    if (period_minutes != null) info.periodInMinutes = Number(period_minutes);
    await chrome.alarms.create(String(name), info);
    return { ok: true, name: String(name) };
  }

  /** List all scheduled tasks. */
  async list() {
    const alarms = await chrome.alarms.getAll();
    return alarms.map((a) => ({
      name: a.name ?? "",
      scheduled_time: a.scheduledTime ?? null,
      period_in_minutes: a.periodInMinutes ?? null,
    }));
  }

  /** Clear a specific scheduled task. */
  async clear({ name } = {}) {
    if (!name) throw cmdError("EXEC_ERROR", "name is required");
    const removed = await chrome.alarms.clear(String(name));
    return { ok: true, name: String(name), removed: Boolean(removed) };
  }

  /** Clear all scheduled tasks. */
  async clearAll() {
    const removed = await chrome.alarms.clearAll();
    return { ok: true, removed: Boolean(removed) };
  }
}
