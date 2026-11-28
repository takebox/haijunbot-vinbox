// dagLayout unit tests (zero dependencies, using node's built-in test runner).
//
// How to run (from the frontend directory):
//   node --test src/components/dagLayout.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { computeLevels, layoutDag, edgePath, LAYOUT } from "./dagLayout.js";

test("computeLevels: linear dependencies increase level by level", () => {
  const levels = computeLevels([
    { stage: "a", dependsOn: [] },
    { stage: "b", dependsOn: ["a"] },
    { stage: "c", dependsOn: ["b"] },
  ]);
  assert.equal(levels.get("a"), 0);
  assert.equal(levels.get("b"), 1);
  assert.equal(levels.get("c"), 2);
});

test("computeLevels: parallel branches take the max dependency level", () => {
  const levels = computeLevels([
    { stage: "a", dependsOn: [] },
    { stage: "b", dependsOn: ["a"] },
    { stage: "c", dependsOn: ["a"] },
    { stage: "d", dependsOn: ["b", "c"] },
  ]);
  assert.equal(levels.get("b"), 1);
  assert.equal(levels.get("c"), 1);
  assert.equal(levels.get("d"), 2);
});

test("computeLevels: cycle defense avoids infinite recursion", () => {
  const levels = computeLevels([
    { stage: "a", dependsOn: ["b"] },
    { stage: "b", dependsOn: ["a"] },
  ]);
  assert.ok(levels.has("a"));
  assert.ok(levels.has("b"));
});

test("computeLevels: ignores non-existent dependencies", () => {
  const levels = computeLevels([{ stage: "a", dependsOn: ["ghost"] }]);
  assert.equal(levels.get("a"), 0);
});

test("layoutDag: same-level nodes have increasing y, levels have increasing x", () => {
  const { positions } = layoutDag([
    { stage: "a", dependsOn: [] },
    { stage: "b", dependsOn: [] },
    { stage: "c", dependsOn: ["a", "b"] },
  ]);
  assert.equal(positions.a.x, positions.b.x);
  assert.ok(positions.b.y > positions.a.y);
  assert.ok(positions.c.x > positions.a.x);
});

test("layoutDag: edges cover all valid dependencies and ignore dangling ones", () => {
  const { edges } = layoutDag([
    { stage: "a", dependsOn: [] },
    { stage: "b", dependsOn: ["a", "ghost"] },
  ]);
  assert.deepEqual(edges, [{ from: "a", to: "b" }]);
});

test("layoutDag: width/height are positive and grow with the node count", () => {
  const single = layoutDag([{ stage: "a", dependsOn: [] }]);
  const chain = layoutDag([
    { stage: "a", dependsOn: [] },
    { stage: "b", dependsOn: ["a"] },
    { stage: "c", dependsOn: ["b"] },
  ]);
  assert.ok(single.width > 0 && single.height > 0);
  assert.ok(chain.width > single.width);
});

test("layoutDag: supports Map input", () => {
  const stages = new Map([
    ["a", { stage: "a", dependsOn: [] }],
    ["b", { stage: "b", dependsOn: ["a"] }],
  ]);
  const { positions } = layoutDag(stages);
  assert.ok(positions.a && positions.b);
  assert.ok(positions.b.x > positions.a.x);
});

test("edgePath: generates a cubic Bezier path", () => {
  const p = edgePath({ x: 0, y: 0 }, { x: 300, y: 100 });
  assert.ok(p.startsWith("M "));
  assert.ok(p.includes(" C "));
  assert.ok(p.includes(String(LAYOUT.NODE_W))); // start x begins at the node's right edge
});
