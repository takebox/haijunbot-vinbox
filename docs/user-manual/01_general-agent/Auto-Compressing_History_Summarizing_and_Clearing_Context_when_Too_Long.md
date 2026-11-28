# Automatically Compressing History, Generating a Summary, and Clearing the Context When It Is Too Long

## When to Use

When your session has become very long, or a multi-turn conversation is about to approach the model's input limit, the system automatically compresses the context to avoid being unable to continue working because the history is too long.

## Steps

1. Continue a normal multi-turn conversation.
2. When the remaining context space is insufficient, or the number of conversation turns exceeds the threshold, the system automatically triggers compression; you do not need to manually enter a control command first.
3. The system first tries adaptive compression.
4. If adaptive compression is unsuccessful, the system falls back to the full-summary compression scheme, then continues the subsequent conversation.

## Prompts and Feedback You Will See

- When compression is triggered, the system prompts the trigger reason, for example:
  - `🔍 Token limit triggered...`
  - `🔍 Conversation turn limit triggered...`
  - `🔍 Token and turn double limit triggered...`
- If the current message itself is too long, the system may first prompt that the content is too long and truncate the middle part.
- After successful compression, you will see:
  - `✅ Adaptive compression complete, conversation context updated`
  - or `✅ Full-summary compression complete, conversation context updated`
- If truncation alone is already sufficient, the system prompts: `✅ No compression needed after truncation`

## Notes

- The goal of automatic compression is to preserve task continuity, not to retain every detail of the original conversation.
- For particularly critical information, it is recommended that you pin it or restate it clearly in advance, rather than relying entirely on history being retained automatically.
- If you find that the agent's understanding drifts after an extra-long session, you should first check whether summary compression has occurred.
