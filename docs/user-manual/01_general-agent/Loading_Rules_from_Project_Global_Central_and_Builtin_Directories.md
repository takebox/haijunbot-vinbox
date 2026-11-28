# Loading Rules from the Project, Global, Central Repository, and Builtin Directories

## When to Use

When you want to use project-specific rules, personal long-term rules, team-shared rules, or system built-in rules at the same time, HaijunBot brings rules from multiple sources into a unified available list for you to view and select later.

## Steps

1. First place the rules in the corresponding source, such as a project rule directory, a personal global rule directory, a team-shared rule repository, or an additional config directory.
2. Start HaijunBot and enter an interactive conversation.
3. In the input box, enter `'<ListRule>'`, and press `Ctrl+J` or `Ctrl+]` to submit.
4. The system lists all currently recognized rules in a unified way, and you can see rule items from different sources in the list.
5. If you need to precisely specify the rules of a certain source, then use prefixed rule names to continue the operation.

## Prompts and Feedback You Will See

- The list displays rules from different sources in a unified way, rather than only showing the contents of one directory.
- You can tell where a rule comes from by its `rule name` and `file path`.
- The list also displays a `content preview` and `status`, so you can identify it first before deciding whether to use it.
- If a shared source is currently unavailable, the corresponding rules may not appear in the list.

## Notes

- This document describes "being uniformly recognized and included in the available list", which does not mean all rules take effect automatically and immediately.
- Project rules are more suitable for constraints specific to the current repository, while global rules are more suitable for personal long-term preferences.
- Team-shared rules depend on the external source being accessible; if that source did not sync successfully, the corresponding rules may not be visible in the list.
