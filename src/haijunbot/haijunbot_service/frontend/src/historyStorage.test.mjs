// Unit tests for historyStorage (zero dependencies, using node's built-in test runner).
//
// How to run (from the frontend directory):
//   node --test src/historyStorage.test.mjs   # run only this file
//   npm run test:node                         # run all node:test cases
//
// Note: historyStorage persists conversation history to localStorage.
// node:test has no localStorage, so a minimal in-memory implementation is mounted
// here (Map semantics, values stored as strings), matching the common subset of
// browser localStorage behavior.
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

// ===== in-memory localStorage stub (must be mounted on globalThis before importing the module under test) =====
const store = new Map();
globalThis.localStorage = {
  getItem: (k) => (store.has(String(k)) ? store.get(String(k)) : null),
  setItem: (k, v) => {
    store.set(String(k), String(v));
  },
  removeItem: (k) => {
    store.delete(String(k));
  },
  clear: () => store.clear(),
};

const historyStorage = (await import("./historyStorage.js")).default;
const {
  saveMessage,
  saveMessages,
  loadHistory,
  getTotalCount,
  clearHistory,
  clearHistoryForAgent,
  getHistoryForAgent,
  setHistoryForAgent,
  getMetadata,
  updateMetadata,
  getStorageInfo,
  pruneHistory,
  MAX_MESSAGES_PER_PAGE,
  MAX_TOTAL_MESSAGES,
  MAX_STORAGE_SIZE_BYTES,
} = historyStorage;

const STORAGE_KEY = "haijunbot_chat_history";
const METADATA_KEY = "haijunbot_chat_metadata";

// Clear storage before each case to avoid cross-test pollution
beforeEach(() => {
  localStorage.clear();
});

// Read the underlying storage directly to assert the real persisted content
const rawMessages = () => JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");

// ===== constants =====

test("exported constants: MAX_MESSAGES_PER_PAGE=50, MAX_TOTAL_MESSAGES=1000", () => {
  assert.equal(MAX_MESSAGES_PER_PAGE, 50);
  assert.equal(MAX_TOTAL_MESSAGES, 1000);
});

// ===== saveMessage =====

test("saveMessage: new messages get id and storageTimestamp auto-filled and are appended", () => {
  const ok = saveMessage({ agent_id: "a1", content: "hi" });
  assert.equal(ok, true);
  const saved = rawMessages();
  assert.equal(saved.length, 1);
  assert.equal(saved[0].agent_id, "a1");
  assert.ok(saved[0].id, "should auto-generate an id");
  assert.ok(saved[0].storageTimestamp, "should auto-write storageTimestamp");
});

test("saveMessage: same-id messages update in place without adding", () => {
  saveMessage({ id: "m1", content: "old" });
  saveMessage({ id: "m1", content: "new" });
  const saved = rawMessages();
  assert.equal(saved.length, 1);
  assert.equal(saved[0].content, "new");
});

test("saveMessage: trims from the head when exceeding MAX_TOTAL_MESSAGES", () => {
  for (let i = 0; i < MAX_TOTAL_MESSAGES + 5; i++) {
    saveMessage({ id: `m${i}`, content: `c${i}` });
  }
  const saved = rawMessages();
  assert.equal(saved.length, MAX_TOTAL_MESSAGES);
  // The oldest 5 are dropped, so the first message should be m5
  assert.equal(saved[0].id, "m5");
  assert.equal(saved[saved.length - 1].id, `m${MAX_TOTAL_MESSAGES + 4}`);
});

// ===== saveMessages =====

test("saveMessages: appends in bulk and fills in missing ids", () => {
  const ok = saveMessages([{ content: "a" }, { content: "b" }]);
  assert.equal(ok, true);
  const saved = rawMessages();
  assert.equal(saved.length, 2);
  assert.ok(saved[0].id);
  assert.ok(saved[1].id);
});

test("saveMessages: entries with existing ids are skipped (not overwritten)", () => {
  saveMessage({ id: "m1", content: "original" });
  saveMessages([
    { id: "m1", content: "should-not-apply" },
    { id: "m2", content: "new" },
  ]);
  const saved = rawMessages();
  assert.equal(saved.length, 2);
  assert.equal(saved.find((m) => m.id === "m1").content, "original");
  assert.equal(saved.find((m) => m.id === "m2").content, "new");
});

