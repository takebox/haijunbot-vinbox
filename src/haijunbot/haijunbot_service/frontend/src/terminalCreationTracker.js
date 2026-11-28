// Terminal creation "initiated on this device" tracker.
//
// After this device sends terminal_create, a matching terminal_created reply should
// auto-switch to the new terminal; but a terminal_created broadcast from another device
// (admin/ACL sharing) must not switch, keeping this device's current workflow intact.
// This module distinguishes the two cases with a flag that auto-resets after a timeout.
export function createTerminalCreationTracker(timeoutMs = 10000) {
  let pending = false;
  let timer = null;

  return {
    // This device initiated terminal creation, waiting for the terminal_created reply
    mark() {
      pending = true;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        pending = false;
        timer = null;
      }, timeoutMs);
    },
    // Called when terminal_created arrives: returns true and resets if this device
    // initiated the creation, otherwise returns false (shared from another device, no switch)
    shouldSwitch() {
      if (pending) {
        pending = false;
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        return true;
      }
      return false;
    },
    isPending() {
      return pending;
    },
  };
}
