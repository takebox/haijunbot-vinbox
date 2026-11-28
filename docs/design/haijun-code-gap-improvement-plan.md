# Improvement Plan and Methods Benchmarked against Haijun Code

> Status: **Plan design (pending review)**
> Date: 2026-10-05
> Scope: `src/haijunbot/haijunbot_agent/`, `src/haijunbot/haijunbot_utils/`, `src/haijunbot/haijunbot_tools/`, `src/haijunbot/haijunbot_service/`, `browser_extension/`
> Related: this document is revised from the "HaijunBot vs Haijun Code Feature Gap Analysis" and the user's item-by-item clarifications

---

## 0. Background

Previously, a feature gap analysis between HaijunBot and Haijun Code was done, listing 8 capabilities that "Haijun Code has, HaijunBot lacks/is weaker in". After the user's item-by-item clarification, several of them **already have equivalents in HaijunBot**, just with different mechanics/forms, and they need to be aligned with HaijunBot's existing design rather than copied from Haijun Code.

This document, based on **source-code verification**, responds to the 8 gaps item by item, giving improvement plans and methods.

---

## 1. Item-by-Item Gap Clarification and Current State Verification

| #   | Original Gap                          | User Clarification                         | Source-Code Verification Conclusion                                                                                                                                            |
| --- | ------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Project-level instruction file (HAIJUN.md/AGENTS.md) | rule.md in rules is also auto-loaded, comparable to HAIJUN.md | ✅ Confirmed: HaijunBot already has a three-layer rule system (builtin/project/global); the project-level `.haijunbot/rules/` is auto-scanned, and `.haijunbot/rules/rule.md` is auto-loaded as the project overview (`rules_manager.py:_load_project_rule_file`) |
| 2   | Hooks lifecycle                       | Hooks can also be configured, registered with Python files, and hook points can be added | ✅ Confirmed: `callback_loader.py` already supports 16 events, registered via Python files, with three kinds: intercept/modify/notify |
| 3   | Tracks + Plugins + `/` commands       | HaijunBot uses `@` instead of `/`             | ✅ Confirmed: HaijunBot uses `@` to trigger built-in commands (`input.py:BUILTIN_COMMANDS` + `builtin_replace_map.py`) |
| 4   | Multi-device/remote control            | HaijunBot's Web frontend can be accessed across devices | ✅ Confirmed: HaijunBot has a web gateway, naturally cross-device |
| 5   | Deep CI/CD integration                 | Could be supplemented                      | ⚠️ Needs supplementing: no official CI action templates or PR auto-review                                  |
| 6   | Agent SDK                              | Could be optimized and provided            | ⚠️ Needs optimization: a Python SDK exists, but its positioning and ecosystem could be strengthened           |
| 7   | Interactive diff/IDE plugins           | The IDE is not important; it can be skipped | ❌ Ignored (the user judged it unimportant, not doing it)                                                       |
| 8   | Prompt Caching                         | This is not important                      | ❌ Ignored (the user judged it unimportant)                                                                     |

---

## 2. Item-by-Item Improvement Plans

### 2.1 Project-level instruction file (benchmarked against HAIJUN.md)

**Current state verification**: HaijunBot already has a three-layer rule system, and project-level rules travel with the repository (`<project root>/.haijunbot/rules/`), with `rule.md` auto-loaded as the project overview. Its positioning matches Haijun Code's HAIJUN.md, but **the triggering is different**: Haijun Code "always loads the project root HAIJUN.md", while HaijunBot uses "rule files + automatic task matching".

**Improvement direction**: make HaijunBot **compatibly read the repository root `AGENTS.md`/`HAIJUN.md`** (a community convention, shared across tools) as a supplementary source for the project overview.

**Improvement method**:

1. In `_load_project_rule_file()` of `rules_manager.py`, in addition to loading `.haijunbot/rules/rule.md`, **additionally check for the repository root `AGENTS.md` (or `HAIJUN.md` if absent)**, wrapping its content as a `project:agents` rule.
2. Priority: `.haijunbot/rules/rule.md` > `AGENTS.md` > `HAIJUN.md` (higher priority overrides in case of conflicts).
3. To handle: AGENTS.md may be very large, so it should be truncated by a token budget (reusing the same budget logic as `get_context_token_count` and `methodology_token_limit`).
4. Compatibility: if the project already has `.haijunbot/rules/rule.md`, AGENTS.md is supplementary rather than a replacement, merged into the injection.

