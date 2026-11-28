// Native messaging executor: wraps chrome.runtime.sendNativeMessage.
//
// ⚠️ Highly sensitive permission: can communicate with registered Native Messaging Hosts on the local machine,
// which is equivalent to allowing a remote Agent to indirectly invoke local programs. The user must pre-register a native host
// in the system, and the host name must be in the manifest's nativeMessaging allowlist (this extension does not fix a host;
// the caller passes it in. If the browser rejects it, the host is not registered or not authorized).
// Always confirm with the user before calling.
import { cmdError } from "../command_router.js";

export class NativeMessagingExecutor {
  /** Send a message to the specified native host and wait for a response. */
  async send({ native_host, message } = {}) {
    if (!chrome.runtime?.sendNativeMessage) {
      throw cmdError(
        "NOT_SUPPORTED",
        "chrome.runtime.sendNativeMessage is not available",
      );
    }
    if (!native_host) throw cmdError("EXEC_ERROR", "native_host is required");
    const payload = message != null ? message : {};
    const response = await chrome.runtime.sendNativeMessage(
      String(native_host),
      payload,
    );
    return {
      ok: true,
      native_host: String(native_host),
      response: response ?? null,
    };
  }
}
