// Popup logic: manages connections to multiple gateways, displays each gateway's status, and provides high-risk action confirmation UI.
//
// Note: The Token is not manually filled in by the user; the extension automatically reuses the login session from the HaijunBot web page already logged into in the browser.

const els = {
  gateway: document.getElementById("gateway"),
  connectBtn: document.getElementById("connectBtn"),
  gwList: document.getElementById("gwList"),
  confirmBox: document.getElementById("confirmBox"),
  confirmDesc: document.getElementById("confirmDesc"),
  confirmYes: document.getElementById("confirmYes"),
  confirmNo: document.getElementById("confirmNo"),
  logBox: document.getElementById("logBox"),
  clearLogBtn: document.getElementById("clearLogBtn"),
  // Script management (Tampermonkey-like)
  scriptName: document.getElementById("scriptName"),
  scriptSource: document.getElementById("scriptSource"),
  scriptFile: document.getElementById("scriptFile"),
  scriptInstallBtn: document.getElementById("scriptInstallBtn"),
  scriptUrl: document.getElementById("scriptUrl"),
  scriptInstallUrlBtn: document.getElementById("scriptInstallUrlBtn"),
  scriptList: document.getElementById("scriptList"),
  // Gateway allow/block list
  gfMode: document.getElementById("gfMode"),
  gfPatterns: document.getElementById("gfPatterns"),
  gfSaveBtn: document.getElementById("gfSaveBtn"),
};

/** Append a diagnostic log entry to the popup panel (also output to console). */
function log(message) {
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  const line = `[${time}] ${message}`;
  console.log("[HaijunBot popup]", message);
  if (!els.logBox) return;
  const div = document.createElement("div");
  div.className = "log-line";
  div.textContent = line;
  els.logBox.appendChild(div);
  els.logBox.scrollTop = els.logBox.scrollHeight;
}

const STATE_TEXT = {
  connected: "Connected",
  connecting: "Connecting…",
  disconnected: "Disconnected",
};

/** Escape HTML to prevent injection from special characters in gateway addresses. */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Render the gateway list. */
function renderGateways(list) {
  const items = Array.isArray(list) ? list : [];
  if (items.length === 0) {
    els.gwList.innerHTML = '<div class="hint">No gateways have been added yet.</div>';
    return;
  }

  els.gwList.innerHTML = items
    .map((gw) => {
      const state = gw.state || "disconnected";
      const stateText = STATE_TEXT[state] || state;
      const authText = gw.has_token ? "Session: obtained" : "Session: not obtained";
      const sessionText = gw.session_id
        ? `session: ${escapeHtml(gw.session_id)}`
        : "";
      const safeGateway = escapeHtml(gw.gateway);
      const isConnected = state === "connected" || state === "connecting";
      return `
        <div class="gw-item">
          <div class="gw-head">
            <span class="dot ${state}"></span>
            <span class="gw-url">${safeGateway}</span>
          </div>
          <div class="gw-meta hint">
            ${stateText} · ${authText}${sessionText ? " · " + sessionText : ""}
          </div>
          <div class="gw-actions">
            <button class="mini" data-action="connect" data-gateway="${safeGateway}" ${
              isConnected ? "disabled" : ""
            }>Connect</button>
            <button class="mini secondary" data-action="disconnect" data-gateway="${safeGateway}" ${
              isConnected ? "" : "disabled"
            }>Disconnect</button>
            <button class="mini secondary" data-action="remove" data-gateway="${safeGateway}">Remove</button>
          </div>
        </div>
      `;
    })
    .join("");
}

/** Query the current status of all gateways from the background. */
async function refreshStatus() {
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "haijunbot_get_status",
    });
    if (resp && resp.success) {
      renderGateways(resp.gateways);
      const list = Array.isArray(resp.gateways) ? resp.gateways : [];
      if (list.length === 0) {
        log("Status refresh: no gateways");
      } else {
        for (const gw of list) {
          log(
            `Status refresh: ${gw.gateway} state=${gw.state} has_token=${gw.has_token}`,
          );
        }
      }
    } else {
      log("Status refresh failed: background did not respond");
    }
  } catch (e) {
    log(`Status refresh error: ${(e && e.message) || String(e)}`);
    renderGateways([]);
  }
}

