# HaijunBot Four Major Systems "Reduce Model Input Volume" Optimization Design Plan

> Target scale: thousands of methodologies / tens of thousands of memories / hundreds of tools / thousands of rules
> Current scale: methodologies 67 / memories 1919 / tools 36 / rules pruned to 47
> This document is a **design**, not an implementation. Core goal: **reduce the input volume (prompt/token) sent to the model on each call**.
> Optimizing in-memory load volume is deprioritized (non-blocking, not a priority), and handled only when incidentally convenient.

---

## 0. Core Conclusions (focusing on model input volume)

Among the four systems, only three paths truly **inflate model input volume**; the other paths already have token/count defenses:

| System     | Input Path to the Model            | Current State                                                                                                                                                                                                                                            |  Inflated?  |
| ---------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------: |
| **Methodology** | Selection stage: **full titles/candidates** stuffed into the LLM | eval goes through decide_choice, constructing one noul question per candidate (decision.py:136); normal concatenates all titles into the prompt (methodology.py:262-264)                                                                                  | 🔴 **Inflated** |
| **Rules**  | Selection stage: **full candidates + descriptions** stuffed into the LLM | `select_rule_by_task` full candidates + each candidate's full description concatenated into the prompt (rules_manager.py:1162-1168)                                                                                                                       | 🔴 **Inflated** |
| **Tools**  | Full tool schemas passed to the model | Native mode `build_openai_tools`/`build_juglow_tools` passes full schemas of all tools to the API tools (native_tools.py:372-404); non-native mode `prompt()` injects full JSON into the system prompt (registry.py:240-274)                             | 🔴 **Inflated** |
| **Memory** | memory tool retrieve returns Markdown | Normal retrieval already has a token limit (memory.py:380-419) + a 50-item cap; **smart_search has no token limit** (memory.py:477-543)                                                                                                                   |   🟡 Partial   |

**Paths already defended, no optimization needed**:

- Methodology **final injection**: has a token limit (`methodology_token_limit = max_input*0.8`, methodology.py:418-435)
- Rules **final loading**: has a `MAX_AUTO_RULES = 3` cap (rules_manager.py:1128)
- Memory **normal retrieval injection**: has a token limit + a 50-item cap (memory.py:380-419)

**Optimization priority** (by the benefit of reducing input volume):

- **P0**: Methodology selection-stage pre-filtering (B1)
- **P0**: Rule selection-stage pre-filtering (C2)
- **P1**: Tool schema summarization/grouping (D1/D2)
- **P2**: Add a token limit to memory smart_search (A3)

---

## 1. Methodology System (P0, core inflation point)

### 1.1 Problem Confirmation (code facts)

Files: `src/haijunbot/haijunbot_utils/methodology.py` + `src/haijunbot/haijunbot_utils/decision.py`

`load_methodology` (347) is called every session (when use_methodology is enabled):

1. `_load_all_methodologies` (109-196) loads all json fully
2. `methodology_titles = [title for title, _ in methodologies]` (383) — **all titles**
3. Selection stage:
   - **eval mode**: `_select_methodologies_with_eval_model` (199) → `decide_choice` (decision.py:136) constructs one noul question for **each candidate**, sending **all candidates' questions** to the evaluation model in a single request (decision.py:155-166). Thousands of methodologies = thousands of questions = a huge input volume
   - **normal mode**: `_select_methodologies_with_normal_model` (241) concatenates **all titles** into the prompt (262-264)

### 1.2 Optimization Plan

#### Plan B1 (P0, recommended): Selection-stage pre-filtering Top-N

- **Before** calling `_select_methodologies_with_eval_model` / `_select_methodologies_with_normal_model`, coarsely filter `methodology_titles` by keyword, keeping only the Top-N (e.g. 30-50) candidates
- Coarse filtering method: extract user-input keywords with jieba tokenization, score by substring/keyword matching against titles, and take the Top-N
- **Benefit**: with thousands of methodologies, the LLM candidates drop from full to Top-N, reducing input volume by an order of magnitude
- **Risk**: a correct methodology may be missed — **a fallback must be retained**: fall back to full when the pre-filtered result is empty
- Implementation location: in `load_methodology` (347), insert the pre-filter after obtaining `methodology_titles` at line 383 and before selection at line 389

#### Plan B2 (P2, optional): Load cache

- `_load_all_methodologies` does a full glob + json.load every time; add an mtime cache (an in-memory load optimization, low priority)

---

## 2. Rule System (P0, core inflation point)

### 2.1 Problem Confirmation (code facts)

File: `src/haijunbot/haijunbot_agent/rules_manager.py`

`select_rule_by_task` (1117):

1. `get_all_available_rule_names` (684-759) does a full os.walk traversal (pruning only track.md directories)
2. For **each candidate**, `_extract_rule_description` reads the file to extract the description (1147-1159, IO)
3. `top_rules = all_rules_list` (1162) — **all candidates**
4. Constructs a numbered list and concatenates **all candidates + descriptions into the prompt** (1164-1168) sent to the LLM

With thousands of rules: all candidates + descriptions stuffed into the LLM = a huge input volume.

### 2.2 Optimization Plan

#### Plan C2 (P0, recommended): Selection-stage pre-filtering Top-N

- Before constructing the numbered list (1164), coarsely filter candidates by keyword, keeping only the Top-N (e.g. 30-50)
- Coarse filtering method: extract user-input keywords with jieba tokenization, and score by keyword matching against rule name/description
- **Benefit**: with thousands of rules, the LLM candidates drop from full to Top-N, reducing input volume by an order of magnitude
- **Risk**: a correct rule may be missed — **a fallback must be retained**: fall back to full when the pre-filtered result is empty
- Implementation location: in `select_rule_by_task` (1117), change `top_rules = all_rules_list` at line 1162 to the pre-filtered result

