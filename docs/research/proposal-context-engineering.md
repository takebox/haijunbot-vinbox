# Proposal: Systematic Context Engineering — Retrieval Budget and Layered Injection

> **Status**: Pending review (proposal first, then implementation)
> **Related report**: `docs/research/agent-tech-report-2026q3.md` (sections 4.2, 6)
> **Nature**: Proposal design document, currently **not implemented**, for maintainers to review and decide.
> **Date**: 2026-10-08

---

## 1. Background and Motivation

In Q3 2026, the Agent field established "context engineering" as an independent discipline: **deciding which tokens flow into the model and when**. Core principle: **retrieval precision matters more than retrieval quantity**; more context ≠ better context (the model loses focus in noise, and cost rises). Industry consensus: 65% of enterprise Agent failures stem from context drift rather than model capability (source: agentmarketcap.ai, data pending verification).

Current state of HaijunBot:

- Already has token budget management (`calculate_token_limit` / `get_max_input_token_count` in `haijunbot_utils/config.py`).
- The memory system has semantic retrieval (SmartRetriever), but **there is no explicit budget allocation or layering strategy when injecting retrieval results into context**.
- Agent context construction (system prompt + memory + tool descriptions + conversation history) lacks a systematic "layered injection" design.

**Pain point**: Memory retrieval results, tool descriptions, rules, and conversation history all compete for the limited context window, but there is no unified budget allocation mechanism, making it easy for "too many retrieval results crowding out conversation space" or "key memories being truncated" problems to occur.

## 2. Goals

1. Establish a **context budget model**: allocate explicit token budgets to each component of the context window (system prompt, memory retrieval, tool descriptions, rules, conversation history, current task).
2. Implement a **layered injection strategy**: inject in layers by priority/relevance, prioritizing high-signal content, and downgrade/truncate rather than discarding everything when over budget.
3. Establish a **retrieval budget**: set a token cap for each memory retrieval, and truncate retrieval results to fit the budget after sorting by relevance.
4. Maintain backward compatibility: do not break the existing context construction logic; enhance incrementally.

## 3. Technical Design

### 3.1 Context Budget Model

Define the budget allocation for the context window (configurable):

```text
Total budget = Model max_input_tokens × utilization (e.g. 0.9, leaving headroom)
  ├─ System prompt (fixed, e.g. 20%)
  ├─ Memory retrieval (dynamic, e.g. 20%, truncated by relevance)
  ├─ Tool descriptions (dynamic, varies with enabled tools, e.g. 15%)
  ├─ Rules/specs (dynamic, e.g. 10%)
  ├─ Conversation history (dynamic, e.g. 25%, compressible)
  └─ Current task/user input (fixed reservation, e.g. 10%)
```

### 3.2 Layered Injection Strategy

Inject in layers by "priority": high-priority content is kept intact, low-priority content can be downgraded:

| Layer | Content                      | Priority | Over-budget handling    |
| ----- | ---------------------------- | -------- | ----------------------- |
| L0    | Current task/user input      | Highest  | No truncation           |
| L1    | System prompt core           | High     | No truncation           |
| L2    | Memory retrieval (high rel)  | High     | Truncate to budget      |
| L3    | Tool descriptions/rules      | Medium   | Trim by enabled tools   |
| L4    | Conversation history         | Low      | Compress/sliding window |

### 3.3 Retrieval Budget

Add budget control before SmartRetriever retrieval results are injected:

- Set a token cap for each retrieval injection (e.g. 3000 tokens).
- Sort retrieval results by relevance score, and truncate once the cumulative token count exceeds the budget.
- Provide "layered summarization": when over budget, summarize low-relevance results instead of discarding them.

### 3.4 Integration with the Existing System

| Existing component                                   | Change                                               |
| ---------------------------------------------------- | ---------------------------------------------------- |
| `haijunbot_utils/config.py`                             | Add context budget config items                      |
| Agent context construction (system prompt assembly)  | Introduce layered injection logic                    |
| `smart_retrieval.py`                                 | Budget truncation before injecting retrieval results |
| Tool description management                          | Trim tool descriptions by budget                     |

## 4. Implementation Steps

1. **Config extension**: add context budget and layer ratio config to `config.py`.
2. **Budget calculator**: implement utility functions that compute available tokens per layer.
3. **Injector**: wire layered injection into Agent context construction, replacing the existing "dump everything" logic.
4. **Retrieval budget**: add budget truncation and layered summarization to SmartRetriever.
5. **Tests**: add unit tests for budget allocation, layered injection, and retrieval truncation.

## 5. Risks and Limitations

- **Behavior changes**: changes to context construction logic may affect existing Agent behavior → need thorough regression testing; keep default config as close to the status quo as possible.
- **Config complexity**: too many budget ratio settings may be hard to maintain → provide sensible defaults; make advanced config optional.
- **Harmful truncation**: truncation may lose key memories → fall back to layered summarization.

## 6. Validation Approach

- Unit tests: budget calculation, layered injection, retrieval truncation, layered summarization.
- Integration: run typical tasks, compare context composition and output quality.
- Regression: existing Agent behavior tests all pass.

## 7. Impact Scope

- Main changes: `config.py`, Agent context construction, `smart_retrieval.py`.
- Impact: core path of Agent context construction; regression must be handled carefully.

## 8. References

- whysogeek.com "AI Agent Memory: Context Engineering Patterns for 2026"
- zylos.ai "Context Engineering for AI Agents" (2026-06-26)
- agentmarketcap.ai "Agent Context Engineering 2026"
