# Enabling System Prompt Auto-Optimization for the Code Agent

## When to Use

When your task description is relatively complex and has many goals, or you want the system to first automatically organize the way the task is expressed before formally executing, and then enter the code analysis and modification flow, you can enable system prompt auto-optimization.

## Steps

1. Open a terminal in the project directory.
2. Enter the following command, then press Enter:

   `hca --optimize-system-prompt`

3. If you already have the task ready, you can also enter it together directly, for example:

   `hca --optimize-system-prompt --task "sort out the exception branches of the order module, add logs, and fix the rollback problem"`

4. In interactive mode, after startup continue to enter your task content and submit it; in non-interactive mode, the system directly uses the content after `--task` to start executing.
5. During subsequent execution, the system first automatically optimizes the prompt used for the current task based on your needs, then continues the later code processing flow.

## Prompts and Feedback You Will See

- The startup method is basically the same as ordinary `hca`, and it still first completes the environment check and repository preparation.
- This capability does not additionally require you to enter new commands; it happens automatically under the premise that the current launch parameter is enabled.
- If you also provided task content, the system enters execution directly; if you did not provide task content, in interactive mode it still waits for you to input your requirement.

## Notes

- This is a switch at startup, not a command you enter temporarily halfway through task execution.
- Its role is to make the system better fit the current code task goal; it is not the same as filling in missing requirements for you; your original task description should still be written as clearly as possible.
- If you are only handling a very simple and very clear small task, you do not necessarily need to specifically enable this option.