/** Add and connect a gateway. */
async function connect() {
  const gateway = els.gateway.value.trim();
  if (!gateway) {
    alert("Please enter the gateway address");
    return;
  }
  log(`Connection request: ${gateway}`);
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "haijunbot_connect",
      gateway,
    });
    if (resp && !resp.success) {
      log(`Connection failed: ${resp.error || "Unknown error"}`);
      alert("Connection failed: " + (resp.error || "Unknown error"));
    } else {
      log("Connection request sent to background");
    }
  } catch (e) {
    log(`Error sending message: ${(e && e.message) || String(e)}`);
    console.error("[HaijunBot] connect failed", e);
  }
  els.gateway.value = "";
  // Wait a moment before refreshing status to give the connection time to establish
  setTimeout(refreshStatus, 800);
}

/** Execute an action on a specified gateway. */
async function gatewayAction(action, gateway) {
  try {
    if (action === "connect") {
      await chrome.runtime.sendMessage({ type: "haijunbot_connect", gateway });
    } else if (action === "disconnect") {
      await chrome.runtime.sendMessage({ type: "haijunbot_disconnect", gateway });
    } else if (action === "remove") {
      await chrome.runtime.sendMessage({
        type: "haijunbot_remove_gateway",
        gateway,
      });
    }
  } catch (e) {
    console.error("[HaijunBot] gateway action failed", action, e);
  }
  setTimeout(refreshStatus, 500);
}

// ---------------- High-risk action confirmation (placeholder implementation) ----------------
//
// Note: The current version has not yet integrated real high-risk action interception.
// In the future, the background will send a confirmation request to the popup before executing a high-risk action,
// and the user will click "Allow/Deny" to proceed or abort.

function showConfirm(desc) {
  els.confirmDesc.textContent =
    desc || "The Agent is requesting to perform an action that may cause irreversible consequences.";
  els.confirmBox.classList.add("show");
}

function hideConfirm() {
  els.confirmBox.classList.remove("show");
}

// ---------------- Script management (Tampermonkey-like) ----------------
//
// Convention with the background: send { type: "haijunbot_script_*", ... },
// receive a result envelope { success, data, error }, where data is the return value from ScriptManager.

/** Render the list of installed scripts. */
function renderScripts(list) {
  const items = Array.isArray(list) ? list : [];
  if (items.length === 0) {
    els.scriptList.innerHTML =
      '<div class="hint">No scripts installed yet. You can paste the script source code and click "Install Script".</div>';
    return;
  }

  els.scriptList.innerHTML = items
    .map((s) => {
      const enabled = s.enabled !== false;
      const stateClass = enabled ? "connected" : "disconnected";
      const stateText = enabled ? "Enabled" : "Disabled";
      const safeName = escapeHtml(s.name || "");
      const safeId = escapeHtml(s.id || "");
      const safeVersion = escapeHtml(s.version || "0.0.0");
      const safeDesc = escapeHtml(s.description || "");
      const matchText =
        Array.isArray(s.match) && s.match.length
          ? escapeHtml(s.match.join(", "))
          : "";
      const sizeText =
        typeof s.source_size === "number" ? `${s.source_size} bytes` : "";
      const metaParts = [safeVersion, stateText];
      if (matchText) metaParts.push(matchText);
      if (sizeText) metaParts.push(sizeText);
      return `
        <div class="gw-item">
          <div class="gw-head">
            <span class="dot ${stateClass}"></span>
            <span class="gw-url">${safeName}</span>
          </div>
          <div class="gw-meta hint">${metaParts.join(" · ")}</div>
          ${safeDesc ? `<div class="gw-meta hint">${safeDesc}</div>` : ""}
          <div class="gw-actions">
            <button class="mini" data-script-action="${
              enabled ? "disable" : "enable"
            }" data-script-id="${safeId}">${enabled ? "Disable" : "Enable"}</button>
            <button class="mini secondary" data-script-action="view" data-script-id="${safeId}">View Source</button>
            <button class="mini secondary" data-script-action="export" data-script-id="${safeId}">Export</button>
            <button class="mini secondary" data-script-action="uninstall" data-script-id="${safeId}">Uninstall</button>
          </div>
        </div>
      `;
    })
    .join("");
}

