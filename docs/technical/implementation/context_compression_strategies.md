# Context Compression Strategies Documentation

## Currently Implemented Strategies

### 1. Summary Compression
- **Implementation**: `Agent._summarize_and_clear_history()`
- **Trigger conditions**:
  - Remaining tokens < 25% of input window (auto-trigger)
  - Conversation turns reach threshold (auto-trigger)
  - LLM outputs `!!!SUMMARY!!!` marker (triggered by LLM)
  - User manually triggers
- **Compression method**: LLM generates conversation summary, preserves key info
- **Preserved content**:
  - Original task goal (`original_user_input`)
  - User pinned content (`pin_content`)
  - Recent memories (`recent_memories`)
  - Task list state
  - Git diff statistics

### 2. Token Threshold Trigger
- **Implementation**: `AgentRunLoop.run()`
- **Threshold**: Remaining tokens < 25% of input window
- **Advantage**: Auto-triggers without intervention

### 3. Conversation Turn Threshold
- **Implementation**: `AgentRunLoop.run()`
- **Config**: `conversation_turn_threshold`
- **Advantage**: Prevents overly long conversations, periodic cleanup

### 4. Git Diff Truncation
- **Implementation**: `AgentRunLoop._check_diff_token_limit()`
- **Limit**: Diff content max 10% of input window
- **Strategy**: Truncate line by line, keep prefix

### 5. Message Truncation
- **Implementation**: `BasePlatform._truncate_message_if_needed()`
- **Strategy**: When message too long, keep prefix, truncate at sentence boundary

### 6. Tool Output Truncation
- **Implementation**: `ToolRegistry._format_tool_output()`
- **Strategy**: Dynamically truncate tool output based on remaining tokens

### 7. Key Information Preservation
- **Implementation**: `Agent._handle_history_with_summary()`
- **Preserved content**:
  - Original task goal (highest priority)
  - User pinned content
  - Recent memories
  - Task list state

### 8. Sliding Window Compression ✅ Implemented
- **Implementation**: `Agent._sliding_window_compression()`
- **Trigger conditions**:
  - Remaining tokens < 25% of input window (auto-trigger, tried before full summary)
  - Message count > 2x window size
- **Config**: `sliding_window_size` env var (default 9 messages: 4 user/tool + 5 assistant; odd number avoids consecutive same-role messages)
- **Compression method**:
  - Preserve system messages (never compressed)
  - Preserve recent user/tool messages (4) and assistant messages (5), total 9; keep intact
  - Compress earlier conversations (LLM summary)
  - Insert summary as user message
- **Advantages**: Keeps recent context intact; lighter than full summary; auto-triggers
- **Use case**: Long-running conversations; try sliding window first, fall back to full summary if insufficient

## Other Possible Strategies

### 9. Importance Scoring Compression ✅ Implemented
- **Implementation**: `Agent._importance_scoring_compression()`, `Agent._score_message_importance()`
- **Trigger conditions**:
  - Remaining tokens < 25% of input window (auto-trigger)
  - Message count > 10
- **Config**: `importance_score_threshold` env var (default 3.0)
- **Scoring dimensions**:
  - Base: user input 5.0, assistant 2.0, system 1.0
  - Keywords: important terms (+0.5), tool calls (+2.0), errors/fixes (+2.0), task completion (+1.5), pinned/important (+3.0)
- **Compression method**:
  - Preserve system messages (never)
  - Keep high-scoring messages (score >= threshold)
  - Compress low-scoring into summary
  - Keep recent 5 low-scoring as context
- **Advantages**: Smart identification of important messages; preserves scattered important info
- **Disadvantages**: Scoring may need tuning per scenario

### 10. Hierarchical Compression
- **Description**: Different strategies for different content types
- **Strategy**: System prompts unchanged; user inputs preserved; tool calls keep call+key results, compress details; LLM responses compress middle, keep decisions/conclusions
- **Advantage**: Targeted, preserves most important info

### 11. Incremental Summarization ✅ Implemented
- **Implementation**: `Agent._incremental_summarization_compression()`
- **Trigger conditions**:
  - Remaining tokens < 25% of input window
  - Message count > 2 chunks
- **Config**: `incremental_summary_chunk_size` env var (default 20 turns)
- **Compression method**:
  - Split history into chunks (N turns each)
  - Summarize earlier chunks
  - Keep last chunk intact
  - System messages never compressed
