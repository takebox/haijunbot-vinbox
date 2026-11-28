---
name: browser_ext_script
description: Triggered when there is a need to write, install, or debug page scripts (Tampermonkey-like scripts) for the HaijunBot browser extension. Triggered whenever the user mentions "browser extension script", "browser_ext script", "script.run", "script management", "page main-world script", or "Tampermonkey script". Not triggered: only using the built-in browser_ext action (use haijunbot_tool_usage); only using hb/Playwright for browser automation (use haijunbot_browser_cli); only writing ordinary Node/Python scripts (use script-generation).
---

# HaijunBot Browser Extension Script Writing Specification

## Rule Introduction

This rule constrains the writing, installation, and debugging of **page scripts** (Tampermonkey-like scripts) in the "HaijunBot Browser Bridge extension".
Such scripts execute in the target tab's **MAIN world** through the extension, and can access the page's own JS objects (such as `window.ze`),
thereby accomplishing operations that the built-in `browser_ext` actions cannot cover. It is suitable for encapsulating a site's complex interactions into reusable actions.

Relevant source code locations (with `{{ haijunbot_src_dir }}` as the HaijunBot source root):

- Script repository: `{{ haijunbot_src_dir }}/browser_extension/background/script_manager.js`
- Script executor: `{{ haijunbot_src_dir }}/browser_extension/background/executors/script_executor.js`
- Routing table: `{{ haijunbot_src_dir }}/browser_extension/background/command_router.js`
- Example script: `{{ haijunbot_src_dir }}/browser_extension/README.md` (contains the script format and a complete example)

## Principles You Must Follow

### 1. The script must be self-contained pure JS source

**Requirement clarification:**

- **Must**: the script source is evaluated in the page's MAIN world with `new Function("module", "exports", src)`,
  so it **must not** use `import` / `export` statements, and must not depend on any variable on the extension side.
- **Must**: export the script object in one of the following two ways:
  - `globalThis.__HAIJUNBOT_SCRIPT__ = { ... }`
  - `module.exports = { ... }` (`module` is passed in as a formal parameter by the executor)
- **Must**: the exported object contains `name` and `actions`; `actions` is a mapping of "action name → `{ run(args) }` or function".
- **Forbidden**: writing `import`/`export`, `require`, or referencing extension background modules in the source.

**Example:**

```js
globalThis.__HAIJUNBOT_SCRIPT__ = {
  name: "mysite",
  version: "1.0.0",
  description: "Operations for a site",
  match: ["example.com"], // informational only; the extension does not enforce interception
  actions: {
    getTitle: { desc: "Read the title", run: () => document.title },
    clickByText: {
      desc: "Click by text",
      params: { text: "string" },
      run: ({ text }) => {
        const el = [...document.querySelectorAll("button")].find(
          (b) => b.textContent.trim() === text,
        );
        if (!el) throw new Error("not found: " + text);
        el.click();
        return { ok: true };
      },
    },
  },
};
```

### 2. The return value must be JSON-serializable

**Requirement clarification:**

- **Must**: the action's return value is processed by `safeSerialize` (`JSON.parse(JSON.stringify(v))`),
  so DOM nodes, functions, circular references, and `undefined` will all be lost or throw an error.
- **Must**: only return primitive types or pure data objects (strings, numbers, booleans, arrays, plain objects).
- **Forbidden**: directly `return document.querySelector(...)` or similar DOM objects or window objects.

### 3. Write operations must be explicit, controllable, and rollback-able

**Requirement clarification:**

