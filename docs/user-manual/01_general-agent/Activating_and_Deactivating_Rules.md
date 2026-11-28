# Activating and Deactivating Rules

## When to Use

When you want certain rules to take effect only for the current task or current stage, rather than remaining enabled all the time, you can first check the current rule status, then toggle the enabled state as needed.

## Steps

1. First enter `'<ListRule>'` in the conversation input box, then press `Ctrl+J` or `Ctrl+]` to view the current rule list.
2. In the list, note down the name of the rule you want to handle, and first confirm whether it is currently `✅ Activated` or `🔴 Not activated`.
3. Then use the rule-toggling method supported by the current entry point to enable or disable the corresponding rule by rule name.
4. After toggling, enter `'<ListRule>'` again to view the result and confirm whether the status has changed.

## Prompts and Feedback You Will See

- After a successful enable, when you view it again, the rule changes from `🔴 Not activated` to `✅ Activated`.
- After a successful disable, when you view it again, the rule changes from `✅ Activated` to `🔴 Not activated`.
- Activated rules participate in subsequent conversations and task execution.
- Disabled rules simply no longer affect subsequent flows and will not retroactively modify content that has already been generated.

## Notes

- Checking the status first and then toggling the rule is more reliable than operating blindly.
- If the current entry point does not provide rule-toggling capability, you can at least use `'<ListRule>'` to confirm the rule name and status first, then switch to an entry point that supports rule management to continue.
- Activating too many rules may cause the current constraints to stack on top of each other, affecting the response style or the way tasks are executed.