**Files involved**: `src/haijunbot/haijunbot_agent/rules_manager.py`
**Priority**: P1 (high value, small change, compatible with community conventions)
**Verification**: create a project containing `AGENTS.md` and confirm its content is injected into the system prompt; when `.haijunbot/rules/rule.md` is also present, both coexist without conflicts.

---

### 2.2 Hooks lifecycle (add hook points)

**Current state verification**: `callback_loader.py` already supports 16 events (`events.py`), with three kinds of callbacks:

- **Intercepting (hook)**: `BEFORE_TOOL_CALL` (returns False to intercept)
- **Modifying (modifier)**: `BEFORE_MODEL_CALL`, `BEFORE_SUMMARY` (return the modified value)
- **Notifying (event)**: `AFTER_TOOL_CALL`, `AFTER_SUMMARY`, etc.

Registered via Python files under `~/.haijunbot/hooks/` (or the config directory), supporting `# requirements:` for automatic dependency installation.

**Improvement direction**: add high-value hook points for the **coding workflow**, matching the coverage of Haijun Code's PreToolUse/PostToolUse/SessionStart.

**Improvement method** (new hook points, ordered by value):

| New hook point          | Type        | Trigger Time            | Typical Use Case                                  |
| ----------------------- | ----------- | ----------------------- | ------------------------------------------------- |
| `AFTER_FILE_EDIT`       | Notifying   | After every file edit completes | Auto-format, lint, git diff hints              |
| `BEFORE_GIT_COMMIT`     | Intercepting| Before the Agent commits | Pre-commit lint/test gates, commit message validation |
| `AFTER_GIT_COMMIT`      | Notifying   | After the commit completes | Push, CI trigger, notifications                 |
| `BEFORE_TASK_START`     | Intercepting| Before each task starts  | Environment preparation, permission checks       |
| `AFTER_TASK_COMPLETE`   | Notifying   | After the task completes | Summary, reporting, cleanup                       |
| `BEFORE_SESSION_START`  | Intercepting| When the session starts  | Load project-specific configuration               |
| `AFTER_SESSION_END`     | Notifying   | When the session ends    | Save state, statistics                            |

**Implementation points**:

1. In `events.py`, define the new event constants and TypedDict payload types.
2. In the Agent main loop (`run_loop.py`), `emit` the new events at the corresponding lifecycle points.
3. Reuse the generic loader `callback_loader.load_event_callbacks()`; you only need to add the registration in `load_all_event_callbacks()`, with no new loading logic needed.
4. The file-edit hook needs to fire after the `edit_file`/`write_file` tools execute (can be added in the tool-execution wrapper layer).

**Files involved**: `src/haijunbot/haijunbot_agent/events.py`, `src/haijunbot/haijunbot_agent/callback_loader.py`, `src/haijunbot/haijunbot_agent/run_loop.py`, `src/haijunbot/haijunbot_tools/` (tool-execution points)
**Priority**: P1 (directly improves coding-workflow automation; reuses the existing loader; changes are manageable)
**Verification**: write a test callback for each new event to confirm the trigger timing and payload are correct; confirm the default behavior is unaffected when there are no callbacks.

---

### 2.3 `@` built-in commands (benchmarked against `/` commands)

**Current state verification**: HaijunBot uses `@` to trigger built-in commands, in two kinds:

- **Prompt-template commands**: `BUILTIN_REPLACE_MAP` in `builtin_replace_map.py`, such as `@Web`, `@Dev`, `@Fix`, `@Check` (append/replace user input)
- **Built-in command markers**: `BUILTIN_COMMANDS` in `input.py` + processed by `builtin_input_handler.py`, executed immediately

The `@` and `/` are merely a difference in the trigger symbol; the functionality is equivalent.

**Improvement direction**: **enrich the `@` command library**, matching Haijun Code's common commands such as `/init`, `/review`, `/plan`, `/clear`, `/compact`.

**Improvement method**:

1. Add new prompt-template commands (`builtin_replace_map.py`):
   - `@Review`: code review template (reuse the code_review rule)
   - `@Plan`: generate an implementation plan
   - `@Test`: add tests for the selected module
   - `@Refactor`: refactoring check template
   - `@Security`: security scan template
2. Add new built-in command markers (`input.py` + `builtin_input_handler.py`):
   - `@clear`: clear the current session context
   - `@compact`: manually trigger context compression
   - `@status`: view the current task/context status
   - `@help`: list all `@` commands