- **Must**: actions that modify page/server-side data (submit, delete, send) must be named separately, and **must not** be executed automatically when the script loads.
- **Must**: prioritize providing a corresponding "query" action (such as `getState`) and a "undo" capability (such as the page's built-in undo), to facilitate verification and rollback.
- **Forbidden**: initiating a write operation as soon as the script loads; forbidden to clear content with coarse-grained operations like "select all + delete".

### 4. Validation is weak validation; syntax errors are exposed only at runtime

**Requirement clarification:**

- **Must**: be aware that `validateSource` only performs string-level checks (whether an export marker is present, whether `actions` is present, whether the brackets are balanced),
  and it does **not** do real syntax parsing -- because the MV3 extension page CSP is `script-src 'self'`, which disables `unsafe-eval`.
- **Must**: after installation, be sure to actually run a "read-only action" once to confirm that the script can be evaluated and executed normally.
- **Forbidden**: concluding that a script is usable based only on "installation succeeded".

## Operations You Must Perform

### Operation 1: Writing a script

**Execution steps:**

1. First confirm which window the target page's key JS object hangs on (the top level or inside an iframe),
   and use a read-only probe action to verify reachability before writing the subsequent logic.
2. Write according to the above "script object" structure; give each entry in `actions` a `desc` and `params` to make it easy for the caller to understand.
3. Provide at least one **read-only** action (such as `getState`) as a probe for connectivity and readiness.
4. Use `node --check <file>` for a basic syntax check (this is the minimum safeguard when the extension environment has no eslint).

**Notes:**

- If the page renders inside an iframe, you need to iterate `document.querySelectorAll("iframe")` to get `contentWindow`
  and then look up the target object; accessing a cross-origin iframe will throw, so you must use `try/catch` for fallback.
- When scripts are executed consecutively on the same page, the executor first does `delete globalThis.__HAIJUNBOT_SCRIPT__`,
  so **do not** rely on global state left over from the previous execution.

### Operation 2: Installing a script

**Execution steps:**

1. Install by pasting the source through the extension popup → "Script Management" and installing, or use "Import from local file", or use "Install from URL".
2. The Agent can also go through the gateway to call `script.install`, with parameters `{ name, source, description, match, version }`;
   a script with the same name is overwritten, and the original `id` is retained.
3. After installation, use `script_list` to confirm `script_id`, `enabled`, and `source_size`.

**Notes:**

- The parameter used to call `script_run` is **`script_id` (the script id, in the form `s-xxx`)**, not the script name;
  there are also `script_action` (the name of the action to execute within the script), `script_args` (the parameter object passed to it), and an optional `tab_id`.
- These three actions are already exposed as actions of the `browser_ext` tool: `script_list` / `script_get` / `script_run`.
  Install/uninstall/enable-disable/export scripts are likewise already exposed as tool actions: `script_install` / `script_uninstall` /
  `script_set_enabled` / `script_export` (for parameter names, see the "Script Management" table in `browser_ext_usage.md`).
  When lower-level control is needed, you can also go through the gateway HTTP: `POST {master_url}/api/browser-ext/command`,
  body `{ session_id, action:"script.install", params:{...}, timeout }`.
  ⚠️ `{master_url}` must be a **master address reachable from the node where the Agent runs**; do not hardcode `127.0.0.1:8000`
  (when the Agent is on a child node, `127.0.0.1` points to the child node's local machine and cannot connect to the master).
  You can use `gateway_manager(action="get_master_url")` to query the master address actually used by the current node.
- Gateway call: `POST {master_url}/api/browser-ext/command`,
  body `{ session_id, action, params, timeout }`, header `Authorization: Bearer $HAIJUNBOT_AUTH_TOKEN`.
- After changing the extension, the extension must be reloaded at `edge://extensions/` to take effect.

#### Choosing an installation method: avoid the script source entering the context

Script source is often very long, so **do not write the source directly into the conversation**. Choose according to the scenario:

| Scenario                         | Recommended method                                                                  |
| -------------------------------- | ----------------------------------------------------------------------------------- |
| The script is already hosted in a publicly accessible static directory | `browser_ext(action="script_install_from_url", script_url=...)`, with the source downloaded by the extension background |
| The script should remain on the gateway for a long time and be deployable repeatedly   | `script_save` (extension → gateway directory) + `script_load_from_file` (gateway directory → extension) |
| One-off small script             | `script_install` passing `script_source` directly                                   |

**Security boundary of `script_install_from_url` (be sure to know it):**

- The extension side performs SSRF protection on the URL: only `http`/`https` are allowed, and it **rejects loopback and intranet addresses**
  (`127.0.0.1`, `localhost`, `10.x`, `172.16-31.x`, `192.168.x`, `169.254.x`, `::1`, `fe80::`, etc.).
- Therefore **a local/intranet gateway cannot be installed via URL**. If the HaijunBot gateway runs on `127.0.0.1` or an intranet,
  use `script_save` / `script_load_from_file` instead (they go through the token-bearing gateway API and are not subject to this restriction).
- The gateway's `/uploads/` directory is statically mounted (`{data_dir}/uploads` → `{master_url}/uploads/<file>`),
  so a **publicly reachable** gateway can have `.js` placed there and then installed via that URL.
- The script name can be derived from the last segment of the URL (`.../my-script.js` → `my-script`); when it cannot be derived, `script_name` must be passed explicitly.
- The downloaded content is stored only as a **source string**; the extension side never evaluates it in the background (evaluation only occurs in the page main world of `script_run`).

**`script_save` / `script_load_from_file` directory convention:**

- Storage directory: `{data_dir}/browser_scripts/` (defaults to `~/.haijunbot/browser_scripts/`, overridable with `HAIJUNBOT_DATA_DIR`).
- The script name allows only `[A-Za-z0-9_.-]`; `/`, `\`, `..`, and a leading `.` are forbidden, to prevent directory traversal.
- These two actions **only return the path/metadata, not the source**, and are the first choice for backing up and migrating scripts.
  In contrast, `script_export` returns the raw source to the Agent, suitable only for small scripts or when the source really needs to be viewed.

### Operation 3: Debugging and verification

**Execution steps:**

1. First run a read-only action to confirm `{ ok: true, result: ... }`.
2. If a complex return value needs to be read, use `debugger.send_command` + `Runtime.evaluate`
   (`returnByValue: true, awaitPromise: true`), because the return value of `script.execute` is not passed through.
3. After a write operation, use an independent read-only means (such as the server-side interface's `revision`/timestamp) to verify whether it actually took effect.
4. On error, read `err.code` (the `Error` thrown by `cmdError(code, message)`; the code hangs on `err.code`, not in the message).

**Notes:**

- The page CSP may restrict eval in the ISOLATED world, so scripts always execute in the MAIN world.
- If the page submits in real time via WebSocket (such as collaborative editing), a write operation may have **already been persisted** when the call returns,
  so verification must check the server-side version number rather than only looking at the local DOM.
- Coordinate/offset-type operations require establishing a mapping between two coordinate systems (such as "the character offset for reading text" and "the offset for the delete interface"),
  otherwise mixing them will delete the wrong position; after each click, verify the focus element position before continuing.

### Operation 4: Canvas rich-text editors embedded in an iframe

**Background (already measured):** some online document sites render the editor inside an `iframe`, with the body drawn by a `canvas`,
and the editor instance hangs on the iframe's `contentWindow`. Such sites often use WebSocket collaborative editing (Etherpad-style OT),
where **editing is persisted in real time with no save button**, so verifying a write operation must check the server-side `revision`, not just the local DOM.

**Execution steps:**

1. Get the editor object: iterate `document.querySelectorAll("iframe")` and find the editor instance on `contentWindow`,
   with `try/catch` for fallback throughout (a cross-origin iframe will throw).
2. When injecting the script, use **the iframe's own `Function` constructor**: `new w.Function("module","exports",src)`.
   If you use the outer `new Function` and then `fn.call(w, ...)`, `globalThis` still points to the outer window,
   and `w.__HAIJUNBOT_SCRIPT__` cannot be obtained. Before injecting, first `delete w.__HAIJUNBOT_SCRIPT__`.
3. Rich-text writing uniformly goes through the editor's **command layer** (in the form `editor.executeCommandAndMoveCursor({ command, range:{startOffset,endOffset}, data })`).
   **Forbidden** to directly call the low-level OT adapter (such as `editor.otAdaptor.applyBatchOperations(...)`), which corrupts the internal state (reporting `Too many closing tags`).
4. Before writing, first `editor.focus()` to establish a real DOM selection, then `editor.setSelection(offset)`.
5. After writing, read `revision`/`contentBody` via the server-side interface to verify persistence.

**Verified editor capabilities (measured as effective; command names are subject to the target site's actual API):**

| Capability       | Invocation method                                                                                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Plain text insertion | `addTextAndAttribs` + `data:{text}`                                                                                                                                             |
| Rich text     | `addTextAndAttribs` + `data:{text, attribs}`; `attribs` supports `size` (**without px**; `'24'`→`24px`, passing `'24px'` becomes `24pxpx`), `family`, `color`, `bold:'true'`, `href`+`target` |
| Hyperlink     | Same as above, `attribs:{href, target}`                                                                                                                                                  |
| Table insertion   | Go through the editor's clipboard inserter (`editor.clipboard.inserter.*`) to pass in ordinary HTML `<table>`, which is parsed into native table nodes                                                                          |
| Read       | `getText()` / `getHtml()` / `getTextLength()` (returns `[len, font size]`) / `getMacroList()` (**returns a Promise**)                                                                       |

**Unsolved / unstable (do not assume it is usable):**

- **Paragraph-level attributes** (line spacing `lineHeight`, alignment `textAlign`): go through a batch attribute command + `attribs:{lineHeight,textAlign,'tag-start':'p'}`,
  and only take effect when the editor is in a **real interactive state** (the user has clicked the document, there is a real DOM selection, and the range length is 0/1);
  when called after a pure script `setSelection`, the `revision` changes but the paragraph style often does not update. The only stable success path is to **actually click the menu item**.
- **Macro insertion**: directly inserting HTML with macro markers is **not recognized** (`revision` does not change),
  and must go through the editor's macro engine registration flow (`macroEngine.getMacroCreateUtils(key)` returns `macroNode`/`attribute`/`params`/`genNodesByHtml`,
  the core being `coreModelNodeToMacroNode`), not yet solved.
- **Code block**: essentially a macro; `<pre><code>` HTML is filtered out, not yet solved.

#### Key pitfall: the offset systems are inconsistent

- The write operation's `offset` is the editor's **internal offset** (from `editor.otAdaptor.rep.text`);
  it is **inconsistent** with the semantic index of `getText()` (`getText()` contains `\n`, whereas the internal text is padded with spaces).
- **Must** use `editor.otAdaptor.rep.text.indexOf(target text)` to get the internal offset, then `setSelection`;
  directly taking the index from `getText()` to write will insert at the wrong position.
- An offset falling inside a table reports `Error: pos=…, table cannot contain text`; the insertion point must avoid the table interval.

**Other measured pitfalls:**

- Clearing a cell: click into the cell → `End` → `Backspace` × N (give a sufficient N, no side effect if it exceeds).
  **Strictly forbidden to use `Ctrl+A`** (that selects the entire document, and combined with Delete will delete the whole text); use `Home`+`Shift+End`+`Delete` with caution
  (it only acts on the current visual line, and there will be residue when the cell content wraps). Accidental deletion can be undone with `Ctrl+Z`.
- If the cell text is too long it wraps and occupies multiple lines; the `style.top` of the cursor input box reflects **the visual line where the cursor is**, not the top of the cell.
- Click coordinates jitter; after each click you must verify that the cursor input box's `style.left/top` hits the target cell before continuing.
- Sending keyboard events via CDP must provide the complete `key`/`code`/`windowsVirtualKeyCode`/`nativeVirtualKeyCode`;
  `Shift` uses `modifiers=8` and `Ctrl` uses `modifiers=2`, otherwise the event is invalid.
- After each column is filled, the column width changes, so subsequent columns need to re-scan the x coordinates for calibration.
- To extract text from the canvas body you need to hook `CanvasRenderingContext2D.prototype.fillText`, and it must be installed **before rendering**;
  a page that has already rendered needs the hook reinstalled and then a repaint triggered (a CDP wheel event can trigger this).

## Checklist

After completing the task, you must confirm:

- [ ] The script is self-contained pure JS, with no `import`/`export`/`require`
- [ ] Exported via `globalThis.__HAIJUNBOT_SCRIPT__` or `module.exports`, and contains `name` and `actions`
- [ ] All action return values are JSON-serializable
- [ ] There is at least one read-only action as a probe
- [ ] Write operations are named separately, not executed automatically, and have a rollback or verification means
- [ ] Syntax has been checked with `node --check`
- [ ] A read-only action has been actually run to confirm the script can be evaluated and executed
- [ ] Write operations have been verified as effective using an independent means such as the server-side version/timestamp

## Related Resources

- Tool usage: `{{ rule_file_dir }}/haijunbot_tool_usage.md`
- Browser automation (server-side Playwright): `{{ rule_file_dir }}/haijunbot_browser_cli.md`
- General script generation specification: `{{ rule_file_dir }}/script-generation.md`
- Extension documentation: `{{ haijunbot_src_dir }}/browser_extension/README.md`
