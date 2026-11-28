# Editor-Agent Integration Architecture Design

> Goal: turn the Monaco editor into a visual workbench for Agent-user collaboration, not an isolated editor.
> This document is based on verified current code and gives the message format, frontend/backend change points, and priorities for each integration point.
> Corresponding tasks: task-326 (architecture design), task-327~333 (feature implementation).

---

## 1. Current State Inventory (verified)

### 1.1 Frontend editor (Vue 3 + Monaco)

- Main file: `src/haijunbot/haijunbot_service/frontend/src/App.vue` (24421 lines); the editor logic is concentrated in App.vue + `components/WorkspacePanel.vue`.
- **Existing capabilities**: multi-language highlighting, multi-tab, multi-pane split, code folding, bracket matching, minimap, smart hints, LSP (hover/completion/diagnostics), save, read-only toggle, Git diff, global search, file tree, command palette (Ctrl+P), file heartbeat auto-refresh (polling mtime to detect Agent-external modifications).
- **Key functions** (App.vue):
  - `openWorkspaceFile(path, agentId)` (:4934) -- opens a file into the editor (core entry; all "open file" operations should go through it).
  - `resolveAgentRelativePath(relativePath, agentId)` (:4481) -- resolves a relative path to an absolute path based on the Agent working_dir.
  - `openFileSearchResult` (:4765) / `openGlobalSearchResult` (:4769) -- opens search results and positions via `revealLineInCenter` + `setSelection`.
  - `checkActiveWorkspaceFileHeartbeat` (:4878) -- polls mtime to detect external modifications.
- **LSP client**: `src/lsp/manager.js` (569 lines), a self-built lightweight JSON-RPC over WebSocket, reusing connections per (serverId, root); three providers are already registered (hover/completion/diagnostics); isolated per language; silently degrades on failure; **never disposes models**.
- **Single source of truth for command palette actions**: `src/actions/registry.js` (1109 lines), a pure module that triggers App.vue functions via `ctx` callbacks.

### 1.2 Backend message channel (app.py, 10531 lines)

- Unified message format: `{"type": "...", "payload": {...}, "seq": N}`.
- Publish mechanism: `self._router.publish(message, session_id, connection_id)`.
- **`output` message** (app.py:547): `payload` contains `text/output_type/timestamp/lang/traceback/section/context`; `context` contains `agent_id`; there is **no file path field**.
- **`eval_js_request` channel already exists** (app.py:744): `payload={call_id, code, timeout}`; the frontend `handleEvalJsRequest` (App.vue:14857) executes arbitrary JS and returns `eval_js_result`. This is a **bidirectional** channel and the Agent can already use it to run JS in the frontend -- but it is a "generic escape hatch" and not appropriate as the canonical channel for structured file instructions.

### 1.3 Backend symbol-level capabilities (code_analyzer)

- `src/haijunbot/haijunbot_code_agent/code_analyzer/context_manager.py`:
  - `find_definition(symbol_name, file_path)` (:187) -> Symbol
  - `find_references(symbol_name, file_path)` (:106) -> List[Reference]
  - `impact_analyzer`, `dependency_analyzer`, `symbol_table_db`, etc.
- These are capabilities of the **Agent (Python side)**, a separate system from the frontend LSP (JS side).

---

## 2. Integration Architecture Overview

