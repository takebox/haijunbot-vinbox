import hljs from "highlight.js";

// Language mapping table
const langMap = {
  py: "python",
  js: "javascript",
  ts: "typescript",
  vue: "vue",
  java: "java",
  c: "c",
  cpp: "cpp",
  h: "cpp",
  hpp: "cpp",
  go: "go",
  rs: "rust",
  rb: "ruby",
  php: "php",
  swift: "swift",
  kt: "kotlin",
  scala: "scala",
  sql: "sql",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  yaml: "yaml",
  yml: "yaml",
  json: "json",
  toml: "toml",
  ini: "ini",
  cfg: "ini",
  conf: "ini",
  xml: "xml",
  html: "html",
  css: "css",
  scss: "scss",
  less: "less",
  md: "markdown",
  txt: "plaintext",
  log: "plaintext",
};

/**
 * Renders the file path in the diff title bar.
 * Adds the data-diff-file-path marker so the message container can delegate the
 * click and open the file in the editor.
 * @param {string} filePath - file path (relative or absolute)
 * @returns {string} escaped HTML
 */
function renderFilePath(filePath) {
  const path = filePath || "Unknown";
  return `<span class="diff-file-path" data-diff-file-path="${escapeHtml(path)}" title="Click to open in editor">📝 ${escapeHtml(path)}</span>`;
}

/**
 * Gets the language type from a filename
 * @param {string} filename - filename
 * @returns {string} language type
 */
export function getLanguageFromFilename(filename) {
  if (!filename) return "plaintext";
  const ext = filename.split(".").pop().toLowerCase();
  return langMap[ext] || "plaintext";
}

// highlight.js has no built-in vue support (consistent with App.vue's marked rendering; fall back to xml)
const HLJS_LANGUAGE_ALIAS = {
  vue: "xml",
};

// Normalize to a highlight.js-registered language id; return "" if not registered (callers fall back to plain text)
function resolveHljsLanguage(language) {
  const normalized = HLJS_LANGUAGE_ALIAS[language] || language;
  return hljs.getLanguage(normalized) ? normalized : "";
}

/**
 * HTML escape
 * @param {string} text - text to escape
 * @returns {string} escaped HTML
 */
export function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML.replace(/\n/g, "<br>");
}

/**
 * Whether the current viewport is mobile (consistent with the global breakpoint: <= 768px)
 * @returns {boolean}
 */
function isMobileViewport() {
  return typeof window !== "undefined" && window.innerWidth <= 768;
}

/**
 * Renders a single line of content (preserves indentation + syntax highlighting, falls back to plain text on failure)
 * @param {string} line - line content
 * @param {string} language - language type
 * @returns {string} rendered HTML fragment
 */
function renderLineContent(line, language) {
  if (line === null || line === undefined) return "";
  const leadingSpaces = line.match(/^(\s*)/)[0];
  const hljsLanguage = resolveHljsLanguage(language);
  if (!hljsLanguage) {
    // highlight.js has no such language registered: fall back to plain text to avoid repeated internal warnings
    return "&nbsp;".repeat(leadingSpaces.length) + escapeHtml(line);
  }
  try {
    const highlighted = hljs.highlight(line, { language: hljsLanguage }).value;
    return (
      "&nbsp;".repeat(leadingSpaces.length) + highlighted.replace(/^(\s+)/, "")
    );
  } catch (e) {
    // If syntax highlighting does not support the language, fall back to plain text
    console.warn("[highlight.js] Language not supported:", language, e);
    return "&nbsp;".repeat(leadingSpaces.length) + escapeHtml(line);
  }
}

/**
 * Renders the mobile inline diff (single column, not side-by-side)
 *
 * Row mapping rules (no information is lost):
 * - equal: shows the new line number + new content
 * - delete: shows the old line number + old content (red background)
 * - insert: shows the new line number + new content (green background)
 * - replace: first outputs one line of old content (red background), then one line of new content (green background)
 *
 * @param {Object} diffData - diff data object
 * @returns {string} rendered HTML
 */
