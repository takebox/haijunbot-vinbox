# Intervening While an Agent is Running

## Use Cases

When the Agent is still executing a task but you want to actively insert an intervention signal in the middle so the current run responds to your manual handling intent as soon as possible, you can use the Web UI's manual intervention capability.

## Steps

1. First switch to the Agent that is currently running.
2. Trigger manual intervention using either of the following:
   - Open the command palette (`Ctrl+P`), search for and select the "Intervene" action (shortcut `Ctrl+Alt+I`).
   - While not in input mode and the input box is empty, press `Ctrl+C` to send a manual intervention signal.

3. The system sends the manual intervention signal to the current Agent immediately.
4. Then keep watching the message area and status changes, and wait for the Agent's follow-up response to this intervention.

## Feedback You Will See

- Manual intervention only applies to the currently selected Agent; if none is selected, the message "No Agent is selected" appears.
- After a successful send, the page shows "Interrupt signal sent".
- After sending, the page does not ask you to enter another command; this is a direct manual intervention operation.
- After intervening, the changes usually appear in the message area output, status changes, or a later request for you to enter content.

## Notes

- This is not ordinary text input but a dedicated manual intervention signal.
- Manual intervention only affects the currently selected Agent; if you switched to the wrong Agent, the signal goes to the wrong target.
- If the current Agent has already finished, or the current page has no live connection, the intervention may not have the expected effect.
- After sending manual intervention, keep watching the message area and status bar to decide whether you still need to provide more input or confirmations.