// ===== loadHistory =====

test("loadHistory: empty storage returns []", () => {
  assert.deepEqual(loadHistory(), []);
});

test("loadHistory: takes the last 50 messages by default", () => {
  for (let i = 0; i < 60; i++) saveMessage({ id: `m${i}` });
  const page = loadHistory();
  assert.equal(page.length, MAX_MESSAGES_PER_PAGE);
  assert.equal(page[0].id, "m10"); // last 50 from the end → m10..m59
  assert.equal(page[page.length - 1].id, "m59");
});

test("loadHistory: offset skips from the end backwards", () => {
  for (let i = 0; i < 10; i++) saveMessage({ id: `m${i}` });
  const page = loadHistory(3, 2); // skip the last 2, then take 3
  assert.deepEqual(
    page.map((m) => m.id),
    ["m5", "m6", "m7"],
  );
});

test("loadHistory: the given agentId only returns that agent's messages", () => {
  saveMessage({ id: "a1", agent_id: "A" });
  saveMessage({ id: "b1", agent_id: "B" });
  saveMessage({ id: "a2", agent_id: "A" });
  const page = loadHistory(50, 0, "A");
  assert.deepEqual(
    page.map((m) => m.id),
    ["a1", "a2"],
  );
});

test("loadHistory: returns [] when offset exceeds the total", () => {
  saveMessage({ id: "m0" });
  assert.deepEqual(loadHistory(50, 5), []);
});

// ===== getTotalCount =====

test("getTotalCount: total count and agentId-filtered count", () => {
  saveMessage({ id: "a1", agent_id: "A" });
  saveMessage({ id: "b1", agent_id: "B" });
  saveMessage({ id: "a2", agent_id: "A" });
  assert.equal(getTotalCount(), 3);
  assert.equal(getTotalCount("A"), 2);
  assert.equal(getTotalCount("nonexistent"), 0);
});

// ===== clearHistory / clearHistoryForAgent =====

test("clearHistory: clears both the messages and metadata keys", () => {
  saveMessage({ id: "m0" });
  updateMetadata();
  assert.equal(clearHistory(), true);
  assert.equal(localStorage.getItem(STORAGE_KEY), null);
  assert.equal(localStorage.getItem(METADATA_KEY), null);
});

test("clearHistoryForAgent: deletes only the given agent, keeping the others", () => {
  saveMessage({ id: "a1", agent_id: "A" });
  saveMessage({ id: "b1", agent_id: "B" });
  assert.equal(clearHistoryForAgent("A"), true);
  const saved = rawMessages();
  assert.equal(saved.length, 1);
  assert.equal(saved[0].id, "b1");
});

test("clearHistoryForAgent: returns true even when the target does not exist", () => {
  saveMessage({ id: "b1", agent_id: "B" });
  assert.equal(clearHistoryForAgent("nonexistent"), true);
  assert.equal(rawMessages().length, 1);
});

// ===== getHistoryForAgent / setHistoryForAgent =====

test("getHistoryForAgent: returns only the given agent's messages", () => {
  saveMessage({ id: "a1", agent_id: "A" });
  saveMessage({ id: "b1", agent_id: "B" });
  assert.deepEqual(
    getHistoryForAgent("A").map((m) => m.id),
    ["a1"],
  );
  assert.deepEqual(getHistoryForAgent("nonexistent"), []);
});

test("setHistoryForAgent: removes the agent's old messages, writes new ones, and leaves other agents untouched", () => {
  saveMessage({ id: "a1", agent_id: "A" });
  saveMessage({ id: "b1", agent_id: "B" });
  const ok = setHistoryForAgent("A", [{ content: "new-a" }]);
  assert.equal(ok, true);
  const saved = rawMessages();
  // B is kept, and A's old messages are replaced with one new message
  const bMessages = saved.filter((m) => m.agent_id === "B");
  const aMessages = saved.filter((m) => m.agent_id === "A");
  assert.equal(bMessages.length, 1);
  assert.equal(bMessages[0].id, "b1");
  assert.equal(aMessages.length, 1);
  assert.equal(aMessages[0].content, "new-a");
  assert.ok(aMessages[0].id, "new messages should get an id");
  assert.ok(aMessages[0].storageTimestamp, "new messages should get a storageTimestamp");
  assert.ok(!saved.some((m) => m.id === "a1"), "old message a1 should be removed");
});

