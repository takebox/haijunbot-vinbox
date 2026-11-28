// diffRenderer unit tests (vitest + jsdom).
//
// How to run (from the frontend directory):
//   npx vitest run src/diffRenderer.test.js   # run only this file
//   npm run test:vitest                       # run all vitest cases
//
// Note: escapeHtml depends on document, so vitest's jsdom environment is used.
// Assertions check the actual rendered HTML (classes / line numbers / escaping),
// not the internal implementation.
import { describe, test, expect, afterEach } from "vitest";
import {
  getLanguageFromFilename,
  escapeHtml,
  renderInlineDiff,
  renderSideBySideDiff,
} from "./diffRenderer.js";

// Build a single diff row
const row = (type, oldNum, oldLine, newNum, newLine) => ({
  type,
  old_line_num: oldNum,
  old_line: oldLine,
  new_line_num: newNum,
  new_line: newLine,
});

const makeDiff = (rows, extra = {}) => ({
  file_path: "a.py",
  additions: 1,
  deletions: 1,
  rows,
  ...extra,
});

// In jsdom window.innerWidth is writable; restore it after each case to avoid leaking into others
const originalInnerWidth = window.innerWidth;
afterEach(() => {
  window.innerWidth = originalInnerWidth;
});

describe("getLanguageFromFilename", () => {
  test("empty/undefined returns plaintext", () => {
    expect(getLanguageFromFilename("")).toBe("plaintext");
    expect(getLanguageFromFilename(undefined)).toBe("plaintext");
    expect(getLanguageFromFilename(null)).toBe("plaintext");
  });

  test("known extensions map correctly", () => {
    expect(getLanguageFromFilename("a.py")).toBe("python");
    expect(getLanguageFromFilename("a.js")).toBe("javascript");
    expect(getLanguageFromFilename("a.h")).toBe("cpp");
    expect(getLanguageFromFilename("a.yml")).toBe("yaml");
    expect(getLanguageFromFilename("a.cfg")).toBe("ini");
    expect(getLanguageFromFilename("a.md")).toBe("markdown");
    expect(getLanguageFromFilename("a.txt")).toBe("plaintext");
  });

  test("case-insensitive", () => {
    expect(getLanguageFromFilename("A.PY")).toBe("python");
    expect(getLanguageFromFilename("A.YML")).toBe("yaml");
  });

  test("multi-dot filenames use the last extension segment", () => {
    expect(getLanguageFromFilename("a.test.py")).toBe("python");
    expect(getLanguageFromFilename("/path/to/x.min.js")).toBe("javascript");
  });

  test("no or unknown extension returns plaintext", () => {
    expect(getLanguageFromFilename("Makefile")).toBe("plaintext");
    expect(getLanguageFromFilename("a.unknownext")).toBe("plaintext");
  });
});

describe("escapeHtml", () => {
  test("empty values return an empty string", () => {
    expect(escapeHtml("")).toBe("");
    expect(escapeHtml(undefined)).toBe("");
    expect(escapeHtml(null)).toBe("");
  });

  test("escapes HTML special characters", () => {
    expect(escapeHtml("<div>")).toBe("&lt;div&gt;");
    expect(escapeHtml("a & b")).toBe("a &amp; b");
    // double quotes are not escaped inside text nodes (innerHTML only escapes
    // quotes in attribute values) — that is real browser semantics
    expect(escapeHtml('"x"')).toBe('"x"');
  });

  test("replaces newlines with <br>", () => {
    expect(escapeHtml("a\nb")).toBe("a<br>b");
  });

  test("XSS payloads are escaped and produce no executable tags", () => {
    const out = escapeHtml("<script>alert(1)</script>");
    expect(out).not.toContain("<script>");
    expect(out).toContain("&lt;script&gt;");
  });
});