export function renderInlineDiff(diffData) {
  if (!diffData || !diffData.rows) {
    return '<div class="diff-error">No diff data</div>';
  }

  const { file_path, additions, deletions, rows } = diffData;
  const language = getLanguageFromFilename(file_path);

  let html = '<div class="diff-side-by-side diff-inline">';

  // Header
  html += '<div class="diff-header">';
  html += renderFilePath(file_path);
  html += `<span class="diff-stats">[<span class="diff-additions">+${additions}</span> / <span class="diff-deletions">-${deletions}</span>]</span>`;
  html += "</div>";

  html += '<table class="diff-table">';
  html += "<colgroup><col><col></colgroup>";

  let lastOldLineNum = 0;
  let lastNewLineNum = 0;

  const appendSeparator = () => {
    html += '<tr class="diff-separator"><td colspan="2"></td></tr>';
  };

  const appendLine = (lineNum, content, contentClass) => {
    html += '<tr class="diff-row">';
    html += `<td class="diff-line-num">${escapeHtml(String(lineNum || ""))}</td>`;
    html += `<td class="diff-content ${contentClass}"><code>${content}</code></td>`;
    html += "</tr>";
  };

  rows.forEach((row, index) => {
    const { type, old_line_num, old_line, new_line_num, new_line } = row;

    // Insert a separator when line numbers are non-consecutive (consistent with side-by-side rendering)
    if (index > 0) {
      const isOldLineGap =
        old_line_num && lastOldLineNum && old_line_num - lastOldLineNum > 1;
      const isNewLineGap =
        new_line_num && lastNewLineNum && new_line_num - lastNewLineNum > 1;
      if (isOldLineGap || isNewLineGap) {
        appendSeparator();
      }
    }

    if (old_line_num) lastOldLineNum = old_line_num;
    if (new_line_num) lastNewLineNum = new_line_num;

    if (type === "delete") {
      appendLine(
        old_line_num,
        renderLineContent(old_line, language),
        "diff-deleted",
      );
      return;
    }

    if (type === "insert") {
      appendLine(
        new_line_num,
        renderLineContent(new_line, language),
        "diff-added",
      );
      return;
    }

    if (type === "replace") {
      // Replace: old first, then new, each on its own line to avoid side-by-side squeezing
      appendLine(
        old_line_num,
        renderLineContent(old_line, language),
        "diff-deleted",
      );
      appendLine(
        new_line_num,
        renderLineContent(new_line, language),
        "diff-added",
      );
      return;
    }

    // equal: show the new line number + new content
    appendLine(new_line_num, renderLineContent(new_line, language), "");
  });

  html += "</table>";
  html += "</div>";

  return html;
}

/**
 * Renders a side-by-side diff
 * @param {Object} diffData - diff data object
 * @returns {string} rendered HTML
 */
