# Proposal: Orchestration Engine Failure Cleanup and Human Approval Enhancement

> **Status**: Pending review (proposal first, then implementation)
> **Related report**: `docs/research/agent-tech-report-2026q3.md` (sections 4.1, 6)
> **Nature**: Proposal design document, currently **not implemented**, for maintainers to review and decide.
> **Date**: 2026-10-08

---

## 1. Background and Motivation

In Q3 2026, multi-agent orchestration moved from "academic demos" to "production infrastructure". The industry emphasizes three reliability patterns: **output validation at every handoff point**, **explicit termination conditions** (max retries/loop caps), and **human approval checkpoints** (human-in-the-loop). Multi-Agent system failures are the hardest to debug — the error may be in the 3rd Agent while the symptom appears in the 5th Agent (source: agentbrisk.com).

Current state of HaijunBot (`src/haijunbot/haijunbot_tools/pipeline_runner.py`):

- Already has DAG orchestration, the `on_error` failure strategy, `retry` retries, and the `gate: true` human approval gate.
- **Identified TODO**: on abort/failure, **created Agents are not cleaned up**, leaving residual running Agents (consuming resources). This enhancement was found on 2026-10-08 while investigating "all orchestrated Agents are created but none execute".
- The gate currently "pauses and waits for approval", but the post-approval approve/reject flow and the approval UI experience have room for enhancement.

**Pain points**:

1. After a pipeline failure (abort), created but incomplete phase Agents remain in the system and must be cleaned up manually.
2. Gate approval lacks clear "approve/reject/retry" interactions and audit records.

## 2. Goals

1. **Failure cleanup**: on pipeline abort/failure, automatically clean up phase Agents created by that pipeline that did not complete normally, avoiding residue.
2. **Human approval enhancement**: provide clear approve/reject/retry actions at the gate, and record an approval log (who, when, decision).
3. Maintain backward compatibility: do not break existing orchestration files or behavior.

## 3. Technical Design

### 3.1 Failure Cleanup (pipeline_runner)

Add cleanup logic to the pipeline_runner failure/abort path:

- **Track created Agents**: when creating each phase Agent, pipeline_runner records its agent_id in the pipeline context (the `created_agents` list).
- **Failure cleanup**: when a phase fails and `on_error=abort` (or an overall abort occurs), iterate over `created_agents` and call delete/stop on Agents still in the running state (reusing gateway_manager's `_delete_agent` or `_handle_agent_stop`).
- **Preserve artifacts**: cleaning up Agents does not delete artifacts already written to disk (artifacts are isolated by pipeline_id under `work_dir/.haijunbot/artifacts/<pipeline_id>/`) for later troubleshooting.
- **Idempotent**: the cleanup operation is idempotent; repeated cleanup does not error.
- **Optional switch**: provide a `cleanup_on_failure` config (default true) that can be turned off.

### 3.2 Human Approval Enhancement

Enhance the approval interaction at the gate phase:

- **Approval actions**: approve / reject / retry.
  - Approve: continue to the subsequent phases.
  - Reject: abort the pipeline and clean up.
  - Retry: re-execute the current gate phase.
- **Approval log**: record the approver, time, action, and notes, written to pipeline events (for frontend display and auditing).
- **Approval UI**: the frontend gate overlay provides three buttons + a notes input field.

### 3.3 Integration with the Existing System

| Existing component                     | Change                                                                 |
| -------------------------------------- | ---------------------------------------------------------------------- |
| `pipeline_runner.py`                   | Record created_agents; failure cleanup logic; approval action handling |
| `gateway_manager.py`                   | Reuse `_delete_agent` / `_handle_agent_stop` for cleanup               |
| `pipeline_events.py`                   | Add approval events (approve/reject/retry)                             |
| Frontend (App.vue / OrchestrationView) | Enhance the gate overlay                                               |

## 4. Implementation Steps

1. **Agent tracking**: record agent_id in the pipeline context when pipeline_runner creates an Agent.
2. **Failure cleanup**: the abort/failure path iterates and cleans up running Agents (reusing gateway_manager delete/stop).
3. **Approval actions**: the gate phase supports approve/reject/retry, writing approval log events.
4. **Frontend enhancement**: gate overlay with three buttons + notes.
5. **Tests**: add unit tests for failure cleanup (simulate failure → verify Agents are cleaned up) and approval actions (approve/reject/retry).

## 5. Risks and Limitations

- **Erroneous cleanup**: cleanup may wrongly delete Agents "used for other purposes" → only clean up Agents created by this pipeline that are still running, strictly tracked by created_agents.
- **Cleanup failure**: the delete/stop interface may fail → log the failure, prompt for manual handling, and do not block.
- **Approval misoperation**: reject aborts the pipeline → require double confirmation.
- **Backward compatibility**: cleanup_on_failure defaults to true but can be turned off; approval actions are backward compatible with the existing approve.

## 6. Validation Approach

- Unit tests: failure cleanup (simulate abort → assert created_agents are cleaned up), approval actions, idempotent cleanup.
- Integration: run a pipeline containing a failing phase, observe whether Agents are cleaned up and whether artifacts are preserved.
- Regression: all existing pipeline_runner tests pass.

## 7. Impact Scope

- Main changes: `pipeline_runner.py`, `pipeline_events.py`, frontend gate overlay.
- Impact: core path of the orchestration engine; regression must be handled carefully; cleanup logic is on by default but can be disabled via config.

## 8. References

- agentbrisk.com "Multi-Agent Orchestration in 2026" (2026-05-19) (output validation/termination conditions/human approval checkpoints)
- This repo's `docs/design/ai-dark-factory-orchestration-engine.md` (orchestration engine design)
- 2026-10-08 investigation record (abort residual Agent TODO)