- **Advantages**: Avoids compressing everything at once; preserves recent context; better summary quality per chunk
- **Disadvantages**: May produce multiple summary messages

### 12. Semantic Clustering Compression
- **Description**: Cluster similar messages, keep representative per cluster
- **Idea**: Cluster by similarity, select representative from each cluster
- **Advantage**: Removes redundancy while preserving diversity

### 13. Key Event Extraction ✅ Implemented
- **Implementation**: `Agent._key_event_extraction_compression()`, `Agent._is_key_event()`
- **Trigger conditions**:
  - Remaining tokens < 25% of input window
  - Message count > 10
- **Key event types**: Task start/complete markers, important decisions (long text with decision keywords), errors/fixes, key tool results, pinned/important content, user inputs
- **Compression method**:
  - Preserve system messages
  - Keep all key event messages in order
  - Compress non-key events into summary
  - Keep recent 5 non-key messages as context
- **Advantages**: Preserves decisions, errors/fixes, tool results
- **Disadvantages**: Rules may need tuning

### 14. Time Decay Compression
- **Description**: Compression strength based on message age (recent less compressed, older more compressed)
- **Idea**: Age = current_time - msg.timestamp; adjust ratio by age

### 15. Topic Segmentation Compression
- **Description**: Split by topic; compress completed topics, keep current topic
- **Idea**: Segment into topics, summarize completed, keep current

### 16. Q&A Pair Compression
- **Description**: Identify Q&A pairs, keep question+final answer, compress middle
- **Idea**: Extract pairs, compress each pair

### 17. Tool Call Chain Compression
- **Description**: Compress tool call intermediate steps, keep start and end of chain
- **Idea**: Extract chains, compress each chain

### 18. Vector Retrieval Compression
- **Description**: Keep only history messages most relevant to current context (semantic similarity)
- **Idea**: Embed history + current; retrieve top-k

### 19. Structured Information Extraction
- **Description**: Extract structured info (task lists, decisions, state) and compress unstructured
- **Idea**: Split structured vs unstructured, compress unstructured

### 20. Adaptive Compression ✅ Implemented
- **Implementation**: `Agent._adaptive_compression()`, `Agent._detect_task_type()`
- **Trigger conditions**:
  - Remaining tokens < 25% of input window (primary)
  - Auto-detect task type and select best strategy
- **Task type detection**:
  - Code: CodeAgent or code tool calls (edit/read/execute) or code keywords
  - Analysis: analysis tool calls (search/rg/fd/grep/retrieve) or analysis keywords
  - Conversation: short Q&A style
  - Mixed: multiple tool types
  - Unknown: unrecognized
- **Strategy selection (sliding window prioritized)**:
  - Code: sliding window → key event extraction → incremental summarization
  - Analysis: sliding window → importance scoring → incremental summarization
  - Conversation: sliding window → importance scoring → incremental summarization
  - Mixed: sliding window → incremental summarization → importance scoring
  - Unknown: sliding window → importance scoring → incremental summarization
- **Advantages**: Auto-selects optimal strategy per task type; preserves task-relevant info; auto-fallback

## Recommended Strategy Combinations

### Combination 1: Basic
- Summary compression (primary)
- Token threshold trigger (auto)
- Key info preservation (safety)

### Combination 2: Advanced ✅ Implemented
- Summary compression
- Importance scoring compression ✅
- Key event extraction ✅
- Incremental summarization ✅
- Sliding window compression ✅

### Combination 3: Intelligent ✅ Implemented
- Adaptive compression ✅
- Incremental summarization ✅
- Key event extraction ✅
- Key info preservation ✅

## Implementation Priority

### High Priority (Done)
1. ✅ Summary compression
2. ✅ Token threshold trigger
3. ✅ Key info preservation
4. ✅ Sliding window compression

### Medium Priority (Done)
5. ✅ Importance scoring compression
6. ✅ Incremental summarization
7. ✅ Key event extraction

### Low Priority (Future)
8. Semantic clustering compression
9. Vector retrieval compression
10. ✅ Adaptive compression

## Notes

1. **Compression quality**: Compressed content must maintain semantic integrity
2. **Key info**: Must not lose original task goal, key decisions
3. **Performance**: Compression shouldn't consume excessive tokens
4. **Recoverability**: Compressed content should be recoverable via session files
5. **UX**: Compression should be transparent to user