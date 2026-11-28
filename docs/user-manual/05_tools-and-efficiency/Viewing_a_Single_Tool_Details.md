# View a Single Tool's Details

## Use Cases

When you already know the name of a tool but are not yet clear about what it specifically does, which arguments it needs, and what its argument structure looks like, you can view this tool's detailed description separately.

## Steps

1. First confirm the target tool name through "list all available tools".
2. If you need to read it manually, run: `ht show toolname`.
3. For example, to view `read_code`, you can run: `ht show read_code`.
4. If you need to hand the result to a script, an automated flow, or another system for processing, you can switch to the JSON output mode: `ht show toolname --json`.
5. After confirming the argument structure, decide whether to continue directly calling this tool.

## Prompts and Feedback You Will See

- When you run `ht show toolname`, the terminal displays this tool's detailed information, including:

  - tool name
  - description
  - protocol version
  - argument definitions

- If this tool has no arguments, the interface clearly displays "no arguments".
- When you run `ht show toolname --json`, it outputs the complete structured tool information.
- If the tool name does not exist, the system clearly prompts that the tool does not exist and exits directly.

## Notes

- The tool name must match a name already registered in the system; entering a wrong name reports an error directly.
- The default output is more suitable for human reading; `--json` is more suitable for further processing.
- If you only want to confirm a few required arguments, it is recommended to focus on the `required` and `properties` parts of the argument definitions.
- Viewing the details does not execute the tool itself; it only helps you confirm the input method before calling.
