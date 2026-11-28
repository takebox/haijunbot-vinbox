# Automatically Triggering Memory Saving Before Clearing History or Task Completion When Forced Memory Is On

## When to Use

When you are worried that important information will be missed when history is cleared or the task completes, and you want the system to automatically make a memory-saving attempt first at key points, you can turn on forced memory mode.

## Steps

1. First enter a session or startup mode where forced memory is already turned on.
2. Execute the task normally.
3. When the system is about to clear history, or the task is about to complete, it automatically checks whether memory needs to be saved.
4. The system attempts to save silently, without affecting the main flow.

## Prompts and Feedback You Will See

- After forced memory is turned on, the system automatically triggers the memory-saving logic at key points.
- If saving succeeds, you will see: `✅ Valuable information has been automatically saved to the memory system`
- If saving fails or there is no information worth saving, the main flow is not blocked.

## Notes

- This feature depends on forced memory already being turned on at the current entry point; it is not executed automatically by every session by default.
- This feature is a "key-point fallback", not a replacement for all your active memory management operations.
- If you do not want the system to do extra memory processing at the ending stage, you should turn off the forced memory feature.
