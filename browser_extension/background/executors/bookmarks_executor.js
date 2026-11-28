// Bookmarks executor: wraps chrome.bookmarks operations.
import { cmdError } from "../command_router.js";

export class BookmarksExecutor {
  /**
   * List bookmarks.
   * Returns the full bookmark tree by default; when parent_id is provided, returns only the direct children of that folder.
   */
  async list({ parent_id } = {}) {
    if (parent_id != null) {
      const children = await chrome.bookmarks.getChildren(String(parent_id));
      return children.map((n) => this._toNode(n));
    }
    const tree = await chrome.bookmarks.getTree();
    return tree.map((n) => this._toNode(n, true));
  }

  /** Search bookmarks by title or URL keyword. */
  async search({ query, max_results } = {}) {
    if (!query) throw cmdError("EXEC_ERROR", "query is required");
    const nodes = await chrome.bookmarks.search(String(query));
    const limited =
      max_results != null ? nodes.slice(0, Number(max_results)) : nodes;
    return limited.map((n) => this._toNode(n));
  }

  /**
   * Add a bookmark.
   * When parent_id is empty, it is placed under "Other Bookmarks" (id "2") by default.
   */
  async create({ title, url, parent_id } = {}) {
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    const node = await chrome.bookmarks.create({
      title: title || url,
      url: String(url),
      parentId: parent_id != null ? String(parent_id) : undefined,
    });
    return { ok: true, bookmark: this._toNode(node) };
  }

  /** Delete a single bookmark (irreversible). */
  async remove({ id } = {}) {
    if (id == null) throw cmdError("NO_ID", "id is required");
    await chrome.bookmarks.remove(String(id));
    return { ok: true, id: String(id) };
  }

  /** Delete a bookmark folder and all its children (irreversible). */
  async removeTree({ id } = {}) {
    if (id == null) throw cmdError("NO_ID", "id is required");
    await chrome.bookmarks.removeTree(String(id));
    return { ok: true, id: String(id) };
  }

  /** Convert a chrome bookmark node to the external structure; recursively expands when with_children is true. */
  _toNode(node, with_children = false) {
    const out = {
      id: node.id,
      parent_id: node.parentId ?? null,
      title: node.title ?? "",
      url: node.url ?? null,
      date_added: node.dateAdded ?? null,
      is_folder: node.url == null,
    };
    if (with_children && Array.isArray(node.children)) {
      out.children = node.children.map((c) => this._toNode(c, true));
    }
    return out;
  }
}
