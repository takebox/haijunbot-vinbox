// Cookies executor: wraps chrome.cookies operations.
//
// ⚠️ Highly sensitive permission: cookies are equivalent to login credentials. Reading or modifying cookies may lead to account impersonation.
// set/remove actually changes the user's login session and is an irreversible operation. Always confirm with the user before calling.
import { cmdError } from "../command_router.js";

export class CookiesExecutor {
  /** Read a single cookie under the specified URL. */
  async get({ url, name } = {}) {
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    if (!name) throw cmdError("EXEC_ERROR", "name is required");
    const cookie = await chrome.cookies.get({
      url: String(url),
      name: String(name),
    });
    return cookie ? this._toCookie(cookie) : null;
  }

  /** Read all cookies under the specified URL or domain. */
  async getAll({ url, domain } = {}) {
    if (!url && !domain) {
      throw cmdError("EXEC_ERROR", "url or domain is required");
    }
    const query = {};
    if (url) query.url = String(url);
    if (domain) query.domain = String(domain);
    const cookies = await chrome.cookies.getAll(query);
    return cookies.map((c) => this._toCookie(c));
  }

  /**
   * Write a cookie (highly sensitive; actually changes the login session).
   * Requires url, name, value; optional domain/path/secure/http_only/same_site/expiration_date.
   */
  async set({
    url,
    name,
    value,
    domain,
    path,
    secure,
    http_only,
    same_site,
    expiration_date,
  } = {}) {
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    if (!name) throw cmdError("EXEC_ERROR", "name is required");
    const details = {
      url: String(url),
      name: String(name),
      value: value != null ? String(value) : "",
    };
    if (domain) details.domain = String(domain);
    if (path) details.path = String(path);
    if (secure != null) details.secure = Boolean(secure);
    if (http_only != null) details.httpOnly = Boolean(http_only);
    if (same_site) details.sameSite = String(same_site);
    if (expiration_date != null)
      details.expirationDate = Number(expiration_date);
    const cookie = await chrome.cookies.set(details);
    return { ok: true, cookie: cookie ? this._toCookie(cookie) : null };
  }

  /** Delete a cookie (highly sensitive, irreversible). */
  async remove({ url, name } = {}) {
    if (!url) throw cmdError("EXEC_ERROR", "url is required");
    if (!name) throw cmdError("EXEC_ERROR", "name is required");
    const result = await chrome.cookies.remove({
      url: String(url),
      name: String(name),
    });
    return { ok: Boolean(result), url: String(url), name: String(name) };
  }

  /** Convert a chrome cookie to the external structure. */
  _toCookie(cookie) {
    return {
      name: cookie.name ?? "",
      value: cookie.value ?? "",
      domain: cookie.domain ?? "",
      path: cookie.path ?? "",
      secure: Boolean(cookie.secure),
      http_only: Boolean(cookie.httpOnly),
      same_site: cookie.sameSite ?? "",
      session: Boolean(cookie.session),
      expiration_date: cookie.expirationDate ?? null,
      host_only: Boolean(cookie.hostOnly),
    };
  }
}
