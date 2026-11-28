# Proposal: Memory System Enhancement — Write-time Selective Storage + Compression + Procedural/Episodic Memory Layering

> **Status**: Pending review (proposal first, then implementation)
> **Related report**: `docs/research/agent-tech-report-2026q3.md` (sections 4.2, 6)
> **Nature**: Proposal design document, currently **not implemented**, for maintainers to review and decide.
> **Date**: 2026-10-08

---

## 1. Background and Motivation

In Q3 2026, the Agent field reached a core consensus: **"context window ≠ memory"**. The context window is RAM (working memory, gone when the session ends), while persistent memory lives in external storage (disk) and must be paged in on demand. Mainstream industry frameworks (Mem0 / Letta / Zep) generally adopt **four memory layers** (short-term/long-term/procedural/episodic) + **write-time selective storage** + **compression**.

Current state of HaijunBot (`src/haijunbot/haijunbot_tools/memory.py` + `haijunbot_memory_organizer/`):

- Already has three memory types: short-term (short_term), project long-term (project_long_term), global long-term (global_long_term).
- Already has semantic retrieval (SmartRetriever, based on jieba + embedding).
- **But missing**: ① explicit layering of procedural/episodic memory; ② write-time selective storage (filtering low-value information at save time); ③ context compression (compress before storing to save tokens).

**Pain point**: The current MemoryTool.save stores "whatever is given", with no value filtering. Over time the memory store fills up with low-value content like "the user said thanks"; at retrieval time noise drowns out signal, wasting tokens and degrading reasoning quality.

## 2. Goals

1. Add two explicit layers, **procedural memory** and **episodic memory**, on top of the existing memory system, complementing the existing short-term/long-term memory.
2. Implement **write-time selective storage**: filter low-value content at save time, keeping only high-signal information that "changes future behavior".
3. Implement **pre-storage compression**: summarize overly long content to control memory store size and retrieval token cost.
4. Maintain backward compatibility: do not break existing save/retrieve/clear calls.

## 3. Technical Design

### 3.1 Memory Layer Extension

Extend the existing `memory_type` enum:

```text
Existing: short_term | project_long_term | global_long_term
New: procedural (procedural: how-to rules, playbooks, lessons from pitfalls)
     episodic (episodic: historical session/task records, for recall queries)
```

**Procedural memory**: stores rules for "what to do when encountering a task of type X". Retrieval triggers on task type match, not semantic similarity. Good for storing: validated solutions, repeated pitfalls, user preference workflows.

**Episodic memory**: stores archived records of historical sessions/tasks. Retrieval triggers on explicit recall queries ("how did we fix that bug last time"). Good for storing: task completion summaries, decision records.

### 3.2 Write-time Selective Storage

Add **value filtering** logic to `MemoryTool.save` (optional, on by default):

- Define "high-signal" heuristic rules:
  - Contains specific facts/preferences/decisions (e.g. "the user prefers metric units") → keep
  - Pure pleasantries/content with no information (e.g. "the user said thanks") → discard
  - Too short (< threshold) or pure duplication → discard
- Provide an `importance` parameter, letting the caller (Agent) explicitly mark importance; fall back to heuristics when unmarked.
- Filtering logic is configurable (rule file or function), not hardcoded.

### 3.3 Pre-storage Compression

For overly long content (over a threshold, e.g. > 2000 tokens), summarize before storing:

- Use a lightweight model or rules to summarize (preserving key facts/decisions/conclusions).
- Compressed content still retains metadata of the original reference (time, source, tags).
- Industry reference: Active Context Compression reports a 22.7% token reduction with accuracy on par (source: whysogeek.com).

### 3.4 Integration with the Existing System

| Existing component                    | Change                                                                           |
| ------------------------------------- | -------------------------------------------------------------------------------- |
| `memory.py` (MemoryTool)              | save adds filtering/compression; enum extended; retrieve supports new types      |
| `smart_retrieval.py` (SmartRetriever) | Support procedural memory matching by task type, episodic memory matching by query |
| `globals.py` (short-term memory)      | Unchanged                                                                        |
| Frontend/tool descriptions            | Update memory tool description                                                   |

## 4. Implementation Steps

1. **Enum and data model extension**: add procedural/episodic types to `memory.py`; add `importance` and `source` fields to the storage structure.
2. **Selective storage filter**: implement heuristic value filtering + the `importance` parameter.
3. **Compressor**: implement summarization compression (can start with rules/a lightweight model, swappable later).
4. **Retrieval enhancement**: add procedural (by task type) and episodic (by query) retrieval branches to SmartRetriever.
5. **Tool description update**: have the memory tool description explain the new types and filtering behavior.
6. **Tests**: add unit tests for save filtering/compression and new-type retrieval.

## 5. Risks and Limitations

- **Misfiltering**: heuristics may wrongly delete valuable information → provide the `importance` explicit mark as a fallback; filtering logic is configurable.
- **Compression distortion**: summarization may lose details → retain original metadata so the raw text can be consulted when needed.
- **Backward compatibility**: existing calls work even without passing importance (falling back to heuristic defaults).
- **Performance**: compression adds save latency → can use async/background compression.

## 6. Validation Approach

- Unit tests: filtering (high/low-value content), compression (overly long content), new-type retrieval (procedural by task type, episodic by query).
- Integration: run a real conversation, observe memory store content quality and retrieval hits.
- Regression: all existing memory-related tests pass.

## 7. Impact Scope

- Main changes: `memory.py`, `smart_retrieval.py`.
- Impact: internal to the memory system; backward compatible; does not break existing Agent behavior (filtering on by default, but can be disabled).

## 8. References

- whysogeek.com "AI Agent Memory: Context Engineering Patterns for 2026" (2026-06-29)
- Mem0 / Letta / Zep official documentation
- Existing memory-related designs in this repo's `docs/design/` (if any)
