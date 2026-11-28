# Introducing Haijun Code's Context Management Mechanism into HaijunBot -- Design Proposal

> Status: **design proposal (pending review)**
> Date: 2026-09-08
> Scope: `src/haijunbot/haijunbot_agent/`, `src/haijunbot/haijunbot_platform/`, `src/haijunbot/haijunbot_utils/config.py`
> Related: this proposal is based on research into Haijun Code's context mechanism (see "Research Basis" at the end)

---

## 1. Background and Problem

### 1.1 HaijunBot current state (code facts)

HaijunBot's context/token management already has the following capabilities:

| Capability                | Implementation location                          | Description                                                  |
| ------------------------- | ------------------------------------------------ | ------------------------------------------------------------ |
| token counting            | `base.py:766-797` `get_used_token_count`         | iterates message content + tool_calls fields, tiktoken estimate |
| remaining space           | `base.py:786-795` `get_remaining_token_count`    | limit - used                                           |
| background pre-compression | `__init__.py:2330` `_start_background_pre_compression` | starts at the 75% threshold; a background thread generates a summary |
| summary takes effect immediately | `run_loop.py:335-346`               | applied immediately after the background completes (implemented) |
| trigger compression       | `run_loop.py:348` `_adaptive_compression`        | 80% threshold; uses the pre-compression summary or sliding window |
| sliding window            | `__init__.py:2173` `_sliding_window_compression` | keeps the most recent N messages, compresses earlier conversation |
| tool result backfill      | `base.py:118-124` `append_native_tool_result`    | role=tool messages store full results in content           |

### 1.2 Gaps vs. Haijun Code (research conclusion)

Haijun Code's context management is a **five-layer cascade** system, of which three layers are missing or insufficient in HaijunBot:

| Haijun Code layer         | Role                                                                  | HaijunBot current state            |
| ------------------------- | --------------------------------------------------------------------- | ------------------------------- |
| **Layer 0 persist to disk & truncate** | when a tool result > ~50K chars, write the full payload to a file and keep only a ~2KB preview + file path in context | ❌ **Missing**: tool results go into context in full |
| **Microcompact**          | no model call; directly strips old tool results; surgical, frequent, cheap | ❌ **Missing**: no such layer   |
| **Session memory compact** | rebuilds a condensed history from pre-extracted notes, no summary call | ⚠️ Partial: background pre-compression is similar |
| **Full compact**          | fork agent summarizes the whole conversation (most expensive)         | ⚠️ Partial: sliding-window / summary compression is similar |
| Auto-compression threshold | ≈ context_window - max_output_tokens - buffer                         | ✅ exists (80% threshold)       |

**Core gap**: HaijunBot lacks the "truncate large tool results to disk" and "strip old tool results" layers, which causes:

1. A single large tool output (e.g. `execute_script` reading a big file, `read_code` over a large range) consumes a large amount of context at once;
2. Stale tool results that are no longer useful in the history (e.g. early `ls`/`grep` output) linger for a long time and are only cleaned up when a full compression is triggered.

---

## 2. Design Goals and Principles

### 2.1 Goals

1. **Truncate large tool results to disk**: tool results over the threshold are written to a temp file, the context keeps only a preview + path, and the model can read them on demand.
2. **Strip old tool results (micro-compression)**: under token pressure, discard the oldest tool results without a model call to reduce context usage.
3. **Coexist with the existing compression system**: the new mechanism acts as a **pre-supplement layer** to the existing 75%/80% compression, without breaking existing background pre-compression / sliding window logic.
4. **Configurable and revertible**: all thresholds go through config; off by default or conservatively on, to avoid behavioral surprises.

### 2.2 Principles

- **Minimal invasiveness**: changes are concentrated at the tool-result backfill entry and the compression checkpoints; no refactoring of the existing compression main flow.
- **Pairing safety**: any trimming must guarantee that assistant tool_calls and role=tool callbacks remain paired (otherwise OpenAI/Juglow return 400); reuse `ensure_tool_pairing`.
- **Observability**: disk-write/strip actions have logging and metrics for validation and tuning.

---

## 3. Layered Mechanism Design

Map Haijun Code's mechanism to HaijunBot's **three supplemental layers**, stacked on top of the existing compression system. Overall trigger order (before each model call, inside `run_loop.check_and_compress_context`):

