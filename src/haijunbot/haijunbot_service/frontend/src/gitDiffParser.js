// unified diff parsing: splits the standard unified diff text produced by
// `git show` into "old file content / new file content" for the original and
// modified models of the Monaco DiffEditor.
//
// Why this is needed: Monaco's DiffEditor does not compute diffs itself; it only
// "displays" the difference between two texts. So the unified diff must first be
// restored into two complete left/right texts.
//
// Design notes:
// - Pure functions, no side effects, no dependencies, so they can be unit tested directly with node.
// - When line numbers are non-consecutive between hunks, blank lines are inserted
//   to keep the left/right line numbers aligned; otherwise Monaco would misalign
//   all subsequent content (this is the easiest pitfall to hit).
// - New file (--- /dev/null) → oldText is empty; deleted file (+++ /dev/null) → newText is empty.

/**
 * Parses a unified diff text into left/right contents.
 *
 * Note: the backend `git show --format=` returns a **partial diff** (only the changed
 * regions and their context), not the full file. So by default the "compact mode" is
 * used: content is not padded to the absolute line numbers in the diff, only each
 * hunk's own content and the relative gaps between hunks are kept. Otherwise Monaco
 * would render thousands of blank lines before the changed content, which is a bad
 * experience.
 *
 * @param {string} diffText - unified diff text from `git show`/`git diff`
 * @param {{ absoluteLineNumbers?: boolean }} [options]
 *        when absoluteLineNumbers=true, pads to the absolute line numbers in the diff
 *        (for cases where both sides already provide complete file contents); default false (compact mode).
 * @returns {{ oldText: string, newText: string, isNewFile: boolean, isDeletedFile: boolean }}
 */
export function parseUnifiedDiff(diffText, options = {}) {
  const empty = {
    oldText: "",
    newText: "",
    isNewFile: false,
    isDeletedFile: false,
  };
  if (!diffText || typeof diffText !== "string") return empty;
  const absoluteLineNumbers = options.absoluteLineNumbers === true;

  const lines = diffText.split("\n");
  const oldLines = [];
  const newLines = [];

  let isNewFile = false;
  let isDeletedFile = false;
  // Whether we have entered the hunk body (header lines vs. hunk lines are handled differently)
  let inHunk = false;
  // Remaining old/new lines the current hunk must consume (used to pad after the hunk ends)
  let oldRemaining = 0;
  let newRemaining = 0;
  // Old/new lines already written in the current hunk
  let oldWritten = 0;
  let newWritten = 0;
  // Total old/new lines written, used to pad alignment between hunks by line number
  let oldTotal = 0;
  let newTotal = 0;
  // Starting line numbers and counts of the previous hunk (used to compute relative gaps between hunks in compact mode)
  let lastHunkOldStart = null;
  let lastHunkNewStart = null;
  let lastHunkOldCount = 0;
  let lastHunkNewCount = 0;

  // Finish a hunk: if the declared line counts were not fully consumed (e.g. truncated diff), pad with blank lines to keep alignment
  const closeHunk = () => {
    if (!inHunk) return;
    while (oldWritten < oldRemaining) {
      oldLines.push("");
      oldWritten += 1;
      oldTotal += 1;
    }
    while (newWritten < newRemaining) {
      newLines.push("");
      newWritten += 1;
      newTotal += 1;
    }
    inHunk = false;
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];

    // File header: diff --git / index / old mode / new mode / similarity etc.
    if (line.startsWith("diff --git ")) {
      closeHunk();
      continue;
    }
    if (
      line.startsWith("index ") ||
      line.startsWith("old mode ") ||
      line.startsWith("new mode ")
    ) {
      continue;
    }
    if (
      line.startsWith("similarity index ") ||
      line.startsWith("dissimilarity index ")
    ) {
      continue;
    }
    if (line.startsWith("rename from ") || line.startsWith("rename to ")) {
      continue;
    }
    if (line.startsWith("new file mode ")) {
      isNewFile = true;
      continue;
    }
    if (line.startsWith("deleted file mode ")) {
      isDeletedFile = true;
      continue;
    }

    // --- / +++ header lines: mark new/deleted files, but are not content
    if (line.startsWith("--- ")) {
      if (line.slice(4).trim() === "/dev/null") isNewFile = true;
      continue;
    }
    if (line.startsWith("+++ ")) {
      if (line.slice(4).trim() === "/dev/null") isDeletedFile = true;
      continue;
    }

    // Hunk header: @@ -oldStart,oldCount +newStart,newCount @@
    if (line.startsWith("@@")) {
      closeHunk();
      const match = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/.exec(line);
      if (match) {
        const oldStart = Number(match[1]);
        const newStart = Number(match[3]);
        oldRemaining = match[2] === undefined ? 1 : Number(match[2]);
        newRemaining = match[4] === undefined ? 1 : Number(match[4]);
        // Pad with blank lines when line numbers are non-consecutive between hunks,
        // to keep the left/right line numbers aligned; otherwise Monaco would
        // misalign all subsequent differences.
        // - Absolute mode: pad up to the absolute line number in the diff (oldStart-1).
        // - Compact mode (default): pad only the relative gap between hunks, avoiding
        //   huge blocks of blank lines before the content of a partial diff.
        if (absoluteLineNumbers) {
          while (oldTotal < oldStart - 1) {
            oldLines.push("");
            oldTotal += 1;
          }
          while (newTotal < newStart - 1) {
            newLines.push("");
            newTotal += 1;
          }
        } else if (lastHunkOldStart !== null) {
          const oldGap = oldStart - lastHunkOldStart - lastHunkOldCount;
          const newGap = newStart - lastHunkNewStart - lastHunkNewCount;
          for (let g = 0; g < oldGap; g += 1) {
            oldLines.push("");
            oldTotal += 1;
          }
          for (let g = 0; g < newGap; g += 1) {
            newLines.push("");
            newTotal += 1;
          }
        }
        lastHunkOldStart = oldStart;
        lastHunkNewStart = newStart;
        lastHunkOldCount = oldRemaining;
        lastHunkNewCount = newRemaining;
        oldWritten = 0;
        newWritten = 0;
        inHunk = true;
      }
      continue;
    }

    // "\ No newline at end of file": ignore
    if (line.startsWith("\\")) continue;

    if (!inHunk) continue;

    const marker = line.charAt(0);
    const content = line.slice(1);

    if (marker === " ") {
      // Context line: goes to both sides
      oldLines.push(content);
      newLines.push(content);
      oldWritten += 1;
      newWritten += 1;
      oldTotal += 1;
      newTotal += 1;
    } else if (marker === "-") {
      oldLines.push(content);
      oldWritten += 1;
      oldTotal += 1;
    } else if (marker === "+") {
      newLines.push(content);
      newWritten += 1;
      newTotal += 1;
    } else if (line === "") {
      // Some implementations drop the prefix on blank lines; treat them as context blank lines
      oldLines.push("");
      newLines.push("");
      oldWritten += 1;
      newWritten += 1;
      oldTotal += 1;
      newTotal += 1;
    }
  }

  closeHunk();

  // Drop the extra blank line created by split('\n') from the trailing newline, so neither side gains an extra row
  if (oldLines.length && oldLines[oldLines.length - 1] === "") oldLines.pop();
  if (newLines.length && newLines[newLines.length - 1] === "") newLines.pop();

  return {
    oldText: oldLines.join("\n"),
    newText: newLines.join("\n"),
    isNewFile,
    isDeletedFile,
  };
}

