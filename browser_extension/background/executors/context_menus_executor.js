// Context menus executor: wraps chrome.contextMenus operations.
// Note: contextMenus are triggered by the user's right-click. This executor only handles registration, querying, and removal of menu items.
import { cmdError } from "../command_router.js";

export class ContextMenusExecutor {
  /** Create a context menu item. */
  async create({ menu_id, title, contexts, url_patterns } = {}) {
    if (!menu_id) throw cmdError("NO_ID", "menu_id is required");
    if (!title) throw cmdError("EXEC_ERROR", "title is required");
    const createProps = {
      id: String(menu_id),
      title: String(title),
      contexts:
        Array.isArray(contexts) && contexts.length ? contexts : ["page"],
    };
    if (Array.isArray(url_patterns) && url_patterns.length) {
      createProps.documentUrlPatterns = url_patterns;
    }
    chrome.contextMenus.create(createProps);
    return { ok: true, menu_id: String(menu_id) };
  }

  /** Remove a specific menu item. */
  async remove({ menu_id } = {}) {
    if (!menu_id) throw cmdError("NO_ID", "menu_id is required");
    await chrome.contextMenus.remove(String(menu_id));
    return { ok: true, menu_id: String(menu_id) };
  }

  /** Remove all menu items. */
  async removeAll() {
    await chrome.contextMenus.removeAll();
    return { ok: true };
  }

  /** List currently registered menu items. */
  async list() {
    // contextMenus has no direct listing API; items can only be removed via removeAll. Returning an informational result here.
    return {
      ok: true,
      note: "chrome.contextMenus does not provide a listing API; only create/remove/removeAll are supported",
    };
  }
}
