// configYaml unit tests (zero dependencies, using node's built-in test runner).
//
// How to run (from the frontend directory):
//   node --test src/utils/configYaml.test.mjs   # run only this file
//   node --test                                 # auto-discover all *.test.mjs
// Note: do not use `node --test src/` (directory arguments are not supported in this node version).
//
// Note: configYaml is the pure-text YAML serialization/parsing utility that the
// config editor (ConfigEditorModal) depends on. It does not touch the DOM, so it
// can be unit tested directly as pure functions.
import { test } from "node:test";
import assert from "node:assert/strict";
import { cloneValue, toYaml, parseYaml } from "./configYaml.js";

// ===== cloneValue =====
test("cloneValue: returns primitive values unchanged", () => {
  assert.equal(cloneValue(1), 1);
  assert.equal(cloneValue("a"), "a");
  assert.equal(cloneValue(true), true);
  assert.equal(cloneValue(null), null);
  assert.equal(cloneValue(undefined), undefined);
});

test("cloneValue: deep-copies objects/arrays, mutating the copy does not affect the source", () => {
  const src = { a: 1, b: { c: [1, 2] } };
  const copy = cloneValue(src);
  assert.deepEqual(copy, src);
  copy.b.c.push(3);
  assert.deepEqual(src.b.c, [1, 2]);
});

// ===== toYaml =====
test("toYaml: scalars", () => {
  assert.equal(toYaml(null), "null");
  assert.equal(toYaml(undefined), "null");
  assert.equal(toYaml(42), "42");
  assert.equal(toYaml(true), "true");
  assert.equal(toYaml("hello"), "hello");
});

test("toYaml: empty array and empty object", () => {
  assert.equal(toYaml([]), "[]");
  assert.equal(toYaml({}), "{}");
});

test("toYaml: string quoting rules (reserved words and special characters must be quoted)", () => {
  // plain words are not quoted
  assert.equal(toYaml("abc"), "abc");
  assert.equal(toYaml("Chinese value"), "Chinese value");
  // words that could be misread as booleans/nulls must be quoted
  assert.equal(toYaml("true"), '"true"');
  assert.equal(toYaml("false"), '"false"');
  assert.equal(toYaml("null"), '"null"');
  assert.equal(toYaml("yes"), '"yes"');
  assert.equal(toYaml("off"), '"off"');
  // empty strings use single quotes
  assert.equal(toYaml(""), "''");
  // special characters like colons use JSON-style quotes
  assert.equal(toYaml("a:b"), '"a:b"');
});

test("toYaml: nested objects", () => {
  const out = toYaml({ a: 1, b: { c: 2 } });
  assert.equal(out, "a: 1\nb:\n  c: 2");
});

test("toYaml: arrays (scalar items)", () => {
  assert.equal(toYaml([1, 2, 3]), "- 1\n- 2\n- 3");
});

test("toYaml: array of objects, first keys align after the \"- \" prefix", () => {
  const out = toYaml([{ name: "x", v: 1 }]);
  assert.equal(out, "- name: x\n  v: 1");
});

test("toYaml: quoting rules for keys", () => {
  // keys with spaces: yamlQuote considers them safe to write bare (YAML keys can contain spaces)
  assert.equal(toYaml({ "a b": 1 }), "a b: 1");
  // regular characters are not quoted
  assert.equal(toYaml({ "a.b": 1 }), "a.b: 1");
  // characters like colons that break the structure must be quoted
  assert.equal(toYaml({ "a:b": 1 }), '"a:b": 1');
});

// ===== parseYaml =====
test("parseYaml: empty input returns an empty object", () => {
  assert.deepEqual(parseYaml(""), {});
  assert.deepEqual(parseYaml("\n\n"), {});
});

test("parseYaml: skips comments and blank lines", () => {
  const out = parseYaml("# comment\n\na: 1\n  # indented comment\nb: 2");
  assert.deepEqual(out, { a: 1, b: 2 });
});

test("parseYaml: scalar type inference", () => {
  const out = parseYaml(
    [
      "i: 10",
      "neg: -3",
      "f: 1.5",
      "t: true",
      "fa: false",
      "n: null",
      "s: abc",
    ].join("\n"),
  );
  assert.deepEqual(out, {
    i: 10,
    neg: -3,
    f: 1.5,
    t: true,
    fa: false,
    n: null,
    s: "abc",
  });
});

test("parseYaml: nested containers are placed by indentation", () => {
  const out = parseYaml(
    ["a:", "  b: 1", "  c:", "    d: 2", "e: 3"].join("\n"),
  );
  assert.deepEqual(out, { a: { b: 1, c: { d: 2 } }, e: 3 });
});

test("parseYaml: quoted strings (double/single quotes)", () => {
  const out = parseYaml(['a: "true"', "b: '123'", 'c: "a:b"'].join("\n"));
  assert.deepEqual(out, { a: "true", b: "123", c: "a:b" });
});

test("parseYaml: keys with special characters (quoted)", () => {
  const out = parseYaml('"a b": 1');
  assert.deepEqual(out, { "a b": 1 });
});

test("parseYaml: round-trips with toYaml (scalars + nesting)", () => {
  const src = { name: "agent", count: 3, nested: { flag: true, list: "x" } };
  assert.deepEqual(parseYaml(toYaml(src)), src);
});
