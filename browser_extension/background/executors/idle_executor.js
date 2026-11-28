// Idle state executor: wraps chrome.idle operations.
import { cmdError } from "../command_router.js";

export class IdleExecutor {
  /** Query the current idle state (active/idle/locked). */
  async queryState({ detection_interval_seconds } = {}) {
    const state = await chrome.idle.queryState(
      detection_interval_seconds != null
        ? Number(detection_interval_seconds)
        : 60,
    );
    return { state };
  }

  /** Set the idle detection interval (in seconds, minimum 15). */
  async setInterval({ detection_interval_seconds } = {}) {
    if (detection_interval_seconds == null) {
      throw cmdError("EXEC_ERROR", "detection_interval_seconds is required");
    }
    chrome.idle.setDetectionInterval(Number(detection_interval_seconds));
    return {
      ok: true,
      detection_interval_seconds: Number(detection_interval_seconds),
    };
  }

  /** Read the idle detection interval (in seconds). */
  async getInterval() {
    const seconds = chrome.idle.getDetectionInterval();
    return { detection_interval_seconds: seconds };
  }
}