// ===== getMetadata / updateMetadata =====

test("getMetadata: returns the default object when there is no data", () => {
  assert.deepEqual(getMetadata(), {
    totalCount: 0,
    lastUpdated: null,
    storageSize: 0,
  });
});

test("updateMetadata: writes totalCount and storageSize", () => {
  saveMessage({ id: "m0", content: "x" });
  const meta = updateMetadata();
  assert.equal(meta.totalCount, 1);
  assert.ok(meta.lastUpdated > 0);
  assert.equal(meta.storageSize, JSON.stringify(rawMessages()).length);
  // Persisted and readable back
  assert.deepEqual(getMetadata(), meta);
});

// ===== getStorageInfo =====

test('getStorageInfo: with empty storage, lastUpdated is "never" and maxMessages=1000', () => {
  const info = getStorageInfo();
  assert.equal(info.totalCount, 0);
  assert.equal(info.lastUpdated, "never");
  assert.equal(info.maxMessages, MAX_TOTAL_MESSAGES);
  // Note: with empty storage, getAllMessages() returns [], and JSON.stringify([]) === "[]" (length 2),
  // so totalSize is 2 rather than 0, and formatBytes(2) yields "2 B". This is the real behavior of the current implementation.
  assert.equal(info.totalSize, 2);
  assert.equal(info.totalSizeFormatted, "2 B");
});

test("getStorageInfo: counts messages and size when data exists", () => {
  saveMessage({ id: "m0" });
  const info = getStorageInfo();
  assert.equal(info.totalCount, 1);
  assert.ok(info.totalSize > 0);
  assert.match(info.totalSizeFormatted, /B$/);
});

// ===== exception tolerance =====

test("exception tolerance: when localStorage.getItem throws, read paths return empty/default values without throwing", () => {
  const original = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: () => {
      throw new Error("boom");
    },
    setItem: () => {},
    removeItem: () => {},
    clear: () => {},
  };
  try {
    assert.deepEqual(loadHistory(), []);
    assert.equal(getTotalCount(), 0);
    assert.deepEqual(getHistoryForAgent("A"), []);
    assert.deepEqual(getMetadata(), {
      totalCount: 0,
      lastUpdated: null,
      storageSize: 0,
    });
    assert.equal(getStorageInfo().totalCount, 0);
  } finally {
    globalThis.localStorage = original;
  }
});

test("exception tolerance: when localStorage.setItem throws, nothing propagates (saveMessage still returns true)", () => {
  const original = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: () => null,
    setItem: () => {
      throw new Error("quota exceeded");
    },
    removeItem: () => {},
    clear: () => {},
  };
  try {
    // Note: saveMessage/saveMessages internally call saveAllMessages but do not check
    // its return value, so a failed underlying write still returns true (the write
    // failure is only caught and logged inside saveAllMessages).
    // This asserts the current behavior honestly — without masking it or sneaking in a fix.
    assert.equal(saveMessage({ content: "x" }), true);
    assert.equal(saveMessages([{ content: "y" }]), true);
  } finally {
    globalThis.localStorage = original;
  }
});

// ===== pruneHistory =====

test("exported constant: MAX_STORAGE_SIZE_BYTES=3MB", () => {
  assert.equal(MAX_STORAGE_SIZE_BYTES, 3 * 1024 * 1024);
});

test("pruneHistory: performs no deletion when the size is within the threshold", () => {
  saveMessage({ id: "a1", agent_id: "A", content: "x" });
  saveMessage({ id: "b1", agent_id: "B", content: "y" });
  const result = pruneHistory();
  assert.deepEqual(result, {
    removedOrphans: 0,
    removedBySize: 0,
    totalRemoved: 0,
    remainingCount: 2,
    remainingSize: JSON.stringify(rawMessages()).length,
  });
  assert.equal(rawMessages().length, 2);
});

