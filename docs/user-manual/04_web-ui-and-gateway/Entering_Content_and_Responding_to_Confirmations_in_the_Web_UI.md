# Entering Content and Responding to Confirmations in the Web UI

## Use Cases

When the Agent is processing a task in the web page, you may need to add more multi-line explanations, answer a single-line input request, or confirm a step. This document helps you determine when to type, how to send, and what to do when a confirmation box appears.

## Steps

### Sending Multi-line Input

1. First switch to the target Agent.
2. Check whether the input area at the bottom is a multi-line input box.
3. Type your additional content directly in the input box.
4. To send, press Ctrl+Enter, or click "Send (Ctrl+Enter)".
5. If the current Agent is waiting for multi-line input, this content is sent to the Agent directly.

### Sending Single-line Input

1. When "Running (awaiting confirmation)" appears at the top of the page or in the Agent list, first check whether the input area at the bottom has switched to a single-line input box.
2. Type your answer in the single-line input box.
3. Press Enter to send.
4. After sending, the input area usually switches back to multi-line mode.

### Sending the Completion Signal

1. When the page is in the "waiting for multi-line input" state and you have finished typing your additional content, click "Done".
2. The page first shows a confirmation prompt: "Are you sure you want to send the completion signal?".
3. After confirming, the system tells the Agent that your multi-line input has ended.
4. If you are currently waiting for multi-line input and the input box is empty, you can also press Ctrl+C directly to trigger the same completion action.

### Handling the Confirmation Box

1. When a confirmation box appears in the message area, read the confirmation content.
2. Click "Confirm" or "Cancel" as needed.
3. If focus is already on a button, you can also press Enter to submit the button that currently has focus.
4. When a confirmation box appears, treat it as a button-confirmation scenario, not as a bottom single-line input scenario.

## Feedback You Will See

- The multi-line input box placeholder reads like "Enter content (Ctrl+Enter to send)".
- The single-line input box placeholder reads like "Enter content (Enter to send)".
- When the page shows "Running (awaiting confirmation)", the input area at the bottom switches to a single-line input box.
- When there is no available Agent, or the Agent is not in an input-capable state, the input box shows "Agent is not running".
- When the Agent is processing a task, the input area shows "Agent is executing..." above it.
- Ordinary input you send successfully is echoed back into the message area so you can review what you entered.
- If the system issues another confirmation request, a confirmation box appears in the message area with "Confirm" or "Cancel" buttons.

## Notes

- Multi-line and single-line input use different send keys: multi-line uses Ctrl+Enter, single-line uses Enter.
- "Running (awaiting confirmation)" corresponds to the bottom single-line input state and is not suitable for continuing with long text.
- The "Done" button is only available when the page is waiting for multi-line input; it is not ordinary text sending, but tells the Agent that the current round of multi-line input has ended.
- The confirmation box in the message area is an independent prompt; only when you actually see it do you need to handle it with buttons.