```text
At tool-result backfill (append_native_tool_result)
   └─ [new] L0 truncate large result to disk (write file, keep preview)
Before each model call (check_and_compress_context)
   ├─ [new] L1 micro-compression: strip oldest tool results (no model call)
   ├─ [existing] 75% background pre-compression
   ├─ [existing] apply once background completes
   └─ [existing] 80% triggers _adaptive_compression
```

### 3.1 L0: Truncate large tool results to disk (new)

**Goal**: when a single tool result is too large, do not put the full text into context; instead use "preview + file path", and the model reads it on demand with `read_code` / `execute_script` when needed.

**Trigger point**: `base.py:118-124` `append_native_tool_result` (the only entry for native tool result backfill).

**Rules**:

- Threshold `tool_result_disk_threshold` (default e.g. 20000 chars, configurable).
- Result length ≤ threshold: goes into context as-is (current behavior unchanged).
- Result length > threshold: the full content is written to a temp file (`haijunbot_data_dir/tool_results/`), and the context content is replaced with a structured preview:

```text
[Tool {name} result too large, persisted to disk]
Full result file: {abs_path} ({N} chars)
Preview (first {preview_len} chars):
{preview}
If you need the full content, read the file with read_code.
```

- Preview length `tool_result_preview_len` (default e.g. 2000 chars).
- Persisted files are cleaned up per session (deleted at session end / compression, to avoid disk accumulation).

**Key points**:

- Only change `append_native_tool_result` in one place; tool results for both the text protocol and the native protocol pass through this backfill (need to confirm whether the text protocol also goes through this method; see §6 pending items).
- After persist-to-disk, if the model needs the full content it proactively issues a `read_code` to read it -- this is Haijun Code's established behavior pattern, and the model is already used to it.

### 3.2 L1: Strip old tool results (micro-compression, new)

**Goal**: with no model call, surgically discard the oldest, now-useless tool results from the history to reduce context usage. Corresponds to Haijun Code's Microcompact.

**Trigger point**: inside `run_loop.check_and_compress_context`, **before** the existing 75% pre-compression.

**Rules**:

- Threshold `microcompact_trigger_ratio` (default e.g. remaining ≤ 35%, i.e. starts at 65% used, earlier than the 75% pre-compression).
- Starting from the **oldest** in history, strip "paired role=tool result messages" one by one until:
  - the released tokens reach `microcompact_target_ratio` (default e.g. release up to 10% of the limit), or
  - there are no more strippable old tool results.
- **Pairing safety**: when stripping role=tool, the corresponding assistant tool_calls message must also be stripped (otherwise 400). Reuse the `ensure_tool_pairing` semantics.
- **Protection**: do not strip the most recent K tool results (default e.g. the most recent 3 rounds), preserving recent context; system messages, the latest user message, and assistant plain-text messages are never stripped.

**Key points**:

- No model call; purely a message-list operation; extremely cheap; can run frequently.
- After stripping, call `set_messages` to rebuild the history (consistent with existing compression).
- If 75%/80% still triggers after stripping, continue through the existing background pre-compression / sliding window -- L1 is just an upstream load reducer.

### 3.3 Handoff to existing compression

- After L1 stripping, recompute the remaining tokens; if still ≤25%, start background pre-compression; if ≤20%, trigger `_adaptive_compression` (logic unchanged).
- L0 persistence completes at backfill, naturally reducing the input size for all downstream layers.
- With the three layers stacked, large tool results no longer blow up the context in one shot, old tool results are cleaned up progressively, and the overall compression trigger frequency drops.

---

## 4. Configuration Item Design (new, `config.py`)

| Config key                   | Default value       | Description                                        |
| ---------------------------- | ------------------- | --------------------------------------------------- |
| `tool_result_disk_threshold` | 20000               | persist-and-truncate when a tool result exceeds this char count (0=disable L0) |
| `tool_result_preview_len`    | 2000                | preview chars kept in context after persisting to disk |
| `tool_result_disk_dir`       | `<data>/tool_results` | persisted file directory                          |
| `microcompact_trigger_ratio` | 0.35                | triggers L1 micro-compression when remaining token ratio ≤ this value (0=disable) |
| `microcompact_release_ratio` | 0.10                | max token ratio L1 releases in a single run         |
| `microcompact_keep_recent`   | 3                   | do not strip tool results from the most recent N rounds |

> The default values are all conservative estimates; use measured values at implementation time; all configurable, on by default but with loose thresholds to avoid behavioral surprises.

---

## 5. Implementation Steps (landing plan)

