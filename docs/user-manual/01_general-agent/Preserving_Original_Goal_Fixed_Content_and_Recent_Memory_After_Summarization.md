# Preserving the Original Task Goal, Pinned Content, and Recent Memory After Summarization

## When to Use

When a conversation has become very long and summary compression is triggered, what you may worry about most is: the original task being lost, previously pinned important requirements being forgotten, and recent key memory disappearing. This feature is designed to solve this problem.

## Steps

1. Carry on a normal long conversation until the system automatically triggers summary compression.
2. If you have previously pinned long-term requirements, or the system has already saved recent memory, this content is prioritized and organized during compression, and you do not need to re-enter it manually.
3. After compression completes, continue working based on the new summary context.

## Prompts and Feedback You Will See

- The summary content is organized into a new context, rather than simply clearing the history and starting over.
- The system prioritizes retaining the following content:
  - The original task goal
  - Important requirements saved through the pinning feature
  - Recent memory
- This content is placed at the front of the summary as high-priority information for continuing the subsequent task.

## Notes

- If some information is particularly critical, it is best to pin it in advance and not rely only on the system remembering it automatically.
- Recent memory retains only a portion; it does not mean all historical details are fully kept.
- The post-summary context is more oriented toward "preserving the main thread" and is not something to rely on to retain every original line of conversation.
