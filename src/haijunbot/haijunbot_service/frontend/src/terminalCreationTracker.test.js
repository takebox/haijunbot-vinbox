// terminalCreationTracker unit tests (vitest).
//
// Covers core behavior: after this device initiates a creation, the terminal_created
// reply should switch views (shouldSwitch=true); shared terminal_created events from
// other endpoints (no creation initiated) must not switch; the flag auto-resets after
// a timeout so stale flags do not cause later shared terminals to switch incorrectly.
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { createTerminalCreationTracker } from "./terminalCreationTracker.js";

describe("createTerminalCreationTracker", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("after this device initiates creation, the terminal_created reply should switch", () => {
    const tracker = createTerminalCreationTracker();
    tracker.mark();
    expect(tracker.shouldSwitch()).toBe(true);
  });

  test("shared terminal_created from another endpoint (no creation initiated) should not switch", () => {
    const tracker = createTerminalCreationTracker();
    expect(tracker.shouldSwitch()).toBe(false);
  });

  test("shouldSwitch resets after being consumed; later shared terminals do not switch", () => {
    const tracker = createTerminalCreationTracker();
    tracker.mark();
    expect(tracker.shouldSwitch()).toBe(true);
    // Second time (simulating another shared terminal arriving) should not switch
    expect(tracker.shouldSwitch()).toBe(false);
  });

  test("flag auto-resets after the timeout to avoid stale flags switching views", () => {
    const tracker = createTerminalCreationTracker(10000);
    tracker.mark();
    expect(tracker.isPending()).toBe(true);
    vi.advanceTimersByTime(10001);
    expect(tracker.isPending()).toBe(false);
    expect(tracker.shouldSwitch()).toBe(false);
  });

  test("isPending reflects whether a reply is currently awaited", () => {
    const tracker = createTerminalCreationTracker();
    expect(tracker.isPending()).toBe(false);
    tracker.mark();
    expect(tracker.isPending()).toBe(true);
  });
});