3. Write the command descriptions into `BUILTIN_COMMANDS`; auto-completion (prompt_toolkit + fzf) takes effect automatically, with no extra changes to the completion logic.

**Files involved**: `src/haijunbot/haijunbot_utils/builtin_replace_map.py`, `src/haijunbot/haijunbot_utils/input.py`, `src/haijunbot/haijunbot_agent/builtin_input_handler.py`
**Priority**: P2 (experience enhancement, does not block core functionality)
**Verification**: typing `@` triggers auto-completion; after selecting a command the behavior is correct; `@help` can list all commands.

---

### 2.4 Web cross-device access

**Current state verification**: HaijunBot has a web gateway (`haijunbot-service`); simply accessing it with a browser makes it naturally cross-device (any device with a browser).

**Improvement direction**: **optimize mobile adaptation and cross-device resumption**, rather than adding new endpoints.

**Improvement method**:

1. **Mobile responsive optimization**: inspect the frontend (`src/haijunbot/haijunbot_service/frontend/src/App.vue`) layout on small screens, focusing on the mobile display of the pet lobby, command palette, and session list.
2. **Cross-device resumption**: sessions already support auto-save/restore (per the README); ensure the Web frontend can restore the same session after switching devices (session storage decoupled from the device).
3. **PWA support**: the frontend already has `manifest.webmanifest` and `sw.js` (confirmed in the build artifacts), which can be completed into an installable PWA to improve the mobile experience.

**Files involved**: `src/haijunbot/haijunbot_service/frontend/src/`
**Priority**: P3 (experience optimization)
**Verification**: a mobile browser accesses the web gateway and core functions work; sessions are restorable across devices.

---

### 2.5 Deep CI/CD integration (supplement)

**Current state verification**: HaijunBot has a headless mode (`no_interaction_mode`), scheduled tasks, and `-p`-style non-interactive entry points, but **no official CI action templates or ready-made PR auto-review integration**.

**Improvement direction**: provide **out-of-the-box CI integration**, letting HaijunBot run inside GitHub Actions / GitLab CI.

**Improvement method**:

