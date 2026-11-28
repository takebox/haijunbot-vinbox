// gitDiffParser unit tests (zero dependencies, using node's built-in test runner).
//
// How to run (from the frontend directory):
//   node --test src/gitDiffParser.test.mjs   # run only this file
//   node --test                              # auto-discover all *.test.mjs
//   node --test "src/**/*.test.mjs"          # explicit glob
// Note: do not use `node --test src/` (directory arguments are not supported in this node version).
//
// This parser is currently the Git diff "fallback path": the
// /api/git/file-content endpoint provides full text for both sides,
// so this parser only reconstructs the left/right texts from a unified diff
// when that full text is unavailable. Pure function behavior only, no DOM / Monaco.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseUnifiedDiff } from "./gitDiffParser.js";

const EMPTY = {
  oldText: "",
  newText: "",
  isNewFile: false,
  isDeletedFile: false,
};

test("empty input returns an empty result", () => {
  assert.deepEqual(parseUnifiedDiff(""), EMPTY);
  assert.deepEqual(parseUnifiedDiff(undefined), EMPTY);
  assert.deepEqual(parseUnifiedDiff(null), EMPTY);
});

test("basic single-hunk change: reconstructs both texts", () => {
  const diff = [
    "diff --git a/a.txt b/a.txt",
    "index 111..222 100644",
    "--- a/a.txt",
    "+++ b/a.txt",
    "@@ -1,3 +1,3 @@",
    " ctx1",
    "-old2",
    "+new2",
    " ctx3",
  ].join("\n");
  const r = parseUnifiedDiff(diff);
  assert.equal(r.oldText, "ctx1\nold2\nctx3");
  assert.equal(r.newText, "ctx1\nnew2\nctx3");
  assert.equal(r.isNewFile, false);
  assert.equal(r.isDeletedFile, false);
});

test("new file: oldText is empty and isNewFile=true", () => {
  const diff = [
    "diff --git a/n.txt b/n.txt",
    "new file mode 100644",
    "--- /dev/null",
    "+++ b/n.txt",
    "@@ -0,0 +1,2 @@",
    "+line1",
    "+line2",
  ].join("\n");
  const r = parseUnifiedDiff(diff);
  assert.equal(r.oldText, "");
  assert.equal(r.newText, "line1\nline2");
  assert.equal(r.isNewFile, true);
});

test("deleted file: newText is empty and isDeletedFile=true", () => {
  const diff = [
    "diff --git a/d.txt b/d.txt",
    "deleted file mode 100644",
    "--- a/d.txt",
    "+++ /dev/null",
    "@@ -1,2 +0,0 @@",
    "-gone1",
    "-gone2",
  ].join("\n");
  const r = parseUnifiedDiff(diff);
  assert.equal(r.oldText, "gone1\ngone2");
  assert.equal(r.newText, "");
  assert.equal(r.isDeletedFile, true);
});

test("single-line hunk (count omitted)", () => {
  const diff = ["--- a/s.txt", "+++ b/s.txt", "@@ -5 +5 @@", "-x", "+y"].join(
    "\n",
  );
  const r = parseUnifiedDiff(diff);
  assert.equal(r.oldText, "x");
  assert.equal(r.newText, "y");
});

test("ignores \\ No newline at end of file marker lines", () => {
  const diff = [
    "--- a/nl.txt",
    "+++ b/nl.txt",
    "@@ -1 +1 @@",
    "-a",
    "\\ No newline at end of file",
    "+b",
    "\\ No newline at end of file",
  ].join("\n");
  const r = parseUnifiedDiff(diff);
  assert.equal(r.oldText, "a");
  assert.equal(r.newText, "b");
});

test("compact mode (default): fills only the gaps between hunks, no leading blanks", () => {
  // Two hunks 98 lines apart (100 - 1 - 1); compact mode keeps that gap to preserve alignment
  const diff = [
    "--- a/m.txt",
    "+++ b/m.txt",
    "@@ -1,1 +1,1 @@",
    "-a",
    "+A",
    "@@ -100,1 +100,1 @@",
    "-b",
    "+B",
  ].join("\n");
  const r = parseUnifiedDiff(diff);
  const oldLines = r.oldText.split("\n");
  assert.equal(oldLines.length, 100);
  assert.equal(oldLines[0], "a");
  assert.equal(oldLines[50], "");
  assert.equal(oldLines[99], "b");
  assert.equal(r.newText.split("\n")[99], "B");
});

test("compact mode: no leading blank lines when the first hunk does not start at line 1", () => {
  const diff = [
    "--- a/g.txt",
    "+++ b/g.txt",
    "@@ -50,1 +50,1 @@",
    "-p",
    "+P",
  ].join("\n");
  const r = parseUnifiedDiff(diff);
  assert.equal(r.oldText, "p");
  assert.equal(r.newText, "P");
});

test("absolute line-number mode: fills by absolute line numbers from the diff (including leading blanks)", () => {
  const diff = [
    "--- a/g.txt",
    "+++ b/g.txt",
    "@@ -50,1 +50,1 @@",
    "-p",
    "+P",
  ].join("\n");
  const r = parseUnifiedDiff(diff, { absoluteLineNumbers: true });
  const oldLines = r.oldText.split("\n");
  assert.equal(oldLines.length, 50);
  assert.equal(oldLines[49], "p");
  assert.equal(r.newText.split("\n")[49], "P");
});

test("absolute line-number mode: multiple hunks align by absolute line numbers", () => {
  const diff = [
    "--- a/m.txt",
    "+++ b/m.txt",
    "@@ -1,1 +1,1 @@",
    "-a",
    "+A",
    "@@ -100,1 +100,1 @@",
    "-b",
    "+B",
  ].join("\n");
  const r = parseUnifiedDiff(diff, { absoluteLineNumbers: true });
  assert.equal(r.oldText.split("\n").length, 100);
  assert.equal(r.oldText.split("\n")[0], "a");
  assert.equal(r.oldText.split("\n")[99], "b");
  assert.equal(r.newText.split("\n")[99], "B");
});

test("pure-context diff: both sides are identical", () => {
  const diff = [
    "--- a/c.txt",
    "+++ b/c.txt",
    "@@ -1,2 +1,2 @@",
    " same1",
    " same2",
  ].join("\n");
  const r = parseUnifiedDiff(diff);
  assert.equal(r.oldText, "same1\nsame2");
  assert.equal(r.newText, "same1\nsame2");
});
