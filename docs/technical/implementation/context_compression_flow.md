# Context Compression Flow Documentation

## Overall Flow Overview

The current context compression system adopts a **multi-level progressive compression strategy** that automatically triggers when tokens are insufficient, ensuring long-running sessions don't get interrupted due to context overflow.

## Trigger Conditions

### 1. Token Threshold Trigger (Primary)
- **Threshold**: Remaining tokens < 25% of input window
- **Trigger timing**: Before each model call
- **Location**: `AgentRunLoop.run()` method

### 2. Conversation Turn Threshold Trigger
- **Threshold**: Conversation turns reach configured value (default 200 turns)
- **Trigger timing**: On each conversation turn check
- **Location**: `AgentRunLoop.run()` method

### 3. Manual Trigger
- **Marker**: LLM output contains `!!!SUMMARY!!!` marker
- **Location**: `AgentRunLoop.run()` method

### 4. User Command Trigger
- **Method**: Triggered by user via input handler
- **Location**: `builtin_input_handler.py`

## Compression Strategy Execution Flow

### Stage 1: Progressive Compression (Before Model Call)

When remaining tokens fall below threshold, compression strategies are executed in the following order:

```
Start
  ↓
Check remaining tokens < 25% threshold?
  ↓ Yes
Adaptive compression (select strategy based on task type)
  ↓
  ├─ Success?
  │   ├─ Yes → Check remaining tokens
  │   │        ├─ Still insufficient → Try other strategies (sliding window → importance scoring)
  │   │        └─ Sufficient → Continue execution
  │   └─ No → Fallback to fixed strategy order
  │            ├─ Sliding window compression (priority)
  │            ├─ Importance scoring compression
  │            ├─ Key event extraction compression
  │            └─ Incremental summarization compression
  ↓
Call model
```

#### 1.1 Adaptive Compression (Primary Strategy)

**Task Type Detection**:
- Code task (code): CodeAgent or contains code-related tool calls
- Analysis task (analysis): Contains analysis-related tool calls
- Conversation task (conversation): Mainly short user inputs and responses
- Mixed task (mixed): Contains multiple tool call types
- Unknown task (unknown): Cannot be clearly identified

**Strategy Selection (Sliding window prioritized)**:
- **Code task**: Sliding window → Key event extraction → Incremental summarization
- **Analysis task**: Sliding window → Importance scoring → Incremental summarization
- **Conversation task**: Sliding window → Importance scoring → Incremental summarization
- **Mixed task**: Sliding window → Incremental summarization → Importance scoring
- **Unknown task**: Sliding window → Importance scoring → Incremental summarization

#### 1.2 Fallback Strategies (If Adaptive Compression Fails)

If adaptive compression fails or remains insufficient, try in following order (sliding window prioritized):

1. **Sliding Window Compression (Priority)**
   - Keep recent user/tool messages (4) and assistant messages (5), total 9 messages (odd number to avoid consecutive same-role messages)
   - Compress earlier conversations into summary
   - Keep recent context intact

2. **Importance Scoring Compression**
   - Score messages by importance, keep high-scoring messages
   - Compress low-scoring messages into summary
   - Keep recent 5 low-scoring messages as context

3. **Key Event Extraction Compression**
   - Extract key events (task completion, error fixes, tool calls etc.)
   - Compress non-key events into summary
   - Keep recent 5 non-key messages as context

4. **Incremental Summarization Compression**
   - Split history into multiple chunks
   - Compress earlier chunks into summary
   - Keep last chunk intact
   - Compress earlier conversations into summary

### Stage 2: Full Summary Compression (Last Resort)

If progressive compression remains insufficient after trying all strategies, or conversation turn threshold is reached, execute full summary compression:

```
Trigger full summary compression
  ↓
Generate conversation summary (using LLM)
  ↓
Clear all conversation history
  ↓
Preserve key information:
  - Original task goal (original_user_input)
  - User pinned content (pin_content)
  - Recent memories (recent_memories)
  - Task list state
  - Git diff statistics (CodeAgent)
  ↓
Add summary as new context
  ↓
Reset conversation length counter
```

## Detailed Flow Description

### Flow 1: Compression Check Before Model Call

```python
# Location: AgentRunLoop.run()

while True:
    # 1. Check remaining tokens
    remaining_tokens = model.get_remaining_token_count()
    
    # 2. If below threshold, trigger compression
    if remaining_tokens < summary_remaining_token_threshold:
        # 2.1 Try adaptive compression
        success = agent._adaptive_compression()
        
        if success:
            # 2.2 Recalculate remaining tokens
            remaining_tokens = model.get_remaining_token_count()
            
            # 2.3 If still insufficient, try other strategies
            if remaining_tokens < threshold:
                # Try importance scoring compression
                # Try sliding window compression
        else:
            # 2.4 Fallback to fixed strategy order
            # Try importance scoring compression
            # Try key event extraction compression
            # Try incremental summarization compression
            # Try sliding window compression
    
    # 3. Call model
    response = agent._call_model(...)
```

### Flow 2: Adaptive Compression Internal Flow

```python
# Location: Agent._adaptive_compression()

def _adaptive_compression():
    # 1. Detect task type
    task_type = _detect_task_type()
    
    # 2. Select strategy based on task type (sliding window prioritized)
    if task_type == "code":
        # Code task: sliding window → key event extraction → incremental summarization
        return _sliding_window_compression() or \
               _key_event_extraction_compression() or \
               _incremental_summarization_compression()
    
    elif task_type == "analysis":
        # Analysis task: sliding window → importance scoring → incremental summarization
        return _sliding_window_compression() or \
               _importance_scoring_compression() or \
               _incremental_summarization_compression()
    
    elif task_type == "conversation":
        # Conversation task: sliding window → importance scoring → incremental summarization
        return _sliding_window_compression() or \
               _importance_scoring_compression() or \
               _incremental_summarization_compression()
    
    # ... other task types
```