export function renderSideBySideDiff(diffData) {
  if (!diffData || !diffData.rows) {
    return '<div class="diff-error">No diff data</div>';
  }

  // Narrow mobile screens make each of the two side-by-side columns unreadable; use single-column inline rendering instead
  if (isMobileViewport()) {
    return renderInlineDiff(diffData);
  }

  const { file_path, additions, deletions, rows } = diffData;
  const language = getLanguageFromFilename(file_path);

  let html = '<div class="diff-side-by-side">';

  // Header
  html += '<div class="diff-header">';
  html += renderFilePath(file_path);
  html += `<span class="diff-stats">[<span class="diff-additions">+${additions}</span> / <span class="diff-deletions">-${deletions}</span>]</span>`;
  html += "</div>";

  // Table
  html += '<table class="diff-table">';
  html += "<colgroup><col><col><col><col></colgroup>";

  let lastOldLineNum = 0;
  let lastNewLineNum = 0;

  rows.forEach((row, index) => {
    const { type, old_line_num, old_line, new_line_num, new_line } = row;

    // Check whether a separator is needed (non-consecutive line numbers)
    // Note: the first row is not checked, and checks only happen when line numbers are valid
    if (index > 0) {
      const isOldLineGap =
        old_line_num && lastOldLineNum && old_line_num - lastOldLineNum > 1;
      const isNewLineGap =
        new_line_num && lastNewLineNum && new_line_num - lastNewLineNum > 1;

      // Insert a separator if either side jumps and that side has line numbers
      // Or if both sides have line numbers but only one side jumps (e.g. only one side changed), insert a separator too
      if (isOldLineGap || isNewLineGap) {
        html += '<tr class="diff-separator"><td colspan="4"></td></tr>';
      }
    }

    // Update the previous line numbers
    if (old_line_num) lastOldLineNum = old_line_num;
    if (new_line_num) lastNewLineNum = new_line_num;

    // Row background color classes
    let rowClass = "diff-row diff-row-" + type;

    // Start the table row
    html += `<tr class="${rowClass}">`;

    // Old code column
    if (type === "equal" || type === "delete" || type === "replace") {
      html += `<td class="diff-line-num diff-old-num">${escapeHtml(String(old_line_num || ""))}</td>`;

      // Count and preserve indentation
      let oldContent = "";
      if (old_line) {
        const leadingSpaces = old_line.match(/^(\s*)/)[0];
        let highlighted;
        try {
          highlighted = hljs.highlight(old_line, { language }).value;
          // Prepend explicit &nbsp; before the highlighted result to preserve indentation
          oldContent =
            "&nbsp;".repeat(leadingSpaces.length) +
            highlighted.replace(/^(\s+)/, "");
        } catch (e) {
          // If syntax highlighting does not support the language, fall back to plain text
          console.warn("[highlight.js] Language not supported:", language, e);
          oldContent =
            "&nbsp;".repeat(leadingSpaces.length) + escapeHtml(old_line);
        }
      }

      // For replace and delete, add the deletion background color to the td
      const oldClass =
        type === "replace" || type === "delete" ? "diff-deleted" : "";
      html += `<td class="diff-content diff-old-content ${oldClass}"><code>${oldContent}</code></td>`;
    } else {
      html += '<td class="diff-line-num diff-old-num"></td>';
      html += '<td class="diff-content diff-old-content"></td>';
    }

    // New code column
    if (type === "equal" || type === "insert" || type === "replace") {
      html += `<td class="diff-line-num diff-new-num">${escapeHtml(String(new_line_num || ""))}</td>`;

      // Count and preserve indentation
      let newContent = "";
      if (new_line !== null && new_line !== undefined) {
        // Handle even empty strings to ensure a placeholder is shown
        const leadingSpaces = new_line.match(/^(\s*)/)[0];
        let highlighted;
        try {
          highlighted = hljs.highlight(new_line, { language }).value;
          // Prepend explicit &nbsp; before the highlighted result to preserve indentation
          newContent =
            "&nbsp;".repeat(leadingSpaces.length) +
            highlighted.replace(/^(\s+)/, "");
        } catch (e) {
          // If syntax highlighting does not support the language, fall back to plain text
          console.warn("[highlight.js] Language not supported:", language, e);
          newContent =
            "&nbsp;".repeat(leadingSpaces.length) + escapeHtml(new_line);
        }
        // If the content is empty, add a space placeholder
        if (!newContent) {
          newContent = "&nbsp;";
        }
      } else {
        // When new_line is null or undefined, show an empty placeholder
        newContent = "";
      }

      // For replace and insert, add the insertion background color to the td
      const newClass =
        type === "replace" || type === "insert" ? "diff-added" : "";
      html += `<td class="diff-content diff-new-content ${newClass}"><code>${newContent}</code></td>`;
    } else {
      html += '<td class="diff-line-num diff-new-num"></td>';
      html += '<td class="diff-content diff-new-content"></td>';
    }

    html += "</tr>";
  });

  html += "</table>";
  html += "</div>";

  return html;
}
