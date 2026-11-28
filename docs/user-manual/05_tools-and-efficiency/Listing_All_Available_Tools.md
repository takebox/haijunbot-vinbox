# List All Available Tools

## Use Cases

When you want to first learn what tools HaijunBot currently provides, roughly what each tool does, and whether you need to further check the argument descriptions, you can start with the tool system's list command.

## Steps

1. In the terminal, enter an environment where HaijunBot commands can be used.
2. If you only want to quickly browse the tool names and descriptions, run: `ht list`.
3. If you want a program or script to further process the result, run: `ht list --json`.
4. If you also want to view each tool's argument structure, run: `ht list --detailed`.
5. If you want to see the detailed fields and also hand them to a program for processing, you can combine them: `ht list --detailed --json`.
6. After viewing the result, note down the target tool name, then continue to use the "view a single tool's details" command to confirm the specific arguments.

## Prompts and Feedback You Will See

- When you run `ht list`, the terminal displays the "available tools list".
- Each tool usually displays:

  - tool name
  - tool description

- After running `ht list --detailed`, you also see each tool's argument structure.
- When you run `ht list --json`, the output becomes structured JSON:

  - the normal JSON mode contains only names and descriptions
  - `ht list --detailed --json` contains more complete tool information

## Notes

- This is a command-line operation, not a feature in a Web page.
- The default mode is more suitable for human reading; `--json` is more suitable for script processing or copying to other systems.
- `--detailed` makes the output longer, suitable for confirming the argument structure before you are about to further call a tool.
- The number and content of tools depend on the currently registered tool set and may differ slightly across environments.
- If you already know a tool's name, the next step is usually to view that tool's details directly.