#### Plan C1 (P2, optional): Rule index cache

- Build a rule index (name → path → description), cache it after the first build, and invalidate it by mtime
- Avoids os.walk + reading all files on every `select_rule_by_task` (an in-memory/IO optimization, low priority)

---

## 3. Tool System (P1, core inflation point)

### 3.1 Problem Confirmation (code facts)

Files: `src/haijunbot/haijunbot_platform/native_tools.py` + `src/haijunbot/haijunbot_tools/registry.py`

There are two paths for injecting tools into the model, and **native mode is used by default** (`enable_native_tool_calls` defaults to True, config.py:1261):

1. **Native mode**: `_native_tools()` (**init**.py:1137) → `build_openai_tools`/`build_juglow_tools` (native_tools.py:372-404) iterate over `registry.tools.values()` for **all tools**, passing each tool's name/description/**full parameters schema** to the API's tools parameter
2. **Non-native mode**: `build_system_prompt` (prompt_manager.py:49) → `get_tool_usage_prompt` → `build_action_prompt` (prompt_builder.py:19-76) → `ToolRegistry.prompt()` (registry.py:240-274) iterates over all tools, injecting the full JSON into the system prompt

The current prompt for 21 tools is about 13.5k tokens (measured). With hundreds of tools, this scales proportionally to 100k+ tokens, which is very significant.

### 3.2 Optimization Plan

#### Plan D1 (P1, recommended): Tool schema summarization/reduction

- Reduce the tool's `parameters` schema: keep only `required` fields + key descriptions, omitting verbose `enum`/`default`/`description` details
- Truncate overly long descriptions
- **Benefit**: with hundreds of tools, each tool's schema shrinks significantly, greatly reducing the total input volume
- Implementation location: `build_openai_tools`/`build_juglow_tools` (native_tools.py:372-404) and `ToolRegistry.prompt()` (registry.py:240-274) share the same reduction function

#### Plan D2 (P2, optional, larger change): Tool grouping and on-demand injection

- Group tools by category; inject only the commonly used core tools, supplementing the rest on demand
- **Risk**: a large change; must ensure the model can discover un-injected tools (in native mode the tools parameter is static, so dynamic injection requires changing run_loop)

#### Plan D3 (P2, optional): Prompt cache

- The tool prompt is built every session; it can be cached if the tool set is unchanged (an in-memory optimization, low priority)

---

## 4. Memory System (P2, partially needs optimization)

### 4.1 Problem Confirmation (code facts)

Files: `src/haijunbot/haijunbot_tools/memory.py` + `src/haijunbot/haijunbot_memory_organizer/smart_retrieval.py`

Memory is actively invoked by the model through the `memory` tool (action=retrieve), returning Markdown injected into the model:

- **Normal retrieval** (`_execute_retrieve`, memory.py:348): **already has a token limit** (380-419, 2/3 of remaining tokens or 2/3 of the input window) + a 50-item cap. **No optimization needed**
- **smart_search** (`_execute_smart_search`, memory.py:477): **no token limit**, directly returning the formatted top-N of `semantic_search` (default 10 items) for injection. Although the item count is small, **each content may be very long**, with no token cap

### 4.2 Optimization Plan

#### Plan A3 (P2, recommended): Add a token limit to smart_search

- In `_execute_smart_search` (memory.py:477), before formatting the output, reuse the token-limit logic of normal retrieval (380-419) to filter the returned memories by token budget
- **Benefit**: prevents a single overly long memory from blowing up the context
- Implementation location: in `_execute_smart_search` (memory.py:477), add token filtering before formatting at line 527

#### Plans A1/A2 (P3, optional, in-memory load optimization, low priority)

- Remove the useless full load in `_load_all_memories` (smart_retrieval.py:168-169, the corpus parameter is actually unused)
- Tag inverted index (smart_retrieval.py:464-482)
- **These are in-memory/IO optimizations, deprioritized per the user's instruction**

---

## 5. Implementation Suggestions

### 5.1 Phased Implementation (ordered by the benefit of reducing model input volume)

| Phase              | Content                         | Change Size | Risk              |
| ------------------ | ------------------------------- | ------ | ----------------- |
| **Phase 1**        | Methodology B1 pre-filtering    | Medium | Medium (needs fallback) |
| **Phase 2**        | Rule C2 pre-filtering           | Medium | Medium (needs fallback) |
| **Phase 3**        | Tool D1 schema reduction        | Medium | Low-Medium        |
| **Phase 4**        | Memory A3 smart_search token limit | Small  | Low               |
| **Phase 5** (optional) | In-memory/IO optimization (A1/A2/C1/B2/D3) | Medium | Low        |

### 5.2 General Principles

- All pre-filtering plans **must retain a fallback** (fall back to full when the pre-filter is empty) to avoid missing selections
- The pre-filtering threshold (Top-N) is configurable, defaulting to 30-50
- Each phase is committed independently and can be rolled back separately
- Each phase is validated with benchmark tests using the current data volume + a simulated target scale

### 5.3 Verification Method

- Phases 1/2: compare the results selected by `load_methodology`/`select_rule_by_task` before and after pre-filtering (pre-filtering should not miss selections; manual spot-checks required); compare the input volume sent to the LLM (token count)
- Phase 3: compare the tool-call success rate (the model should still be able to call tools correctly); compare the input volume of the tools section
- Phase 4: compare the smart_search returned results and the input volume
