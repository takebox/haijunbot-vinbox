# Previewing the Tools and Argument Summaries to Be Executed Before Tool Calls

## When to Use

When you want to check what the agent is about to do and whether the arguments are reasonable before it actually calls a tool, you can use the pre-tool-call preview capability.

## Steps

1. First enter a session or startup mode with tool confirmation enabled.
2. Enter your task normally and submit it in the usual way.
3. When the agent is about to call a tool, it does not execute immediately; instead, it first shows the tool name and argument summary.
4. First see clearly what is about to be executed this time, then decide whether to allow it to continue.

## Prompts and Feedback You Will See

- If there is only one tool call this round, the system displays: `🔧 About to execute tool: tool name`
- If multiple tool calls are about to execute at the same time, the system displays: `🔧 About to execute N tool calls:`, and lists the number, tool name, and argument summary item by item
- The argument summary automatically compresses longer content and hides sensitive fields
- Afterward the system continues into the confirmation flow, letting you decide whether this tool call executes

## Notes

- What you see is a summary, not necessarily the full text of all original arguments.
- If the summary is already clearly wrong, it usually means the agent's next action needs to be stopped or corrected.
- This capability shows a preview first only when the confirmation flow is enabled; if it is not enabled, the tool may execute directly without previewing first.