```text
┌───────────────────────────── Frontend (Vue 3 + Monaco) ─────────────────────────┐
│                                                                                 │
│  App.vue handleMessage() -- message dispatch hub                                │
│    ├─ type='editor_open_file'   -> openWorkspaceFile + revealLineInCenter       │
│    ├─ type='editor_diff'        -> open Git diff view (Agent-change visualization) │
│    └─ type='eval_js_request'    -> existing, generic JS execution                │
│                                                                                 │
│  actions/registry.js -- single source of truth for actions                      │
│    ├─ editor function actions (format/goto line/outline/problems panel...)      │
│    └─ Agent-integration actions ("have the Agent analyze the selected code"...) │
│                                                                                 │
│  lsp/manager.js -- lightweight LSP client (reuses connections)                  │
│    ├─ existing: hover / completion / diagnostics                                │
│    └─ new: definition / references / implementation / documentSymbols /         │
│              documentFormatting / rename                                        │
│                                                                                 │
│  Monaco editor -- context menu + shortcuts + selected content                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                              │  WebSocket (JSON-RPC style messages)
                              ▼
┌───────────────────────────── Backend (app.py) ─────────────────────────────────┐
│  WebGateway.emit_output / request_input / publish_execution_event               │
│  -- new: publish_editor_command(agent_id, command)                              │
│  Agent side: code_analyzer (symbol-level) + file operation tools                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Core principles**:

1. **Agent integration takes priority over isolated editor features** -- every editor feature should be evaluated with "can the Agent benefit/trigger/integrate with this?".
2. **Reuse existing channels**: LSP reuses `lsp/manager.js`; Agent instructions reuse `app.py publish` + frontend `handleMessage`; actions reuse `actions/registry.js`.
3. **No new third-party dependencies**.

---

## 3. Integration Point 1: Agent -> Editor Instruction Channel (highest priority)

### 3.1 Requirements

When the Agent references files / locates code in a conversation, the frontend editor should automatically open the corresponding file and jump to the specified line/column. This is the core experience of "Agent-user collaboration".

### 3.2 Message format (new `editor_open_file` type)

```jsonc
// Backend -> Frontend (via _router.publish, session_id=None to broadcast to all sessions)
{
  "type": "editor_open_file",
  "payload": {
    "agent_id": "agent-xxx", // target Agent (determines working_dir and node_id)
    "path": "src/foo/bar.py", // path relative to the Agent working_dir (or an absolute path)
    "line": 42, // optional, 1-based, jump line
    "column": 5, // optional, 1-based, jump column
    "select_start": 40, // optional, selection range start (character offset within the line)
    "select_end": 50, // optional, selection range end
    "reveal": true, // optional, whether to center the view (default true)
  },
  "seq": 123,
}
```

### 3.3 Backend change points (app.py)

Add a new method to `WebGateway`:

```python
def publish_editor_command(self, agent_id: str, command: str, payload: dict) -> None:
    """Broadcast an editor instruction (e.g. open file / goto line) to all frontends."""
    message = {
        "type": f"editor_{command}",
        "payload": {"agent_id": agent_id, **payload},
    }
    self._router.publish(message, session_id=None)
