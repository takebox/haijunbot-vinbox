// URL safety guard: determines whether a URL is allowed to be actively fetched by the extension.
//
// Purpose: `script.install_from_url` downloads script source code from a URL provided by the user/Agent.
// Without restrictions, this capability could be exploited to probe internal network services (SSRF) or read local files,
// so a whitelist-style validation is applied here:
//   - Only http/https protocols are allowed (file:, ftp:, data:, etc. are blocked);
//   - Rejects loopback, private, and link-local internal addresses (both IPv4 and IPv6);
//   - Rejects localhost and its subdomains.
//
// This module **deliberately does not depend on any chrome API or other modules** so it can be directly imported by node for unit testing.

/** Allowed protocol whitelist. */
const ALLOWED_PROTOCOLS = ["http:", "https:"];

/**
 * Determines whether an IPv4 literal belongs to a "non-routable" range.
 * Covers: 0.0.0.0/8, 10/8, 127/8, 169.254/16, 172.16/12, 192.168/16.
 * @param {string} host e.g. "127.0.0.1"
 * @returns {boolean} true means it should be rejected
 */
function isBlockedIPv4(host) {
  const parts = host.split(".");
  if (parts.length !== 4) return false;
  const nums = [];
  for (const p of parts) {
    // Only accept pure decimal digits (reject non-standard notations like 0x7f.1)
    if (!/^\d{1,3}$/.test(p)) return false;
    const n = Number(p);
    if (n > 255) return false;
    nums.push(n);
  }
  const [a, b] = nums;
  if (a === 0) return true; // 0.0.0.0/8
  if (a === 10) return true; // 10.0.0.0/8
  if (a === 127) return true; // 127.0.0.0/8
  if (a === 169 && b === 254) return true; // 169.254.0.0/16
  if (a === 172 && b >= 16 && b <= 31) return true; // 172.16.0.0/12
  if (a === 192 && b === 168) return true; // 192.168.0.0/16
  return false;
}

/**
 * Determines whether an IPv6 literal belongs to a "non-routable" address.
 * Covers: ::1 (loopback), :: (unspecified), fe80::/10 (link-local), fc00::/7 (unique local).
 * @param {string} host e.g. "::1" or "[::1]" (brackets already stripped)
 * @returns {boolean} true means it should be rejected
 */
function isBlockedIPv6(host) {
  const h = host.toLowerCase().replace(/^\[|\]$/g, "");
  if (!h.includes(":")) return false;
  if (h === "::1" || h === "::" || h === "0:0:0:0:0:0:0:1") return true;
  // fe80::/10 link-local
  if (/^fe[89ab]/.test(h)) return true;
  // fc00::/7 unique local address
  if (/^f[cd]/.test(h)) return true;
  return false;
}

/**
 * Determines whether a hostname belongs to an internal / loopback / local address.
 * @param {string} hostname The hostname portion of the URL (without port)
 * @returns {boolean} true means it should be rejected
 */
function isBlockedHostname(hostname) {
  const h = String(hostname || "")
    .trim()
    .toLowerCase();
  if (!h) return true;
  // localhost and its subdomains
  if (h === "localhost" || h.endsWith(".localhost")) return true;
  // Strip IPv6 brackets before checking
  const bare = h.replace(/^\[|\]$/g, "");
  if (isBlockedIPv6(bare)) return true;
  if (isBlockedIPv4(bare)) return true;
  return false;
}

/**
 * Validates whether a script download URL is safe to use.
 *
 * @param {string} url The URL to validate
 * @returns {{ok: boolean, reason?: string}} When ok=false, reason describes why it was rejected
 */
export function isAllowedScriptUrl(url) {
  const raw = String(url || "").trim();
  if (!raw) return { ok: false, reason: "url is required" };

  let parsed;
  try {
    parsed = new URL(raw);
  } catch (e) {
    return { ok: false, reason: `invalid url: ${raw}` };
  }

  if (!ALLOWED_PROTOCOLS.includes(parsed.protocol)) {
    return {
      ok: false,
      reason: `only http/https is allowed, got: ${parsed.protocol}`,
    };
  }

  if (isBlockedHostname(parsed.hostname)) {
    return {
      ok: false,
      reason: `refusing to fetch from private/loopback host: ${parsed.hostname}`,
    };
  }

  return { ok: true };
}

/**
 * Derive a script name from a URL: takes the filename from the last segment of the pathname, stripping the .js extension.
 * Returns an empty string if it cannot be derived (the caller decides whether to raise an error).
 *
 * @param {string} url Script URL
 * @returns {string} The derived script name; empty string if it cannot be derived
 */
export function deriveNameFromUrl(url) {
  try {
    const parsed = new URL(String(url || "").trim());
    const segs = parsed.pathname.split("/").filter(Boolean);
    if (!segs.length) return "";
    const last = decodeURIComponent(segs[segs.length - 1]);
    return last.replace(/\.js$/i, "").trim();
  } catch (e) {
    return "";
  }
}
