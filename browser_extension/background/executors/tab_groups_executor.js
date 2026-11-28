// Tab groups executor: wraps chrome.tabGroups operations.
import { cmdError } from "../command_router.js";

export class TabGroupsExecutor {
  /** List all tab groups. */
  async list() {
    this._ensureSupported();
    const groups = await chrome.tabGroups.query({});
    return groups.map((g) => this._toGroup(g));
  }

  /** Get a specific tab group. */
  async get({ group_id } = {}) {
    this._ensureSupported();
    if (group_id == null) throw cmdError("NO_ID", "group_id is required");
    const group = await chrome.tabGroups.get(Number(group_id));
    return this._toGroup(group);
  }

  /** Query tab groups by criteria (e.g. title, color, window_id). */
  async query({ title, color, window_id } = {}) {
    this._ensureSupported();
    const info = {};
    if (title) info.title = String(title);
    if (color) info.color = String(color);
    if (window_id != null) info.windowId = Number(window_id);
    const groups = await chrome.tabGroups.query(info);
    return groups.map((g) => this._toGroup(g));
  }

  /** Update tab group properties (title, color, collapsed state). */
  async update({ group_id, title, color, collapsed } = {}) {
    this._ensureSupported();
    if (group_id == null) throw cmdError("NO_ID", "group_id is required");
    const props = {};
    if (title) props.title = String(title);
    if (color) props.color = String(color);
    if (collapsed != null) props.collapsed = Boolean(collapsed);
    const group = await chrome.tabGroups.update(Number(group_id), props);
    return { ok: true, group: this._toGroup(group) };
  }

  /** Check if the API is available. */
  _ensureSupported() {
    if (!chrome.tabGroups) {
      throw cmdError("NOT_SUPPORTED", "chrome.tabGroups is not available");
    }
  }

  /** Convert a chrome tab group to the external structure. */
  _toGroup(group) {
    return {
      group_id: group.id ?? null,
      title: group.title ?? "",
      color: group.color ?? "",
      collapsed: Boolean(group.collapsed),
      window_id: group.windowId ?? null,
    };
  }
}