/** Query installed scripts from the background and render them. */
async function refreshScripts() {
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "haijunbot_script_list",
    });
    if (resp && resp.success) {
      renderScripts(resp.data);
      const list = Array.isArray(resp.data) ? resp.data : [];
      log(`Script list refreshed: ${list.length} entries`);
    } else {
      log(`Script list refresh failed: ${(resp && resp.error) || "background did not respond"}`);
      renderScripts([]);
    }
  } catch (e) {
    log(`Script list refresh error: ${(e && e.message) || String(e)}`);
    renderScripts([]);
  }
}

/** Install a script (from input box / selected file content). */
async function installScript() {
  const name = els.scriptName.value.trim();
  const source = els.scriptSource.value;
  if (!name) {
    alert("Please enter the script name");
    return;
  }
  if (!source || !source.trim()) {
    alert("Please paste the script source code or select a local .js file");
    return;
  }
  log(`Install script request: ${name}`);
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "haijunbot_script_install",
      name,
      source,
      description: "",
      match: [],
      version: "1.0.0",
    });
    if (resp && resp.success) {
      log(`Script installed successfully: ${name}`);
      els.scriptName.value = "";
      els.scriptSource.value = "";
      els.scriptFile.value = "";
    } else {
      const err = (resp && resp.error) || "Unknown error";
      log(`Script install failed: ${err}`);
      alert("Install failed: " + err);
    }
  } catch (e) {
    log(`Script install error: ${(e && e.message) || String(e)}`);
  }
  refreshScripts();
}

/**
 * Install a script from a URL.
 *
 * The source code is fetched by the background; the popup does not touch the source code;
 * URL validity (protocol, internal network addresses) is validated by the background's url_guard.
 */
async function installScriptFromUrl() {
  const url = els.scriptUrl.value.trim();
  if (!url) {
    alert("Please enter the script URL");
    return;
  }
  const name = els.scriptName.value.trim();
  log(`Install script from URL request: ${url}`);
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "haijunbot_script_install_from_url",
      url,
      name,
      description: "",
      match: [],
      version: "1.0.0",
    });
    if (resp && resp.success) {
      const installed = (resp.data && resp.data.name) || name || url;
      log(`Script installed from URL: ${installed}`);
      els.scriptUrl.value = "";
      els.scriptName.value = "";
      els.scriptSource.value = "";
      els.scriptFile.value = "";
    } else {
      const err = (resp && resp.error) || "Unknown error";
      log(`Install from URL failed: ${err}`);
      alert("Install from URL failed: " + err);
    }
  } catch (e) {
    log(`Install from URL error: ${(e && e.message) || String(e)}`);
  }
  refreshScripts();
}

/**
 * Export a script as a .js file (browser download), for easy sharing with others.
 * @param {string} id Script ID
 */
async function exportScript(id) {
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "haijunbot_script_export",
      id,
    });
    if (!resp || !resp.success || !resp.data) {
      log(`Script export failed: ${(resp && resp.error) || "Unknown error"}`);
      alert("Export failed: " + ((resp && resp.error) || "Unknown error"));
      return;
    }
    const { filename, content } = resp.data;
    // Use Blob + a[download] to trigger download (works in popup, no extra permissions needed)
    const blob = new Blob([content || ""], {
      type: "text/javascript;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "script.js";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    log(`Script exported: ${filename}`);
  } catch (e) {
    log(`Script export error: ${(e && e.message) || String(e)}`);
  }
}

/** Execute an action on a specified script: enable / disable / view / export / uninstall. */
async function scriptAction(action, id) {
  try {
    if (action === "enable" || action === "disable") {
      const resp = await chrome.runtime.sendMessage({
        type: "haijunbot_script_set_enabled",
        id,
        enabled: action === "enable",
      });
      if (resp && resp.success) {
        log(`Script ${action === "enable" ? "enabled" : "disabled"}: ${id}`);
      } else {
        log(`Script enable/disable failed: ${(resp && resp.error) || "Unknown error"}`);
      }
    } else if (action === "view") {
      const resp = await chrome.runtime.sendMessage({
        type: "haijunbot_script_get",
        id,
      });
      if (resp && resp.success && resp.data) {
        els.scriptSource.value = resp.data.source || "";
        els.scriptName.value = resp.data.name || "";
        log(`Script source loaded: ${resp.data.name || id}`);
      } else {
        log(`Failed to read script source: ${(resp && resp.error) || "Unknown error"}`);
      }
      return; // No need to refresh list when viewing source
    } else if (action === "export") {
      await exportScript(id);
      return; // No need to refresh list when exporting
    } else if (action === "uninstall") {
      const resp = await chrome.runtime.sendMessage({
        type: "haijunbot_script_uninstall",
        id,
      });
      if (resp && resp.success) {
        log(`Script uninstalled: ${id}`);
      } else {
        log(`Script uninstall failed: ${(resp && resp.error) || "Unknown error"}`);
      }
    }
  } catch (e) {
    log(`Script action error: ${(e && e.message) || String(e)}`);
  }
  refreshScripts();
}

