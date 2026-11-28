# View All Available Rule Indexes

## Use Cases

When you want to quickly understand what rules are available in the current system and the rough description of each rule, you can use the rule index viewing command.

## Steps

1. If you want to quickly browse the rule indexes, run: `hri`.
2. If you need a structured result, run: `hri --json`.
3. If you want to get the raw content without beautification, run: `hri --raw`.
4. You can also first browse quickly in the default mode, then switch to `--json` or `--raw` as needed.
5. After viewing the output, decide whether to continue loading or using the relevant rules in other commands.

## Prompts and Feedback You Will See

- When you run `hri`, the system displays all available rules and their descriptions in an easy-to-read format.
- When you run `hri --json`, the output is more suitable for program processing or saving.
- When you run `hri --raw`, the system directly prints the raw content without additional beautification.
- The output usually contains index information from multiple categories of rule sources, making it easy for you to get a quick overview.

## Notes

- The goal of this command is to "view the rule indexes", not to directly load the rule body.
- The default mode is suitable for human reading; `--json` and `--raw` are more suitable for automated processing, copying, or comparison.
- If you only need to quickly confirm which rules there are, the default mode is usually sufficient.
- The rule index content changes with the currently available rule set and may not be entirely consistent across environments.
