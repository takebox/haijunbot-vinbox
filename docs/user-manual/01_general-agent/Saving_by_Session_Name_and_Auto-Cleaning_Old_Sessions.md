# Saving by Session Name and Auto-Cleaning Old Sessions

## When to Use

As the sessions you save grow in number, the system tries to give each session an easily recognizable name and automatically cleans up overly old records, to avoid the directory growing without bound.

## Steps

1. First ensure the current session already has actual task input content.
2. If the current entry point supports session saving, enter `'<SaveSession>'` in the conversation input box, then press `Ctrl+J` or `Ctrl+]` to submit.
3. If the current session does not have a name yet, the system generates a short Chinese name based on your original input.
4. The saved file name carries this session name and a timestamp.
5. When too many sessions of the same kind are saved, the system automatically cleans up old sessions and keeps only the most recent batch.

## Prompts and Feedback You Will See

- When generating a name for the first time, the system prompts: `📝 Generating session name: ...`
- On a successful save, you will also see: `✅ Session saved successfully.`
- The saved file name includes the session name, the Agent name, and the timestamp, making it easy to distinguish different sessions.
- The system automatically cleans up old sessions and by default keeps only the most recent 10 main sessions and their auxiliary files.

## Notes

- The session name comes from an automatic summary of the original task content, and may not be exactly the same as your manual title.
- If you restore from an old session and then continue saving, the system prefers to keep using the original session name.
- If the current entry point does not support `'<SaveSession>'`, you need to switch to an entry point that supports session saving to operate.
