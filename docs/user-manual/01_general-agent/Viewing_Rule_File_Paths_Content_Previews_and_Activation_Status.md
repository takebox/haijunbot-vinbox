# Viewing Rule File Paths, Content Previews, and Activation Status

## When to Use

When you are not sure which rules are currently available, where these rules come from, or whether they are already activated, you can bring up the rule list first and then decide which one to load next.

## Steps

1. Directly enter `'<ListRule>'` in the current conversation input box.
2. Press `Ctrl+J` or `Ctrl+]` to submit this instruction.
3. The system immediately lists the currently available rules, rather than treating this text as an ordinary task and continuing the conversation.
4. Look at the rule name, content preview, file path, and status in the list, then decide whether to continue using the relevant rules.

## Prompts and Feedback You Will See

- The list title is displayed as: `📋 All available rules`
- The table contains the following columns:
  - `Rule name`
  - `Content preview`
  - `File path`
  - `Status`
- The status column is displayed as:
  - `✅ Activated`
  - `🔴 Not activated`
- The bottom of the list also shows the total, for example: `Total: N rules`
- The content preview shows only the first short section, making it easy to quickly judge whether this rule is what you are looking for.

## Notes

- The content preview is not the full rule text; it is only suitable for quickly identifying the purpose.
- When the file path is too long, the interface may display it as a truncated short path.
- This step only views the status; it does not automatically enable or disable rules for you.