test("pruneHistory: cleans up orphan messages missing an agent_id", () => {
  saveMessage({ id: "a1", agent_id: "A", content: "x" });
  saveMessage({ id: "orphan1", content: "orphan" });
  saveMessage({ id: "orphan2", agent_id: "", content: "empty-agent" });
  const result = pruneHistory({ removeOrphans: true });
  assert.equal(result.removedOrphans, 2);
  assert.equal(result.totalRemoved, 2);
  const saved = rawMessages();
  assert.equal(saved.length, 1);
  assert.equal(saved[0].id, "a1");
});

test("pruneHistory: does not delete messages without agent_id when removeOrphans=false", () => {
  saveMessage({ id: "a1", agent_id: "A", content: "x" });
  saveMessage({ id: "orphan1", content: "orphan" });
  const result = pruneHistory({ removeOrphans: false });
  assert.equal(result.removedOrphans, 0);
  assert.equal(rawMessages().length, 2);
});

test("pruneHistory: deletes the oldest messages by storageTimestamp when the size exceeds the threshold", () => {
  // Build a batch of sizeable messages, writing directly to the underlying storage to control timestamps precisely
  const messages = [];
  for (let i = 0; i < 200; i++) {
    messages.push({
      id: `m${i}`,
      agent_id: "A",
      content: "x".repeat(5000),
      storageTimestamp: 1000 + i,
    });
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  // 200 messages * ~5KB ≈ 1MB, still below 3MB; inflate the size past the threshold
  const big = messages.map((m) => ({ ...m, content: "x".repeat(40000) }));
  localStorage.setItem(STORAGE_KEY, JSON.stringify(big));

  const beforeSize = JSON.stringify(rawMessages()).length;
  assert.ok(beforeSize > MAX_STORAGE_SIZE_BYTES, "precondition: the size must exceed the threshold");

  const result = pruneHistory();
  assert.ok(result.removedBySize > 0, "should delete the oldest messages by size");
  const saved = rawMessages();
  const afterSize = JSON.stringify(saved).length;
  assert.ok(afterSize <= MAX_STORAGE_SIZE_BYTES, "the size should fall back within the threshold after cleanup");
  // The oldest (smallest storageTimestamp) should be deleted first; the smallest remaining timestamp should be greater than the largest deleted timestamp
  const timestamps = saved.map((m) => m.storageTimestamp).sort((a, b) => a - b);
  const removedMaxTs = 1000 + result.removedBySize - 1;
  assert.ok(
    timestamps[0] > removedMaxTs,
    `the oldest ${result.removedBySize} should be deleted, leaving the smallest timestamp ${timestamps[0]} greater than the largest deleted ${removedMaxTs}`,
  );
});

test("pruneHistory: triggered automatically after saveMessage, cleaning up when the threshold is exceeded", () => {
  // Write a batch of over-threshold data, then save one message, verifying the write path auto-cleans
  const messages = [];
  for (let i = 0; i < 200; i++) {
    messages.push({
      id: `m${i}`,
      agent_id: "A",
      content: "x".repeat(40000),
      storageTimestamp: 1000 + i,
    });
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  saveMessage({ id: "new", agent_id: "A", content: "hello" });
  const saved = rawMessages();
  assert.ok(
    JSON.stringify(saved).length <= MAX_STORAGE_SIZE_BYTES,
    "should auto-prune within the threshold after saveMessage",
  );
  // The new message should be kept (it is the newest)
  assert.ok(saved.some((m) => m.id === "new"), "the newly written message should not be deleted");
});

test("pruneHistory: returns all-zero stats for empty storage", () => {
  const result = pruneHistory();
  assert.deepEqual(result, {
    removedOrphans: 0,
    removedBySize: 0,
    totalRemoved: 0,
    remainingCount: 0,
    remainingSize: 2,
  });
});

test("getStorageInfo: includes maxStorageSize=3MB", () => {
  const info = getStorageInfo();
  assert.equal(info.maxStorageSize, MAX_STORAGE_SIZE_BYTES);
});