/**
 * Extracts the "changed context regions" from a unified diff: keeps only each hunk's
 * content (context lines + added/removed lines) and drops the file headers and the
 * large unchanged code between hunks.
 *
 * Difference from parseUnifiedDiff: parseUnifiedDiff pads blank lines for the line-number
 * gaps between hunks to align absolute line numbers, which in full-text mode produces
 * large blocks of blank space; this function only takes the hunk bodies, so both sides
 * are compact, suitable for the "diff context only" reading mode.
 *
 * @param {string} diffText - unified diff text from `git show`/`git diff`
 * @returns {{ oldText: string, newText: string, isNewFile: boolean, isDeletedFile: boolean }}
 */
export function extractDiffContext(diffText) {
  const empty = {
    oldText: "",
    newText: "",
    isNewFile: false,
    isDeletedFile: false,
  };
  if (!diffText || typeof diffText !== "string") return empty;

  const lines = diffText.split("\n");
  const oldLines = [];
  const newLines = [];

  let isNewFile = false;
  let isDeletedFile = false;
  let inHunk = false;
  let oldRemaining = 0;
  let newRemaining = 0;
  let oldWritten = 0;
  let newWritten = 0;

  // Finish a hunk: pad with blank lines when the diff is truncated so the left/right sides stay aligned
  const closeHunk = () => {
    if (!inHunk) return;
    while (oldWritten < oldRemaining) {
      oldLines.push("");
      oldWritten += 1;
    }
    while (newWritten < newRemaining) {
      newLines.push("");
      newWritten += 1;
    }
    inHunk = false;
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];

    if (line.startsWith("new file mode ")) {
      isNewFile = true;
      continue;
    }
    if (line.startsWith("deleted file mode ")) {
      isDeletedFile = true;
      continue;
    }
    if (line.startsWith("--- ")) {
      if (line.slice(4).trim() === "/dev/null") isNewFile = true;
      continue;
    }
    if (line.startsWith("+++ ")) {
      if (line.slice(4).trim() === "/dev/null") isDeletedFile = true;
      continue;
    }

    if (line.startsWith("@@")) {
      closeHunk();
      const match = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/.exec(line);
      if (match) {
        oldRemaining = match[2] === undefined ? 1 : Number(match[2]);
        newRemaining = match[4] === undefined ? 1 : Number(match[4]);
        oldWritten = 0;
        newWritten = 0;
        inHunk = true;
      }
      continue;
    }

    // "\ No newline at end of file": ignore
    if (line.startsWith("\\")) continue;

    if (!inHunk) continue;

    const marker = line.charAt(0);
    const content = line.slice(1);

    if (marker === " ") {
      oldLines.push(content);
      newLines.push(content);
      oldWritten += 1;
      newWritten += 1;
    } else if (marker === "-") {
      oldLines.push(content);
      oldWritten += 1;
    } else if (marker === "+") {
      newLines.push(content);
      newWritten += 1;
    } else if (line === "") {
      oldLines.push("");
      newLines.push("");
      oldWritten += 1;
      newWritten += 1;
    }
  }

  closeHunk();

  if (oldLines.length && oldLines[oldLines.length - 1] === "") oldLines.pop();
  if (newLines.length && newLines[newLines.length - 1] === "") newLines.pop();

  return {
    oldText: oldLines.join("\n"),
    newText: newLines.join("\n"),
    isNewFile,
    isDeletedFile,
  };
}
