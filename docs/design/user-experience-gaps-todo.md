# User-Perspective Feature Gap TODO

> Version: 1.0
> Date: 2026-09-22
> Status: To be evaluated
> Source: A static review of the frontend (`src/haijunbot/haijunbot_service/frontend/src/`) and the current documentation, starting from an ordinary user's usage path
> Note: HaijunBot's feature surface is already quite complete (multi-Agent orchestration, symbol-level understanding, multi-user ACL, distributed nodes, browser extension, scheduled tasks, methodology accumulation, etc. are all in place). This list focuses on gaps that **would stall a user or break the experience on real usage paths**, rather than "missing big features".

---

## 1. Onboarding and Help Paths

### 1.1 The frontend has no "Help / Docs" entry point at all

- **Current state**: Searching the entire frontend for `help|docs|FAQ` matches only two CSS comments; there are already 100+ documents under `docs/user-manual/`, but the frontend has no link entry, so users do not know these documents exist.
- **Impact**: When new users run into problems, they can only rely on the one-time onboarding tour or command palette search.
- **Suggestion**: Add an "Open User Docs" action to the command palette; or add a `?` entry to the top-right toolbar.
- **Cost**: Low (the docs already exist, only a link is needed).
- **Priority**: P0

### 1.2 The onboarding tour cannot be re-watched per scenario

- **Current state**: The 5 tours in `OnboardingTour.vue` + `App.vue` (`WELCOME_TOUR_STEPS` / `LOBBY_TOUR_STEPS` / `AGENT_TOUR_STEPS` / `PANEL_TOUR_STEPS` / `SIDEBAR_TOUR_STEPS`) use localStorage to mark them as "seen"; only "Reset onboarding" (reset all) is supported.
- **Impact**: When a user wants to re-watch a specific scenario (such as "how to use the panel"), they can only reset everything.
- **Suggestion**: Add a "tour catalog" so individual scenarios can be re-watched separately.
- **Priority**: P2

### 1.3 No error self-diagnosis / feedback entry point

- **Current state**: No entries such as "Copy diagnostics" or "Report a problem".
- **Impact**: When the WebSocket cannot connect or the Agent will not start, users can only check the browser console themselves.
- **Suggestion**: Add a "Copy diagnostics" button (connection status, version, recent error logs).
- **Priority**: P2

---

## 2. Observability

### 2.1 No token / cost statistics

- **Current state**: Searching the entire frontend for `token|usage|cost` matches only the auth token, with no usage statistics at all.
- **Impact**: When multiple Agents run long tasks, users cannot see consumption at all, hurting trust and cost control.
- **Suggestion**: Show token usage and estimated cost by Agent / session / time dimension.
- **Priority**: P0

### 2.2 No search for session history

- **Current state**: `SessionDialog.vue` (191 lines) only shows a list, with no search/filter.
- **Impact**: Once there are many sessions, finding a historical session means browsing one by one.
- **Suggestion**: Filter by keyword / time / Agent.
- **Priority**: P1

### 2.3 No global "running tasks" overview

- **Current state**: The pet lobby shows pet status, but there is no table listing "what task every Agent is currently running, how long it has run, and where it is stuck".
- **Impact**: In multi-Agent scenarios, it is hard to quickly locate anomalies.
- **Suggestion**: Add a task overview view (can reuse existing Agent status data).
- **Priority**: P1

---

## 3. Portability of Data and Configuration

### 3.1 Configuration cannot be exported / imported

- **Current state**: Searching `App.vue` / `SettingsModal.vue` for `export config|import config|backup` yields zero matches.
- **Impact**: To switch machines or share configuration across a team, users can only copy by hand. There is already a "central Git repository for sharing methodologies/rules", but personal configuration (models, shortcuts, preferences) has no one-click export.
- **Suggestion**: Add configuration export/import (JSON).
- **Priority**: P1

### 3.2 Chat history / session data cannot be exported

- **Current state**: Only "Clear chat history" exists; there is no export.
- **Suggestion**: Support export to Markdown / JSON.
- **Priority**: P2

---

## 4. Mobile and Accessibility

### 4.1 Mobile is "usable" rather than "pleasant to use"

- **Current state**: Mobile interactions are fixed patch by patch (such as the back button and panel switching).
- **Impact**: There is a lack of systematic adaptation (gestures, bottom navigation, long-list performance).
- **Suggestion**: Do a round of systematic mobile review and adaptation.
- **Priority**: P2

### 4.2 No i18n (internationalization)

- **Current state**: Searching `i18n|locale` yields zero matches; everything is hard-coded in Chinese.
- **Impact**: Overseas users cannot use it (the project is open source, the README contains English, and it once won an open-source competition championship).
- **Suggestion**: Introduce an i18n framework, providing at least Chinese and English.
- **Priority**: P2

### 4.3 No accessibility (a11y) support

- **Current state**: No `aria-*`; keyboard focus management basically relies on custom shortcuts.
- **Impact**: Unusable for visually impaired users.
- **Suggestion**: Add semantic tags and focus management.
- **Priority**: P3

---

## 5. Collaboration Scenarios

### 5.1 Weak notification capabilities

- **Current state**: Only two toggles, `notifyOnExit` / `notifyOnInput`, **off by default**, and only system notifications.
- **Impact**: With multiple Agents, key nodes that "need confirmation" are easily missed.
- **Suggestion**: Add strong alerts (when confirmation is needed), notification history, and @-mention alerts.
- **Priority**: P1

### 5.2 No "task templates / common commands"

- **Current state**: Every time a new Agent is created, the requirements must be described again.
- **Impact**: Duplicate work. Methodology accumulation belongs to the Agent side, not a user-side shortcut entry.
- **Suggestion**: Support saving/reusing user-side task templates.
- **Priority**: P2

---

## Priority Summary

| Priority | Gap                                                                                                  | Reason                                             |
| ------ | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| P0     | Frontend documentation entry (1.1)                                                                   | Extremely low cost (docs already exist), directly solves "users don't know docs exist" |
| P0     | token / cost statistics (2.1)                                                                        | The most painful for heavy users, directly affects trust and cost control |
| P1     | Session history search (2.2)                                                                         | Gets stuck once data grows; change is limited to `SessionDialog.vue` |
| P1     | Configuration export / import (3.1)                                                                  | A hard requirement for switching machines / team sharing; implementation is self-contained and low-risk |
| P1     | Running task overview (2.3)                                                                          | A hard requirement for multi-Agent scenarios       |
| P1     | Enhanced notification capabilities (5.1)                                                             | Key nodes are easily missed                        |
| P2     | Tour catalog (1.2), error self-diagnosis (1.3), chat export (3.2), mobile adaptation (4.1), i18n (4.2), task templates (5.2) | Experience polish |
| P3     | Accessibility support (4.3)                                                                          | Long-term item                                     |

---

## Notes

- This list is based on a **static review** of `frontend/src` (`App.vue` 18798 lines + 24 components) and the `README.md` and `docs/user-manual/` directory; no actual product walkthrough was done, and the specific conclusions should be verified on a real machine.
- The "suggestions" for each item are only directional descriptions; the approach and scope of impact must be evaluated separately before implementation.
