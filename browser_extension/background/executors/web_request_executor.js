// Network rules executor: manages network interception/redirection rules based on declarativeNetRequest.
//
// ⚠️ Highly sensitive permission: can intercept, block, or redirect the user's network requests.
// In MV3, chrome.webRequest can no longer block requests; blocking is provided solely by declarativeNetRequest;
// dynamic rules require the declarativeNetRequest permission in the manifest (this extension has declared webRequest;
// to make it effective, add the declarativeNetRequest permission and host permissions).
// register actually affects the user's browsing, making it a high-risk operation. Always confirm with the user before calling.
import { cmdError } from "../command_router.js";

export class WebRequestExecutor {
  /** List currently registered dynamic rules. */
  async listRules() {
    this._ensureSupported();
    const rules = await chrome.declarativeNetRequest.getDynamicRules();
    return rules.map((r) => this._toRule(r));
  }

  /**
   * Register a dynamic rule (highly sensitive).
   * Requires rule_id, url_filter; optional action_type (block/allow/redirect), redirect_url, priority.
   */
  async registerRule({
    rule_id,
    url_filter,
    action_type,
    redirect_url,
    priority,
  } = {}) {
    this._ensureSupported();
    if (rule_id == null) throw cmdError("NO_ID", "rule_id is required");
    if (!url_filter) throw cmdError("EXEC_ERROR", "url_filter is required");
    const type = action_type ? String(action_type) : "block";
    const action = { type };
    if (type === "redirect") {
      if (!redirect_url) {
        throw cmdError(
          "EXEC_ERROR",
          "redirect_url is required for redirect action",
        );
      }
      action.redirect = { url: String(redirect_url) };
    }
    const rule = {
      id: Number(rule_id),
      priority: priority != null ? Number(priority) : 1,
      action,
      condition: { urlFilter: String(url_filter) },
    };
    await chrome.declarativeNetRequest.updateDynamicRules({
      addRules: [rule],
      removeRuleIds: [Number(rule_id)],
    });
    return { ok: true, rule_id: Number(rule_id) };
  }

  /** Unregister a specified dynamic rule. */
  async unregisterRule({ rule_id } = {}) {
    this._ensureSupported();
    if (rule_id == null) throw cmdError("NO_ID", "rule_id is required");
    await chrome.declarativeNetRequest.updateDynamicRules({
      removeRuleIds: [Number(rule_id)],
    });
    return { ok: true, rule_id: Number(rule_id) };
  }

  /** Check if the API is available. */
  _ensureSupported() {
    if (!chrome.declarativeNetRequest) {
      throw cmdError(
        "NOT_SUPPORTED",
        "chrome.declarativeNetRequest is not available; add the declarativeNetRequest permission",
      );
    }
  }

  /** Convert a chrome rule to the external structure. */
  _toRule(rule) {
    return {
      rule_id: rule.id ?? null,
      priority: rule.priority ?? 1,
      action_type: rule.action?.type ?? "",
      redirect_url: rule.action?.redirect?.url ?? null,
      url_filter: rule.condition?.urlFilter ?? "",
    };
  }
}
