// In-page content script.
//
// Responsibility: responds to page metadata requests (haijunbot_page_info) from the background.
//
// Notes:
// - DOM operations are performed by the background via chrome.scripting.executeScript injection.
// - Login session Token is read by the background via chrome.scripting.executeScript({ world: "MAIN" })
//   directly in the main world from window.__haijunbotAuthBridge.
//   Dynamically inserting an inline script to bridge the main world from the content script is not possible:
//   in MV3, such an approach is blocked by the page CSP (script-src without unsafe-inline), so the script will not execute.
(function () {
  if (window.__haijunbotContentScriptLoaded) return;
  window.__haijunbotContentScriptLoaded = true;

  // Leave a marker on the DOM: the isolated world and the page main world share the DOM,
  // so the main world can diagnose injection status via document.documentElement.dataset.haijunbotCsLoaded.
  try {
    document.documentElement.dataset.haijunbotCsLoaded = String(Date.now());
  } catch (e) {
    // Ignore when DOM is not yet available
  }

  // Marker for locally installed extension: the page uses this to hide the "Install browser extension" guide button.
  // The marker is written to the DOM (not localStorage) for these reasons:
  // - The isolated world and the page share the DOM, so the page can read it directly;
  // - It is automatically rebuilt on page refresh, and disappears when the user uninstalls the extension, requiring no cleanup logic.
  // Note: This marker means "the extension is installed locally" and is unrelated to "whether the extension is online / connected to a gateway",
  // so it does not cause the desktop online status to affect mobile devices that do not have the extension installed.
  try {
    document.documentElement.dataset.haijunbotExtInstalled = "1";
    const manifest = chrome.runtime.getManifest();
    if (manifest && manifest.version) {
      document.documentElement.dataset.haijunbotExtVersion = String(
        manifest.version,
      );
    }
  } catch (e) {
    // Ignore when extension context is invalidated
  }

  // Report that the content script has been injected, for background-side diagnostics
  try {
    chrome.runtime.sendMessage({
      type: "haijunbot_cs_loaded",
      url: location.href,
    });
  } catch (e) {
    // Ignore when extension context is invalidated
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || !message.type) {
      return false;
    }

    // Page metadata request
    if (message.type === "haijunbot_page_info") {
      try {
        sendResponse({
          success: true,
          data: {
            url: location.href,
            title: document.title,
            ready_state: document.readyState,
          },
        });
      } catch (e) {
        sendResponse({ success: false, error: String(e) });
      }
      return true;
    }

    return false;
  });
})();
