# Checking Whether the History Messages Exceed the Current Model's Token Limit Before Restoring a Session

## When to Use

When you are about to restore a very long historical session, the system first checks whether these history messages already exceed the input limit the current model can bear, to avoid failing immediately due to exceeding the limit right after restoring.

## Steps

1. First return to the original project directory and start HaijunBot.
2. If the current entry point supports session restore, enter `'<RestoreSession>'` in the conversation input box, then press `Ctrl+J` or `Ctrl+]` to submit.
3. After selecting the session to restore, the system first counts the token usage of this segment of history messages.
4. The system then compares this result with the maximum input limit of the current model group.
5. If the limit is already exceeded, it directly blocks the restore; if it is close to the limit, it also warns you of the risk first.

## Prompts and Feedback You Will See

- During the restore, the system prints statistics: `📊 Session token stats: used X, max limit Y`
- If the upper limit is already exceeded, the system blocks the restore and prompts: `❌ Session restore failed: the number of tokens in the history messages exceeds the current model's limit.`
- If it is not over the limit but is very close to it, the system also gives a warning first, reminding you that the available space after restoring is limited.

## Notes

- This step checks the current model; different model groups may have different bearable upper limits.
- The fact that the same session can be restored under one model does not mean it can definitely be restored under another model.
- If you encounter an over-limit problem, you can first switch to a model that supports a larger context, then retry the restore.
