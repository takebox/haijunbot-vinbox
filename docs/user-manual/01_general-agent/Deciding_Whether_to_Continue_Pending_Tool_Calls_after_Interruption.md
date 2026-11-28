# Deciding Whether to Continue a Pending Tool Call After an Interruption

## When to Use

When you notice during the agent's run that it may be about to perform some tool operation, but you still want to intervene first, you can use an interruption to buy yourself one opportunity for human decision-making.

## Steps

1. While the agent is outputting, press the interrupt shortcut to interrupt the current output.
2. After the interruption, the system prompts you to enter supplementary information: `⚠ Interruption detected, please enter supplementary information (Ctrl+J/Ctrl+] to confirm, press Enter directly to skip)`
3. If you have new constraints or corrections, enter the content and press `Ctrl+J` or `Ctrl+]` to submit; if you have nothing to add, press Enter directly to skip.
4. If there are still tool calls about to execute afterward, and the current session has tool confirmation enabled, the system continues into the tool confirmation flow.
5. In the confirmation interface, decide again whether this tool call should continue executing.

## Prompts and Feedback You Will See

- The interruption itself does not forcibly cancel all subsequent actions for you; instead, it first gives you a chance to insert supplementary information.
- After the interruption you will first see: `⚠ Interruption detected, please enter supplementary information (Ctrl+J/Ctrl+] to confirm, press Enter directly to skip)`
- If the tool confirmation feature is enabled, you can still decide again whether to allow it before the tool actually executes.
- This prevents the agent from continuing to execute the tool operations in the original plan after you have already spotted a problem.

## Notes

- Interruption and tool confirmation are two different layers of protection: the former is for supplementary notes, the latter is for final approval or cancellation of execution.
- If tool confirmation is not enabled, whether the tools after the interruption continue executing depends on whether the subsequent flow still considers that action necessary.
- For high-risk operations, it is recommended to use both the interruption capability and the tool confirmation capability.