// ---------------- Gateway allow/block list ----------------
//
// Convention with the background: { type: "haijunbot_get_gateway_filter" } returns
// { success, mode, patterns }; { type: "haijunbot_set_gateway_filter", mode, patterns }
// saves and returns the actual values after saving. Configuration is stored in the gateway_filter key in chrome.storage.local.

/** Read the list from the background and populate the form. */
async function refreshGatewayFilter() {
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "haijunbot_get_gateway_filter",
    });
    if (resp && resp.success) {
      els.gfMode.value = resp.mode || "off";
      els.gfPatterns.value = Array.isArray(resp.patterns)
        ? resp.patterns.join("\n")
        : "";
      log(`List loaded: mode=${resp.mode || "off"}`);
    } else {
      log(`List load failed: ${(resp && resp.error) || "background did not respond"}`);
    }
  } catch (e) {
    log(`List load error: ${(e && e.message) || String(e)}`);
  }
}

/** Save the form content to the background (one pattern per line, ignoring empty lines). */
async function saveGatewayFilter() {
  const mode = els.gfMode.value;
  const patterns = String(els.gfPatterns.value || "")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  try {
    const resp = await chrome.runtime.sendMessage({
      type: "haijunbot_set_gateway_filter",
      mode,
      patterns,
    });
    if (resp && resp.success) {
      log(`List saved: mode=${resp.mode}, ${resp.patterns.length} rules total`);
    } else {
      const err = (resp && resp.error) || "Unknown error";
      log(`List save failed: ${err}`);
      alert("Save failed: " + err);
    }
  } catch (e) {
    log(`List save error: ${(e && e.message) || String(e)}`);
  }
}

els.connectBtn.addEventListener("click", connect);
els.confirmYes.addEventListener("click", () => hideConfirm());
els.confirmNo.addEventListener("click", () => hideConfirm());
els.clearLogBtn.addEventListener("click", () => {
  if (els.logBox) els.logBox.innerHTML = "";
});

// Gateway list button events (event delegation)
els.gwList.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-action]");
  if (!btn) return;
  gatewayAction(btn.dataset.action, btn.dataset.gateway);
});

// Script management: install button
els.scriptInstallBtn.addEventListener("click", installScript);

// Gateway allow/block list: save button
els.gfSaveBtn.addEventListener("click", saveGatewayFilter);

// Script management: install from URL button
els.scriptInstallUrlBtn.addEventListener("click", installScriptFromUrl);

// Script management: after selecting a local .js file, fill the source code box
els.scriptFile.addEventListener("change", (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    els.scriptSource.value = String(reader.result || "");
    if (!els.scriptName.value.trim()) {
      // When no name is entered, use the filename (without extension) as the default script name
      els.scriptName.value = file.name.replace(/\.js$/i, "");
    }
    log(`Local script file read: ${file.name}`);
  };
  reader.onerror = () => log(`Failed to read local script file: ${file.name}`);
  reader.readAsText(file);
});

// Script list button events (event delegation)
els.scriptList.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-script-action]");
  if (!btn) return;
  scriptAction(btn.dataset.scriptAction, btn.dataset.scriptId);
});

// Listen for state change broadcasts from the background
chrome.runtime.onMessage.addListener((message) => {
  if (message && message.type === "haijunbot_state") {
    log("Received state broadcast");
    renderGateways(message.gateways);
  }
  if (message && message.type === "haijunbot_confirm") {
    showConfirm(message.description);
  }
  return false;
});

// Initialization
log("Popup opened, starting status query");
refreshStatus();
refreshScripts();
refreshGatewayFilter();
