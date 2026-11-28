# Viewing an Agent's Running Status

## Use Cases

When you want to determine whether an Agent is still processing a task, waiting for you to add multi-line content, waiting for your confirmation, or has already finished running, you can use the status display in the Web UI to quickly decide what to do next.

## Steps

1. First enter a successfully connected web page.
2. In the Agent list on the left, look at the status text to the right of each Agent's name.
3. If you have already switched to an Agent, you can also check its status again in the current Agent info area at the top.
4. Decide the next action based on the status:
   - If it shows "Running", it usually means the Agent is still processing the task
   - If it shows "Running (awaiting multi-line input)", now is the time to add content in the multi-line input box at the bottom
   - If it shows "Running (awaiting confirmation)", the input area at the bottom switches to a single-line input box, suitable for a quick one-line answer or short content
   - If it shows "Completed", this Agent has finished running and is suitable for reviewing history results

5. If a confirmation box appears separately in the message area, use its buttons to continue or cancel; this is a different scenario from the bottom single-line input state.

## Feedback You Will See

- The status text appears directly in the Agent list.
- The current Agent's status also appears at the top of the page.
- While the Agent is processing normally, "Agent is executing..." appears above the input area at the bottom.
- When the status switches to waiting for multi-line input, the "Done" and "@" completion buttons become available.
- When the status switches to "Running (awaiting confirmation)", the input area at the bottom switches to a single-line input box.
- If the system needs you to confirm something in the message area, a confirmation box appears with "Confirm" or "Cancel" buttons.
- When an Agent finishes, the status changes to "Completed", and you can still review its history messages.

## Notes

- "Running" does not necessarily mean you can type right away; only when it enters "awaiting multi-line input" is the page truly waiting for additional multi-line content.
- "Running (awaiting confirmation)" switches the bottom input area to single-line input, which is not suitable for continuing with long text.
- The confirmation box in the message area is a separate prompt; only when the page actually shows it do you need to click "Confirm" or "Cancel".
- A completed Agent does not disappear from the list; it usually stays in the list for you to review history later.
- If the status has not updated for a long time, first check whether the top of the current page still shows "Connected".