### Flow 3: Full Summary Compression Flow

```python
# Location: Agent._summarize_and_clear_history()

def _summarize_and_clear_history():
    # 1. Generate summary
    summary = generate_summary()
    
    # 2. Get key information
    # - original_user_input
    # - pin_content
    # - recent_memories
    # - task list state
    # - git diff statistics
    
    # 3. Format summary message
    formatted_summary = _format_summary_message(summary)
    
    # 4. Clear history
    model.reset()
    session.clear_history()
    
    # 5. Add summary as new context
    session.addon_prompt = formatted_summary
    
    # 6. Reset counter
    conversation_length = 0
```

## Compression Strategy Comparison

| Strategy | Compression Intensity | Retained Content | Use Case |
|----------|---------------------|-----------------|----------|
| Importance Scoring | Light | High-scoring messages kept intact | General scenarios |
| Key Event Extraction | Medium | Key events kept intact | Code tasks, troubleshooting |
| Incremental Summarization | Medium | Recent chunk kept intact | Long conversations |
| Sliding Window | Medium | Recent N turns kept intact | Conversational tasks |
| Full Summary | Heavy | Only summary + key info preserved | Last resort |

## Key Information Preservation

Regardless of compression strategy, the following information is always preserved:

1. **Original Task Goal** (`original_user_input`)
   - User input from first run
   - Always kept at the front after summarization

2. **User Pinned Content** (`pin_content`)
   - Content marked by user with `<Pin>` tag
   - Full requirements in non-interactive mode

3. **System Messages**
   - System prompts
   - Never compressed

4. **Recent Memories** (`recent_memories`)
   - Last 10 memory entries

5. **Task List State**
   - Task list summary
   - Task execution progress

6. **Git Diff Statistics** (CodeAgent)
   - Code change statistics

## Compression Effect Evaluation

After each compression, the system:
1. Recalculates remaining token count
2. Checks if threshold is met
3. If still insufficient, tries next strategy
4. If all strategies fail or still insufficient, triggers full summary compression

## Configuration Parameters

### Environment Variables
- `sliding_window_size`: Sliding window size (default 9 messages: 4 user/tool + 5 assistant; odd number avoids consecutive same-role messages)
- `importance_score_threshold`: Importance score threshold (default 3.0)
- `incremental_summary_chunk_size`: Incremental summary chunk size (default 20 turns)
- `conversation_turn_threshold`: Conversation turn threshold (default 200 turns)

### Built-in Config
- `summary_remaining_token_threshold`: Remaining token threshold (25% of input window)
- Auto-calculated, no manual config needed

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│              Check before each model call                      │
└─────────────────────────────────────────────────────────────┘
                             ↓
         ┌───────────────────────────────────┐
         │  Remaining tokens < 25% threshold? │
         └───────────────────────────────────┘
                     ↓ Yes              ↓ No
         ┌──────────────────┐         Continue execution
         │  Adaptive compression │
         └──────────────────┘
                     ↓
         ┌───────────────────────────────────┐
         │  Detect task type                  │
         │  (code/analysis/conversation/...)  │
         └───────────────────────────────────┘
                     ↓
         ┌───────────────────────────────────┐
         │  Select strategy by task type     │
         │  - Code: key event extraction     │
         │  - Analysis: importance scoring   │
         │  - Conversation: sliding window   │
         └───────────────────────────────────┘
                     ↓
         ┌───────────────────────────────────┐
         │  Execute selected compression      │
         └───────────────────────────────────┘
                     ↓
         ┌───────────────────────────────────┐
         │  Compression successful?           │
         └───────────────────────────────────┘
         ↓ Yes              ↓ No
    Recalculate tokens   Fallback to fixed order
         ↓                    ↓
    Still insufficient?   Importance scoring
         ↓                    ↓
     Yes   No              Key event extraction
      ↓    │              Incremental summarization
      │    │              Sliding window
      │    │                    ↓
      │    │              Recalculate tokens
      │    │                    ↓
      │    │              Still insufficient?
      │    │              Yes   No
      │    │               ↓    │
      │    └───────────────┘    │
      │                         │
      └─────────────────────────┘
               ↓
     ┌─────────────────────────┐
     │  Full summary compression │
     │  - Generate summary       │
     │  - Clear history          │
     │  - Preserve key info      │
     │  - Add as new context     │
     └─────────────────────────┘
               ↓
          Continue execution
```

## Best Practices

1. **Prefer adaptive compression**: System auto-selects best strategy
2. **Set reasonable thresholds**: Adjust window size and scoring threshold based on usage
3. **Preserve key info**: Use `<Pin>` tag for important content to prevent compression
4. **Monitor compression effect**: Check remaining tokens after compression
5. **Regular checks**: For long-running sessions, monitor history; manually trigger summary if needed

## Notes

1. **Compression is irreversible**: Compressed history cannot be fully recovered; enable session file saving
2. **Key info prioritized**: Original task goal always preserved
3. **Progressive compression**: Prefer lightweight compression over clearing all history
4. **Fault tolerance**: Compression failure doesn't affect main flow; auto-fallback to other strategies
5. **Performance**: Compression consumes tokens but cheaper than context overflow