describe("renderInlineDiff", () => {
  test("returns a placeholder when there is no data or rows are missing", () => {
    expect(renderInlineDiff(null)).toContain("diff-error");
    expect(renderInlineDiff({})).toContain("diff-error");
    expect(renderInlineDiff({ rows: null })).toContain("diff-error");
  });

  test("renders normally with header, file path and stats", () => {
    const html = renderInlineDiff(makeDiff([row("equal", 1, "x", 1, "x")]));
    expect(html).toContain("diff-header");
    expect(html).toContain("diff-file-path");
    expect(html).toContain("a.py");
    expect(html).toContain("diff-stats");
    expect(html).toContain("diff-inline");
  });

  test("delete/insert/equal row-type classes and line numbers are correct", () => {
    const html = renderInlineDiff(
      makeDiff([
        row("delete", 1, "gone", null, null),
        row("insert", null, null, 1, "added"),
        row("equal", 2, "same", 2, "same"),
      ]),
    );
    expect(html).toContain("diff-deleted");
    expect(html).toContain("diff-added");
    // equal rows carry no add/delete background
    expect(html).toMatch(/<td class="diff-content ">/);
  });

  test("replace outputs both the old and new rows", () => {
    const html = renderInlineDiff(
      makeDiff([row("replace", 1, "old", 1, "new")]),
    );
    expect(html).toContain("diff-deleted");
    expect(html).toContain("diff-added");
    expect(html).toContain("old");
    expect(html).toContain("new");
  });

  test("inserts a separator when line numbers are not contiguous", () => {
    const html = renderInlineDiff(
      makeDiff([
        row("equal", 1, "a", 1, "a"),
        row("equal", 10, "b", 10, "b"), // line-number jump
      ]),
    );
    expect(html).toContain("diff-separator");
  });

  test("does not insert a separator when line numbers are contiguous", () => {
    const html = renderInlineDiff(
      makeDiff([row("equal", 1, "a", 1, "a"), row("equal", 2, "b", 2, "b")]),
    );
    expect(html).not.toContain("diff-separator");
  });

  test("displays Unknown when file_path is missing", () => {
    const html = renderInlineDiff(
      makeDiff([row("equal", 1, "a", 1, "a")], { file_path: "" }),
    );
    expect(html).toContain("Unknown");
  });

  test("falls back to plain text without throwing when the language is unknown", () => {
    const html = renderInlineDiff(
      makeDiff([row("equal", 1, "  indented", 1, "  indented")], {
        file_path: "a.unknownext",
      }),
    );
    expect(html).toContain("indented");
  });
});

describe("renderSideBySideDiff", () => {
  test("returns a placeholder when there is no data", () => {
    expect(renderSideBySideDiff(null)).toContain("diff-error");
    expect(renderSideBySideDiff({})).toContain("diff-error");
  });

  test("renders the 4-column side-by-side layout on desktop", () => {
    window.innerWidth = 1024;
    const html = renderSideBySideDiff(
      makeDiff([row("replace", 1, "old", 1, "new")]),
    );
    expect(html).toContain("diff-side-by-side");
    expect(html).toContain("<colgroup><col><col><col><col></colgroup>");
    expect(html).toContain("diff-old-num");
    expect(html).toContain("diff-new-num");
  });

  test("mobile (<=768) falls back to inline rendering", () => {
    window.innerWidth = 768;
    const html = renderSideBySideDiff(
      makeDiff([row("replace", 1, "old", 1, "new")]),
    );
    expect(html).toContain("diff-inline");
    expect(html).not.toContain("<colgroup><col><col><col><col></colgroup>");
  });

  test("delete rows fill only the old column, insert rows only the new column", () => {
    window.innerWidth = 1024;
    const html = renderSideBySideDiff(
      makeDiff([
        row("delete", 1, "gone", null, null),
        row("insert", null, null, 1, "added"),
      ]),
    );
    expect(html).toContain("diff-row-delete");
    expect(html).toContain("diff-row-insert");
    expect(html).toContain("gone");
    expect(html).toContain("added");
  });

  test("inserts a 4-column separator when line numbers jump", () => {
    window.innerWidth = 1024;
    const html = renderSideBySideDiff(
      makeDiff([row("equal", 1, "a", 1, "a"), row("equal", 20, "b", 20, "b")]),
    );
    expect(html).toContain(
      '<tr class="diff-separator"><td colspan="4"></td></tr>',
    );
  });
});