1. **Add `.github/workflows/` templates** (placed in the repo's `scripts/ci/` or as documentation examples):
   - `haijunbot-pr-review.yml`: PR-triggered; reviews the diff and comments (reusing the code_review rule)
   - `haijunbot-issue-triage.yml`: issue-triggered; auto-categorizes/tags
   - `haijunbot-ci-test.yml`: commit-triggered; runs tests and reports
2. **Provide a `hca -p` non-interactive review command wrapper**: confirm `haijunbot-code-agent` supports non-interactive + structured output (`--output-format json`) for CI parsing.
3. **Documentation**: add a "CI integration guide" in the README or `docs/`, providing copy-pasteable action templates.
4. **PR auto-review**: use `sub_code_agent` or an independent Agent to review `git diff` and output structured conclusions (issue list + severity level + suggestions) as a PR comment in CI.

**Files involved**: `scripts/ci/` (new), `docs/` (new guide)
**Priority**: P1 (high value for team collaboration; purely additive, no regression risk)
**Verification**: run the review flow locally with a sample PR diff and confirm the output is structured; try the action templates in a real repository.

---

### 2.6 Agent SDK (optimization) — ❌ deleted, not implementing

> **Status update (2026-10-05)**: this plan was once implemented as `src/haijunbot/haijunbot_agent/sdk.py`, but review found that the `run_agents_parallel` parallel orchestration API has serious concurrency problems under a real `CodeAgent`: ① `set_current_agent` writes to a process-level global stack, so `get_current_agent()` can return the wrong Agent when running in parallel; ② `os.getcwd()`/`os.chdir` are process-level globals, so when running in parallel each thread's working directory interferes with the others, and a task may execute in the wrong repository. Therefore this SDK module, its tests, and documentation references have all been deleted, and it will **no longer be implemented**. HaijunBot's programmatic entry point remains the `CodeAgent`/`Agent` classes (`from haijunbot.haijunbot_code_agent.code_agent import CodeAgent`).

**Original plan (deprecated)**:

**Current state verification**: HaijunBot has a Python SDK (`from haijunbot.haijunbot_code_agent.code_agent import CodeAgent`) that can invoke an Agent to run tasks, but its positioning is "call an Agent" rather than "build a complete SDK ecosystem for custom Agents".

**Improvement direction**: **strengthen the SDK's programmability**, letting developers orchestrate multiple Agents, inject custom tools/rules, and control permissions.

**Improvement method**:

1. **SDK orchestration API**: provide high-level orchestration functions such as `run_agents_parallel([...])` and `pipeline([...])`, reusing the existing multi-Agent capabilities of `gateway_manager`.
2. **SDK injection capabilities**: allow injecting custom tools/rules/model groups when constructing an Agent (`Agent(config_file=..., tool_group=...)`), documenting the parameters.
3. **SDK callbacks**: expose Agent lifecycle events (reusing the hook points from 2.2) to SDK callers.
4. **Structured output**: provide `agent.run_structured(task, schema)`, returning JSON instead of plain text.
5. **Documentation**: add a "Python SDK advanced usage" section to the README, with orchestration, injection, and callback examples.

**Files involved**: `src/haijunbot/haijunbot_agent/`, `src/haijunbot/haijunbot_code_agent/`, `README.md`
**Priority**: P2 (enhances programmability, does not block existing functionality)
**Verification**: write SDK integration tests to confirm orchestration/injection/callbacks work.

---

### 2.7 Interactive diff / IDE plugins

**User judgment: not important, not doing it.** Not included in the scope of improvement. (HaijunBot's Web frontend already bakes in a Monaco editor + LSP + Git diff, so the coding experience is basically sufficient; VS Code/JetBrains plugins have high cost and limited value, hence not doing them.)

---

### 2.8 Prompt Caching

**User judgment: not important, ignored.** Not included in the scope of improvement. (HaijunBot already has a context-compression mechanism, and the caching strategy depends on the model platform, so its value is limited.)

---

## 3. Overall Implementation Roadmap

| Phase                  | Content                                                                 | Priority | Risk                              |
| ---------------------- | ----------------------------------------------------------------------- | -------- | --------------------------------- |
| **Phase A (near term)** | 2.1 Project-level AGENTS.md compatibility · 2.2 Add hook points · 2.5 CI integration templates | P1       | Low (reuses existing mechanisms, purely incremental) |
| **Phase B (mid term)**  | 2.3 Enrich `@` commands · 2.6 SDK enhancement                           | P2       | Medium (some involve frontend changes) |
| **Phase C (long term)** | 2.4 Mobile/PWA                                                           | P3       | Medium (frontend changes require a rebuild) |

> 2.7 (IDE plugins) and 2.8 (Prompt Caching) were judged unimportant by the user, so they are **not done** and not included in the roadmap.

**Suggested starting order**: first do 2.1 (AGENTS.md compatibility) and 2.2 (hook points) of phase A — both are small, high-value changes with no regression risk and can be quickly implemented and verified; then move on to 2.5 CI integration.

---

## 4. Design Principles

- **Don't copy, only align**: Haijun Code is a single-user coding assistant; HaijunBot is a collaborative platform. Improvements should strengthen HaijunBot's existing capabilities (rules, hooks, `@`, Web), not introduce mechanisms it does not have.
- **Reuse existing mechanisms**: hooks reuse the `callback_loader` generic loader; commands reuse the `@` system; rules reuse the three-layer rule system; CI reuses the headless mode.
- **Purely incremental, reversible**: all improvements are added capabilities that do not change existing default behavior; behavior is unchanged with no callbacks/no commands/no AGENTS.md.
- **Compatible with community conventions**: AGENTS.md is a cross-tool convention; supporting it lets HaijunBot directly reuse the instruction files of community projects.

---

## 5. Appendix: Source-Code Verification Basis

- Three-layer rule system: `src/haijunbot/haijunbot_agent/rules_manager.py` (`_load_project_rule_file` loads `.haijunbot/rules/rule.md`; `get_all_available_rule_names` scans the builtin/project/global directories)
- Hook mechanism: `src/haijunbot/haijunbot_agent/callback_loader.py` (`load_event_callbacks` supports the three kinds hook/modifier/event), `src/haijunbot/haijunbot_agent/events.py` (16 event constants)
- `@` commands: `src/haijunbot/haijunbot_utils/input.py` (`BUILTIN_COMMANDS`), `src/haijunbot/haijunbot_utils/builtin_replace_map.py`, `src/haijunbot/haijunbot_agent/builtin_input_handler.py`
- Web cross-device: `src/haijunbot/haijunbot_service/frontend/` (`manifest.webmanifest`, `sw.js` support PWA)
- Context compression: `src/haijunbot/haijunbot_agent/run_loop.py` (`_adaptive_compression`), `src/haijunbot/haijunbot_agent/__init__.py` (`_start_background_pre_compression`)