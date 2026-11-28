# Call a Specific Tool Directly from the Command Line

## Use Cases

When you already know the name and argument structure of a tool and want to bypass other interfaces to directly execute that tool from the command line and view the execution result, you can use the tool system's invocation command.

## Steps

1. First confirm the target tool name and argument requirements.
2. If the tool has no required arguments, you can run directly: `ht call toolname`.
3. If you need to pass arguments directly on the command line, you can use `--args` to pass a JSON string, for example: `ht call read_code --args '{"files":[{"path":"README.md","start_line":1,"end_line":20}]}'`.
4. If the arguments are long, it is recommended to first write them to a JSON file and then read it via `--args-file`, for example: `ht call read_code --args-file ./args.json`.
5. The content in `args.json` should be consistent with the tool's argument structure, for example: `{"files":[{"path":"README.md","start_line":1,"end_line":20}]}`.
6. After submitting the command, wait for the tool to finish executing and view the result; if execution fails, correct the missing-argument prompt, JSON format error prompt, or tool error output shown in the terminal and try again.

## Prompts and Feedback You Will See

- After the tool executes, the system clearly displays:

  - the tool executed successfully
  - or the tool execution failed

- If the tool has standard output, it displays the "output" content.
- If the tool has error output, it displays the "error" content.
- If the content in `--args` or `--args-file` is not valid JSON, it directly prompts an argument format error.
- If required arguments are missing, the system clearly lists:

  - which arguments are missing
  - the description of each required argument

- If the tool name does not exist, the system directly prompts that the tool does not exist.

## Notes

- Both `--args` and `--args-file` require the argument content to be valid JSON, and the field names and hierarchy must match the argument definitions seen with `ht show toolname`.
- When arguments are long and deeply nested, it is more suitable to first write them to a JSON file and then read them with `--args-file`.
- If the tool execution fails, it is not necessarily that the tool system itself has a problem; it may also be that the business arguments you passed are incorrect.
- The invocation command actually executes the target tool, so when it comes to tools that write files, make network requests, or change state, confirm the scope of impact first.
