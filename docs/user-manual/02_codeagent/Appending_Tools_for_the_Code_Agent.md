# Appending Tools for the Code Agent

## When to Use

When the default toolset is not enough and you want the current code task to also have some extra tool capabilities, you can temporarily append tools when starting the code agent.

## Steps

1. Open a terminal in the project directory.
2. Enter a command like: `hca --append-tools "toolA,toolB" --task "your task"`
3. If you are only appending one tool, you can also write just one name, for example: `hca --append-tools "tool_x" --task "your task"`
4. After pressing Enter, on top of the code agent's default toolset, the system will bring the extra tools you specified along into this task.
5. Wait for the task to finish executing.

## Prompts and Feedback You Will See

- After appending tools, the system continues to run in the normal way, and you do not need to manually enable these tools again after entering the task.
- If the same tool is already in the default toolset, the system automatically avoids appending it twice.
- After a successful append, the range of tools available for this task will be larger than the default, but the terminal usually still shows normal task execution output.

## Notes

- Separate multiple tool names with an English comma.
- This only affects the current launch and is not the same as permanently changing the default toolset.
- Before appending tools, it is best to confirm that these tools are actually supported by the current environment; if a tool name is misspelled, the expected effect may not be achieved.
- If you are not sure whether you really need extra tools, prefer keeping the minimal toolset, which is usually easier for controlling task boundaries.
