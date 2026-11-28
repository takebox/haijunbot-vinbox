# Using hcad to Dispatch Code Tasks Directly

## When to Use

When you just want to quickly throw a code task to the code agent to execute, and want the system to automatically start in a suitable dispatch way, without wanting to manually assemble the longer `hca` parameters, you can use `hcad` directly.

## Steps

1. First open a terminal in the project directory.
2. Enter the following command, then press Enter:

   `hcad "fix the exception of the export interface with empty data, and add regression tests"`

3. If this content is a single-line task, the system directly dispatches it to the code agent to execute.
4. If the content you pass in is itself a file path that already exists, the system treats it as a task file, rather than as ordinary text.
5. After dispatching, wait for the system to hand the task to the code agent to run.

## Prompts and Feedback You Will See

- `hcad` calls the code agent's dispatch flow, so you usually see the execution information subsequently output by the code agent.
- If the system cannot find the `hca` command, the terminal reports an error directly and prompts you to first confirm that HaijunBot is correctly installed.
- If what you provide is multi-line content, `hcad` automatically switches to the temporary file approach and then dispatches, rather than forcing the whole block of text into one command.

## Notes

- `hcad` is better suited to quickly starting one-off tasks, and not to scenarios where you need to continue long interactive supplementary explanations after startup.
- If what you pass in is a file path, the system reads it as a task file; if you originally meant to pass ordinary text, please confirm that this text is not a file name that actually exists in the current directory.
- To directly input a longer multi-paragraph task, it is recommended to use `hcad`'s interactive input method, rather than hard-writing multiple paragraphs of text in one command.