```

- On the Agent side, call it in the "references file" tool callback (e.g. after the `open_file` tool succeeds, or when a file path is detected in streaming conversation output).
- **Minimal change**: the backend only adds one publish helper function + triggers it at the right callback; no new dependencies.

### 3.4 Frontend change points (App.vue handleMessage)

Add a new branch in `handleMessage` (:14376) (before `eval_js_request`):

```js
} else if (type === 'editor_open_file') {
  handleEditorOpenFile(payload)
}
```

Add a new handler:

```js
async function handleEditorOpenFile(payload) {
  const agentId = payload?.agent_id || currentAgentId.value;
  const path = resolveAgentRelativePath(payload?.path, agentId);
  if (!path) return;
  await openWorkspaceFile(path, agentId); // reuse the existing entry point
  await nextTick();
  const modelData = editorModels.get(path);
  const view = getActiveWorkspaceView();
  if (!view || !modelData) return;
  const line = Number(payload?.line || 1);
  const col = Number(payload?.column || 1);
  view.revealLineInCenter(line); // center positioning
  if (payload?.select_start != null && payload?.select_end != null) {
    view.setSelection(
      new monaco.Selection(
        line,
        payload.select_start + 1,
        line,
        payload.select_end + 1,
      ),
    );
  }
  view.setPosition({ lineNumber: line, column: col });
  view.focus();
}
```

### 3.5 Relationship to the existing `eval_js_request`

- `eval_js_request` is the generic escape hatch (arbitrary JS); keep it for scenarios that cannot be structured.
- `editor_open_file` is a **structured, type-safe** editor instruction that goes through a dedicated branch, enabling precise frontend control, auditing, and graceful degradation.
- **Recommendation**: when later adding an `open_file` tool on the Agent side, uniformly send `editor_open_file` instead of assembling JS via eval_js.

---

## 4. Integration Point 2: Editor Selection -> Send to Agent

### 4.1 Requirements

The user selects a piece of code in the editor and sends the selection to the current Agent via the context menu / command palette, asking the Agent to analyze/explain/modify it.

### 4.2 Frontend change points

1. **actions/registry.js** add a new action (`ctx` callback triggers App.vue functions):

   ```js
   {
     id: "editor-send-selection-to-agent",
     label: "Have the Agent analyze the selected code",
     en: "Send Selection to Agent",
     group: "Current Agent",
     icon: "🤖",
     keywords: ["analyze", "selection", "agent"],
     enabled: (ctx) => !!ctx?.currentAgentId && !!ctx?.getEditorSelection,
     run: (ctx) => ctx.sendSelectionToAgent && ctx.sendSelectionToAgent(),
   }
   ```

2. **App.vue** add `sendSelectionToAgent()`:
   - Get `getSelection()` + `getModel().getValueInRange(range)` from the active editor view to obtain the selected text and file path.
   - Send the text to the current Agent through the existing "send message to Agent" channel (`sendMessageToAgent` / input box injection).
   - Message format: `Analyze the following selected code (file: <path> lines <start>-<end>):\n<selected text>`.
3. **Monaco context menu**: register via `monaco.editor.addAction` or a context menu; the "Have the Agent analyze the selected code" menu item calls `sendSelectionToAgent`.

### 4.3 Message channel

Reuse the existing "user -> Agent" input channel (`input_result` / `send_to_agent`); **no new backend message type is needed**.

---

## 5. Integration Point 3: Agent Modifications -> Editor Real-time Integration

### 5.1 Current state

`checkActiveWorkspaceFileHeartbeat` (:4878) already polls mtime to detect external modifications and auto-refreshes. But there is **no diff visualization** and no real-time "Agent is modifying" feedback.

### 5.2 Enhancement plan

1. **Keep the heartbeat polling** as a fallback (do not break existing functionality).
2. **Add an `editor_diff` message**: after the Agent finishes modifying a file, the backend sends one instruction and the frontend automatically opens the Git diff view to show the changes:

   ```jsonc
   {
     "type": "editor_diff",
     "payload": {
       "agent_id": "agent-xxx",
       "path": "src/foo/bar.py", // optional; show diff for this file only; default shows the whole workspace diff
       "action": "show", // show / refresh
     },
   }
   ```

   The frontend `handleMessage` gets a new branch -> calls the existing `openWorkspaceDiff` / `refreshGitView`.

3. **Auto-flag on heartbeat refresh**: when an external modification is detected and the user has not edited (`!tab.isDirty`), if the content changed after refresh, automatically show a "the Agent has modified this file" prompt with a "view changes" entry (reusing the existing `current-view-diff` action).

### 5.3 Data flow

```text
Agent modifies file -> (file system) -> frontend heartbeat polling detects mtime change
                          -> auto-refresh model content
                          -> flag externalModified / prompt to view changes
