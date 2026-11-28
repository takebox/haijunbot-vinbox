# Viewing Execution Terminal Output in Messages

## Use Cases

When the Agent executes certain tasks, the web message area may embed terminal output in addition to normal text replies. This capability is suitable for viewing the command execution process, standard output, and error output in real time, and for reviewing that terminal history after the task ends.

## Steps

1. Switch to the Agent that is executing a task.
2. Look for new execution messages in the message area.
3. When an execution starts producing terminal-stream output, an embedded terminal area appears in the message area.
4. While the execution is running, watch the output scroll directly in this area.
5. When the execution ends, stay in the current session to review the results; the original live terminal turns into a history output block.
6. If you refresh the page later, re-enter the same Agent, or load its history messages again, you can continue to view the saved terminal history.

## Feedback You Will See

- While an execution is running, a terminal-style embedded area appears in the message area.
- After the execution ends, this area becomes a history display block titled something like "Terminal Output".
- Finished terminal history keeps the full text for later review.
- If an Agent has a lot of history messages, scrolling up in the message area loads the old execution terminal history together with the history messages.

## Notes

- This refers to the execution terminal in the message area, not the standalone terminal panel opened by the button at the top; the two serve different purposes.
- An unfinished execution terminal is mainly for real-time viewing; what is actually saved to history is the terminal text content assembled after the execution ends.
- If you switch to a completed Agent, you can usually only view its preserved terminal history, rather than continuing to interact with that execution in real time.
- If the current page connection drops, the live terminal stream is affected; after reconnecting, you can still review the history content that was already saved.
