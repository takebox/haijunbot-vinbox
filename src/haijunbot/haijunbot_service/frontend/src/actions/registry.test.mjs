// Unit tests for actions/registry (zero dependencies, using node's built-in test runner).
//
// How to run (from the frontend directory):
//   node --test src/actions/registry.test.mjs   # run only this file
//   npm run test:node                           # run all node:test cases
//
// Note: registry is the single shared data source for the command palette, the
// pet menu and keyboard shortcuts. It is a pure module with no Vue or DOM
// dependencies, so the pure functions and the data table can be unit tested
// directly.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ACTIONS,
  filterActions,
  groupActions,
  findShortcutConflicts,
} from "./registry.js";

// ===== filterActions =====

test("filterActions: empty query returns a shallow copy (new array, same element references)", () => {
  const src = [{ id: "a" }, { id: "b" }];
  const out = filterActions(src, "");
  assert.notEqual(out, src); // must be a new array so callers cannot mutate the original table
  assert.deepEqual(out, src);
  assert.equal(out[0], src[0]); // elements are still the same references
});

test("filterActions: null/undefined query is treated as an empty query", () => {
  const src = [{ id: "a", label: "A" }];
  assert.equal(filterActions(src, null).length, 1);
  assert.equal(filterActions(src, undefined).length, 1);
});

test("filterActions: query leading/trailing whitespace and case are normalized", () => {
  const src = [{ id: "view-diff", label: "View Changes", en: "View Diff" }];
  assert.equal(filterActions(src, "  VIEW  ").length, 1);
  assert.equal(filterActions(src, "view").length, 1);
});

test("filterActions: can match any of label / en / id / group / keywords", () => {
  const src = [
    {
      id: "x1",
      label: "View Changes",
      en: "View Diff",
      group: "Current Agent",
      keywords: ["changes"],
    },
  ];
  assert.equal(filterActions(src, "View").length, 1); // label
  assert.equal(filterActions(src, "diff").length, 1); // en (case-insensitive)
  assert.equal(filterActions(src, "x1").length, 1); // id
  assert.equal(filterActions(src, "agent").length, 1); // group
  assert.equal(filterActions(src, "changes").length, 1); // keywords
  assert.equal(filterActions(src, "nonexistent").length, 0);
});

test("filterActions: non-array input falls back to an empty array", () => {
  assert.deepEqual(filterActions(null, "x"), []);
  assert.deepEqual(filterActions(undefined, "x"), []);
  assert.deepEqual(filterActions("not-array", "x"), []);
});

test("filterActions: items missing fields do not throw (filter(Boolean) fallback)", () => {
  const src = [{ id: "only-id" }, { label: "label-only" }, {}];
  assert.equal(filterActions(src, "only-id").length, 1);
  assert.equal(filterActions(src, "label-only").length, 1);
  assert.equal(filterActions(src, "zzz").length, 0);
});

// ===== groupActions =====

test("groupActions: groups by group, preserving first-occurrence order within and across groups", () => {
  const src = [
    { id: "a", group: "G1" },
    { id: "b", group: "G2" },
    { id: "c", group: "G1" },
  ];
  const out = groupActions(src);
  assert.deepEqual(
    out.map((g) => g.group),
    ["G1", "G2"],
  );
  assert.deepEqual(
    out[0].actions.map((a) => a.id),
    ["a", "c"],
  );
  assert.deepEqual(
    out[1].actions.map((a) => a.id),
    ["b"],
  );
});

test("groupActions: missing group falls into \"Other\"", () => {
  const out = groupActions([{ id: "a" }, { id: "b", group: "" }]);
  assert.equal(out.length, 1);
  assert.equal(out[0].group, "Other");
  assert.equal(out[0].actions.length, 2);
});

test("groupActions: non-array input returns an empty array", () => {
  assert.deepEqual(groupActions(null), []);
  assert.deepEqual(groupActions("x"), []);
});

// ===== findShortcutConflicts =====

test("findShortcutConflicts: the real registry currently has no shortcut conflicts (regression guard)", () => {
  const conflicts = findShortcutConflicts();
  assert.ok(Array.isArray(conflicts));
  assert.deepEqual(
    conflicts,
    [],
    `registry has indistinguishable same-key actions: ${JSON.stringify(conflicts)}`,
  );
});

test("findShortcutConflicts: same key with a repeated scope → conflict reported", () => {
  const actions = [
    { id: "a", shortcut: "Ctrl+K", shortcutScope: "global" },
    { id: "b", shortcut: "ctrl+k", shortcutScope: "global" },
  ];
  const conflicts = findShortcutConflicts(actions);
  assert.equal(conflicts.length, 1);
  assert.equal(conflicts[0].shortcut, "ctrl+k"); // shortcut names are normalized to lowercase
  assert.match(conflicts[0].reason, /global/);
  assert.deepEqual(conflicts[0].actions, ["a", "b"]);
});

test("findShortcutConflicts: same key with distinct scopes → no conflict", () => {
  const actions = [
    { id: "a", shortcut: "F2", shortcutScope: "global" },
    { id: "b", shortcut: "F2", shortcutScope: "node" },
  ];
  assert.deepEqual(findShortcutConflicts(actions), []);
});

test("findShortcutConflicts: an undeclared scope counts as global and conflicts with explicit global", () => {
  const actions = [
    { id: "a", shortcut: "F2" },
    { id: "b", shortcut: "F2", shortcutScope: "global" },
  ];
  const conflicts = findShortcutConflicts(actions);
  assert.equal(conflicts.length, 1);
  assert.deepEqual(conflicts[0].actions, ["a", "b"]);
});

test("findShortcutConflicts: actions without a shortcut are ignored; non-array input does not throw", () => {
  assert.deepEqual(
    findShortcutConflicts([{ id: "a" }, { id: "b", shortcut: "" }]),
    [],
  );
  assert.deepEqual(findShortcutConflicts(null), []);
  assert.deepEqual(findShortcutConflicts("x"), []);
});

// ===== ACTIONS data table self-check =====

test("ACTIONS: every item has id/label/group/icon/run and unique ids", () => {
  assert.ok(Array.isArray(ACTIONS));
  assert.ok(ACTIONS.length > 0);
  const ids = ACTIONS.map((a) => a.id);
  assert.equal(new Set(ids).size, ids.length, "duplicate ids");
  for (const action of ACTIONS) {
    assert.equal(
      typeof action.id,
      "string",
      `id is not a string: ${JSON.stringify(action)}`,
    );
    assert.ok(action.id.length > 0, "id is empty");
    assert.equal(typeof action.label, "string", `label is not a string: ${action.id}`);
    assert.ok(action.label.length > 0, `label is empty: ${action.id}`);
    assert.equal(typeof action.group, "string", `group is not a string: ${action.id}`);
    assert.equal(typeof action.icon, "string", `icon is not a string: ${action.id}`);
    assert.equal(typeof action.run, "function", `run is not a function: ${action.id}`);
  }
});