Divided into 3 phases by dependency order; each phase is independently verifiable and revertible.

### Phase A: L0 truncate large tool results to disk

1. Add `tool_result_disk_threshold` / `tool_result_preview_len` / `tool_result_disk_dir` read functions to `config.py`.
2. Add a utility function `maybe_truncate_tool_result(name, content) -> str` (in `native_tools.py` or a new module): if over threshold, write to disk and return the preview text.
3. Call it inside `base.py:118-124` `append_native_tool_result`, replacing the backfilled content.
4. Clean up the `tool_results/` directory files at session end / compression.
5. **Verification**: mock an over-threshold tool result; confirm the role=tool content becomes a preview + path, the file is persisted, and token statistics drop significantly; existing tests such as `test_native_tools` do not regress.

### Phase B: L1 strip old tool results (micro-compression)

1. Add `microcompact_trigger_ratio` / `microcompact_release_ratio` / `microcompact_keep_recent` read functions to `config.py`.
2. Add a method `_microcompact_old_tool_results() -> bool` (in `__init__.py`, alongside the existing compression methods): strip paired tool results + corresponding tool_calls from the oldest, until the release target is reached or nothing more can be stripped.
3. Insert the call inside `run_loop.check_and_compress_context`, **before** the 75% pre-compression.
4. **Verification**: build a history containing many old tool results; confirm token usage drops after stripping, pairing is intact (`ensure_tool_pairing` passes), and the latest K rounds are preserved; existing compression tests do not regress.

### Phase C: integration test and tuning

1. Real long-conversation testing: confirm L0/L1 work together with the 75% background pre-compression and 80% trigger compression, with no conflicts and no duplicate compression.
2. Adjust the default thresholds based on measurements (persist threshold, strip ratio, protected rounds).
3. Add unit tests covering L0/L1 boundaries (threshold edge cases, empty history, all-tool history, broken pairing, etc.).

---

## 6. Pending Items and Risks

### 6.1 Pending items

- **Text-protocol tool result backfill path**: the native protocol goes through `append_native_tool_result` (base.py:118), but the text protocol (`_handle_tool_calls`, run_loop.py:522) has a different backfill path. Need to verify whether text-protocol tool results also produce role=tool messages and whether they can reuse L0 persistence; otherwise the text-protocol path needs its own integration.
- **Persisted file lifecycle**: the exact hook point for session-end / compression cleanup needs to be located at implementation time (`delete_chat` / `reset` / compression methods).
- **Model compliance with "persisted preview + path"**: needs real testing to confirm the model proactively issues `read_code` to read the persisted file rather than ignoring the preview.

### 6.2 Risks and mitigations

| Risk                                           | Impact          | Mitigation                                                       |
| ---------------------------------------------- | --------------- | ---------------------------------------------------------------- |
| Model does not proactively read the file after persistence, losing critical info | degraded task quality | preview keeps enough context; prompt guidance; conservative threshold (only very large results are persisted) |
| Stripping old tool results damages a still-referenced result | model confusion | protect the most recent K rounds; only strip the oldest; configurable off |
| Broken pairing causes API 400                    | request failure | reuse `ensure_tool_pairing`; strip in pairs                      |
| Disk accumulation of persisted files           | disk usage      | per-session cleanup; directory cap                               |
| Duplicate triggers with existing compression   | behavioral anomalies | recompute remaining tokens after L1; keep the original threshold checks |
| **L1 stripping breaks server-side prefix cache hits** | cost / latency increase | see §6.3; strip as late as possible, lower frequency; prioritize L0; measure hit rate in Phase C |

### 6.3 Impact on server-side prompt caching (review addendum)

> This section is analysis added during proposal review, answering "does L1 stripping old tool results affect model server-side cache hits".

**Conclusion**: L1 stripping **will** break server-side prefix cache hits, but the impact is local and predictable; on the OpenAI-compatible backends HaijunBot connects to, its "cost-effectiveness" is lower than in Haijun Code's native environment and must be weighed at implementation time.

#### 6.3.1 Server-side caching mechanism (facts)

HaijunBot actually connects to OpenAI-compatible APIs (vLLM / DeepSeek / ModelScope and other third-party hosts), whose prompt caching is **pure automatic prefix matching** with no explicit breakpoints:

