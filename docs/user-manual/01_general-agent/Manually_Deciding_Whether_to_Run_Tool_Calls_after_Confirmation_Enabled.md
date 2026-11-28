# Manually Deciding Whether to Run Tool Calls After Confirmation Is Enabled

## When to Use

When you do not want the agent to directly operate on files, execute commands, or call external capabilities without confirmation, you can turn on the confirmation flow and manually decide whether each tool call actually executes.

## Steps

1. First enter a session or startup mode where tool execution confirmation is already enabled.
2. Submit the task normally, letting the agent plan and attempt to call tools.
3. After the system displays the tool name and argument summary, it further asks whether you confirm the execution.
4. Choose to continue or cancel according to the situation.

## Prompts and Feedback You Will See

- Before the tool actually executes, the system asks: `Execute tool name to confirm execution?`
- If you confirm, the tool continues and actually executes.
- If you cancel, this tool call does not execute, and the system directly ends this round of the tool execution flow.
- If an error occurs during tool execution, the system prompts: `❌ Tool execution failed: ...`

## Notes

- This capability depends on tool confirmation already being enabled at the current entry point; not all sessions automatically show this step.
- This confirmation point is suitable for intercepting high-risk operations, such as writing files, executing scripts, network requests, etc.
- If you frequently cancel critical tools, the agent may be unable to complete the current task.
