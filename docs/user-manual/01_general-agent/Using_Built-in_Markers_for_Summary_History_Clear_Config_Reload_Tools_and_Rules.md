# Executing Summary, Clearing History, Reloading Config, and Viewing Tool Usage and Rule Status via Built-in Markers

## When to Use

When you have already been working in a session for a while and want to quickly trigger system operations rather than exiting and restarting, you can use built-in markers directly in the input.

## Steps

1. Write the corresponding built-in marker in the current conversation input box, for example:
   - `'<Summary>'` to summarize the current context
   - `'<Clear>'` to clear history
   - `'<ToolUsage>'` to view the tool usage instructions
   - `'<ReloadConfig>'` to reload the config
   - `'<ListRule>'` to view the rule status
2. Press `Ctrl+J` or `Ctrl+]` to submit.
3. The system immediately executes the corresponding operation, rather than treating these markers as ordinary task text.

## Prompts and Feedback You Will See

- After using `'<Summary>'`, the system performs a summary and uses the summary result as the basis for continuing to work afterward.
- After using `'<Clear>'`, the current history is cleared.
- After using `'<ToolUsage>'`, the system adds the tool usage instructions to the current session prompt.
- After using `'<ReloadConfig>'`, the system reloads the config.
- After using `'<ListRule>'`, the system displays a rule table containing the rule name, content preview, file path, and status, and shows `✅ Activated` or `🔴 Not activated`.

## Notes

- These markers are session-control operations and are not suitable for being mixed heavily with ordinary task descriptions.
- Both clearing history and summarizing affect the current context; before executing, confirm whether you still need to keep the current conversation chain.
- If you just want the agent to explain a concept, do not misuse these control markers.
