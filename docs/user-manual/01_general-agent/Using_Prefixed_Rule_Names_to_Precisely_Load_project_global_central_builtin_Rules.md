# Using Prefixed Rule Names to Precisely Load project / global / central / builtin Rules

## When to Use

When rules with the same name exist in different sources, or you clearly know that you want to use the one under a certain source, you can add a prefix to the rule name to reduce confusion.

## Steps

1. First enter `'<ListRule>'` and press `Ctrl+J` or `Ctrl+]` to confirm that the target rule indeed exists.
2. Note down the rule name, and confirm which source it belongs to.
3. When referencing this rule afterward, use the prefixed rule name directly, for example:
   - `builtin:rule-name`
   - `project:rule-name`
   - `global:rule-name`
   - `central:rule-name`
   - `configN:rule-name`
4. After submitting, the system looks up the rule by the source you specified first, rather than doing fuzzy matching again.

## Prompts and Feedback You Will See

- After using a prefixed rule name, the system processes it by the specified source, and no longer prioritizes guessing which same-named rule you want.
- If the corresponding rule exists under that source, the subsequent flow continues with that rule.
- If that rule does not exist under that source, you will encounter a situation where the corresponding rule cannot be found, and you need to re-check the prefix or the rule name.

## Notes

- This kind of prefix is suitable when there are many same-named rules and can noticeably reduce ambiguity.
- Writing the prefix wrong, the source wrong, or the rule name wrong will all cause the target rule to fail to match.
- If you are not sure whether the rule exists, first use `'<ListRule>'` to look at the list, then write the prefixed name, which is the most reliable.