Agent finishes modifying -> backend publishes editor_diff -> frontend auto-opens diff view
```

---

## 6. Integration Point 4: LSP Capabilities Connected to Backend code_analyzer

### 6.1 Positioning

- **Frontend LSP** (`lsp/manager.js`) handles **interactive** language features: go to definition/references/implementation, symbol tree, formatting, rename -- depends on a local language server and has good real-time performance.
- **Backend code_analyzer** handles **Agent-side** symbol-level analysis: `find_definition` / `find_references` / `impact_analyzer` / `dependency_analyzer` -- used by the Agent when making modification decisions.

### 6.2 How to connect (without reinventing the wheel)

1. **Frontend editor features** (task-327/330/328) prioritize reusing `lsp/manager.js`'s JSON-RPC channel and extending providers: `textDocument/definition`, `references`, `implementation`, `documentSymbol`, `formatting`, `rename`.
2. **Agent side** continues to use the backend code_analyzer (Python); each serves its own consumer; **no data-layer merge** (to avoid cross-language sync complexity).
3. **Optional integration**: if the frontend LSP is unavailable (language server not installed), the editor's "go to definition" can degrade to calling the backend `code_analyzer.find_definition` (via the existing HTTP API), implementing "LSP first, code_analyzer as fallback".

### 6.3 New LSP provider list (lsp/manager.js)

| Feature             | LSP method                              | Frontend trigger            | Corresponding task |
| ------------------- | --------------------------------------- | --------------------------- | ------------------ |
| Go to definition    | `textDocument/definition`               | F12 / context menu / Ctrl+Click | task-327       |
| Find references     | `textDocument/references`               | Shift+F12 / context menu    | task-327           |
| Go to implementation | `textDocument/implementation`          | Ctrl+F12 / context menu     | task-327           |
| Code formatting     | `textDocument/formatting`               | Shift+Alt+F / on save       | task-328           |
| Problems panel      | `textDocument/publishDiagnostics` (existing) | sidebar "Problems" view | task-329        |
| Outline / symbol tree | `textDocument/documentSymbol`         | sidebar "Outline" view      | task-330           |
| Breadcrumbs         | `documentSymbol` hierarchy              | top breadcrumb              | task-330           |
| Rename symbol       | `textDocument/rename`                   | F2                          | task-331           |

> **Constraint**: all providers reuse the existing `getClientForModel` / `ensureClient` connection reuse mechanism; silently degrade on failure; **never dispose models**.

---

## 7. Priority Ordering and Task Mapping

| Priority | Feature                              | Type              | Dependencies                          | Corresponding task |
| -------- | ------------------------------------ | ----------------- | ------------------------------------- | ------------------ |
| **P0**   | Agent->editor open file / goto line | Agent integration | backend publish + frontend handleMessage | task-332        |
| **P0**   | Editor selection -> Agent            | Agent integration | actions/registry + App.vue            | task-333           |
| **P1**   | Agent modifications -> diff integration | Agent integration | heartbeat + editor_diff              | merged into task-332/329 |
| **P1**   | LSP go to definition/references/implementation | pure editor + LSP | lsp/manager.js                        | task-327           |
| **P1**   | Code formatting                      | pure editor + LSP | lsp/manager.js                        | task-328           |
| **P2**   | Problems panel                       | pure editor + LSP | reuse diagnostics                     | task-329           |
| **P2**   | Outline / symbol tree + breadcrumbs  | pure editor + LSP | lsp/manager.js                        | task-330           |
| **P2**   | Go to line / auto-save / status bar  | pure editor       | App.vue                               | task-331           |

**Recommended implementation order**: do the two P0 Agent integration points first (task-332/333, delivering the core value of "editor-Agent collaboration"), then the P1 LSP enhancements (task-327/328), finally the P2 panel-type features (task-329/330/331).

---

## 8. Changed File List (summary)

| File                                                                                 | Changes                                                                                                                    |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| `src/haijunbot/haijunbot_web_gateway/app.py`                                               | Add `publish_editor_command`; trigger when the Agent references a file / finishes modifying                              |
| `src/haijunbot/haijunbot_service/frontend/src/App.vue`                                     | `handleMessage` adds `editor_open_file` / `editor_diff` branches; `handleEditorOpenFile`; `sendSelectionToAgent`; context menu registration |
| `src/haijunbot/haijunbot_service/frontend/src/actions/registry.js`                         | Add editor function actions + Agent-integration actions                                                                    |
| `src/haijunbot/haijunbot_service/frontend/src/lsp/manager.js`                              | Extend definition/references/implementation/documentSymbol/formatting/rename providers                                      |
| `src/haijunbot/haijunbot_service/frontend/src/lsp/registry.js`                             | Register providers by capability if needed                                                                                  |
| `src/haijunbot/haijunbot_service/frontend/src/components/WorkspacePanel.vue`               | Problems panel / outline view / status bar rendering                                                                       |
| `src/haijunbot/haijunbot_service/frontend/src/components/WorkspacePaneTree.vue`            | Sidebar views (Problems / Outline)                                                                                         |

---

## 9. Verification Criteria

- `npm run build` passes after each feature change.
- **Agent integration chain** (P0):
  - Agent sends `editor_open_file` -> frontend auto-opens the file and jumps to the line (real-device verification).
  - Select code in the editor -> context menu "Analyze with Agent" -> message reaches the Agent (real-device verification).
- **LSP enhancements** (P1/P2): F12 go to definition, Shift+F12 references, formatting, problems panel, outline are interactive (`npm run build` + browser verification).
- No regressions: heartbeat refresh, split views, read-only toggle, multi-tab undo stack (no model disposal).

---

## 10. Risks and Mitigation

| Risk                                        | Mitigation                                                                                                              |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Agent instruction channel abuse (arbitrary JS) | replace the eval_js escape hatch with structured `editor_open_file`; keep eval_js but only for scenarios that cannot be structured |
| Duplicate LSP provider registration         | reuse the `registeredProviders` Set for dedup (manager.js:29)                                                           |
| Breaking the multi-tab undo stack           | all changes never dispose models (per existing constraint)                                                               |
| Heartbeat conflicting with user edits       | auto-refresh only when `!tab.isDirty` (reuse the existing logic at :4900)                                                |
| Large backend change surface                | only add the publish helper + callback trigger points; do not touch the existing message chain                            |