- **vLLM Automatic Prefix Caching**: hashes and caches KV by token block (default 16 tokens); each new request matches token-by-token from the first block, hitting the "longest common prefix"; once the prefix diverges at any point, everything after that point is invalidated.
- **DeepSeek context hard-disk cache**: on by default; full matching by "cache prefix unit" (request end position persisted + common prefix detection + persistence at fixed token intervals); `usage` returns `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` for observable hit tracking.

**Ideal state (no compression)**: every HaijunBot round appends only new messages (`self.messages.append`), system is first and stable, so the N+1th-round request is a **prefix superset** of the Nth round -> the server side hits almost completely, needing to prefill only the new messages. This is the ideal working mode for prefix caching.

#### 6.3.2 How L1 stripping breaks hits (reasoning)

L1 strips `[assistant(tool_calls), role=tool]` pairs starting from the **oldest** in history. Given history `[S, U1, A1(tc), T1, A2, U2, A3(tc), T3, A4, U3, ...]`, stripping the oldest `[A1(tc), T1]` yields `[S, U1, A2, U2, A3(tc), T3, A4, U3, ...]`. The server-side cache prefix is `[S, U1, A1, T1, A2, ...]`; the new request diverges right after U1 -> **the common prefix only reaches `[S, U1]`, and all history KV after the strip point is invalidated**, requiring a full re-prefill. The further forward and the more the stripping happens, the larger the invalidation scope.

#### 6.3.3 Fundamental difference from the Haijun Code environment (why it cannot be copied directly)

Haijun Code connects to Juglow, whose caching uses **explicit `cache_control` breakpoints + a 20-block rollback window**, allowing multi-breakpoint layering to "pin" high-value static prefixes (system / tools / HAIJUN.md). microcompact stripping happens in the dynamic conversation region **after** the breakpoints and **never touches the static breakpoint cache** -- sacrificing only the conversation layer that changes fastest and has the lowest hit value, while preserving the token bulk (the static prefix). Haijun Code treats cache hit rate as a SEV-level monitoring metric; its stripping is the rational trade of "sacrificing low-value cache, keeping high-value cache".

The backends HaijunBot connects to have **no explicit breakpoints**; a hit equals the longest common prefix of the whole request, and no layer can be protected hierarchically. L1 stripping is a "one-size-fits-all" cut that hurts all history after the strip point. So the same strip action "hurts only the low-value layer" on Haijun Code but "hurts the entire history after the strip point" on HaijunBot -- **significantly lower cost-effectiveness**.

#### 6.3.4 Implication for the proposal (opinion)

1. **L1 stripping is less cost-effective in HaijunBot's environment than in Haijun Code's**; a demerit in proposal review, but not a veto.
2. **L1 is not unusable**: it saves client tokens + prefill at the cost of breaking some cache. Whether it pays off depends on strip frequency, strip point position, and backend cache billing (DeepSeek hits cost about 0.1x).
3. **If L1 is kept**, stripping should happen as late as possible in the conversation to shrink the invalidation scope, or raise the trigger threshold and lower frequency to avoid long-term low cache hit from small per-round strips.
4. **L0 persistence is cache-friendly** (truncating at backfill does not change already-sent history) and should take priority over L1.
5. **Phase C needs real measurement**: compare the `prompt_cache_hit_tokens` hit rate and cost with "L1 on / L1 off" as the decision basis for whether to keep L1.

---

## 7. Research Basis

This proposal is based on research into Haijun Code's context mechanism (official docs + teardown analysis):

- **Haijun Code official context-window documentation**: file reads, tool output, HAIJUN.md, memory, tracks, MCP tool names all enter the context; `/compact` replaces the conversation with a structured summary; auto-compression triggers near the limit.
- **Haijun Code's five-layer cascade compression** (startdebugging.net teardown):
  - Layer 0 (persist to disk): when tool results exceed ~50K chars, the full payload is written to a file and context keeps only a ~2KB preview + path; the combined cap for all tool_result blocks in a single message is ~200K chars.
  - Microcompact: no model call; directly strips old tool results; cheap, surgical, and runs frequently.
  - Session memory compact: rebuilds a condensed history from pre-extracted notes, no summary call.
  - Full compact: fork agent summarizes the entire conversation (most expensive).
  - Auto-compression threshold ≈ context_window - max_output_tokens - buffer (firing at ~167K in a 200K window).

> Note: the specific mechanisms of OpenAI Codex / Cursor / Aider could not be obtained because search tools timed out repeatedly; this proposal benchmarks against Haijun Code as the reference baseline.