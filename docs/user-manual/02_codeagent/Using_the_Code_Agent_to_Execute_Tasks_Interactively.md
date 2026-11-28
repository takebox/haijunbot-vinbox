# Using the Code Agent to Execute Code Analysis, Modification, or Generation Tasks

## When to Use

When you want the code agent to help you analyze code, modify implementations, generate new code, or continue doing verification and subsequent organization after the modification is complete in the current project, you can directly use the code agent to start a task.

## Steps

1. First open a terminal in your project directory.
2. Choose one of the following two entries according to your usage:

   - **Interactive mode**: enter `hca`, then press Enter.
   - **Non-interactive mode**: enter a command like the following, then press Enter:

     `hca -n --task "fix the problem of configuration loading failure, and check related files"`

3. If the current directory is not yet a Git repository:
   - In interactive mode, the system first asks whether you want to initialize a Git repository.
   - In non-interactive mode, the system directly tries to prepare the repository environment by continuing initialization.
4. If you use interactive mode, after entering the interface directly enter this code task, for example "help me fix the null pointer problem of the login interface and add the necessary tests", then submit following the prompt.
5. If you use non-interactive mode, the system directly uses the content after `--task` as the task description to start executing, and no longer enters the interactive input interface.
6. Wait for the system to complete this round of code analysis, modification, verification, and subsequent processing, and view the result in the terminal.

## Prompts and Feedback You Will See

- After startup you see a welcome message, indicating that the code agent is ready.
- In interactive mode, you see a prompt to input your requirement, and can continue to enter task content.
- If a history session consistent with the current commit exists in the current repository, in interactive mode the system may first let you choose whether to restore one of the sessions, then continue to enter a new requirement.
- In non-interactive mode, the system does not open the input interface again, but directly uses the content after `--task` to start executing.
- If you only write `hca -n` without providing `--task` at the same time, the system reports an error directly and indicates that `--task` must be used to pass in the task content.
- If you end in interactive mode without entering anything, this run exits directly and does not continue to execute the task.

## Notes

- Interactive mode suits tasks where you add explanations as you think; non-interactive mode is better suited to scripts, automated flows, and one-off clear tasks.
- Non-interactive mode must be used together with `--task`; you cannot start it and then manually add the requirement later.
- If the task is very long, it is recommended to switch to the task file method, rather than hard-writing the whole description into the command line.
- If you want to directly restore an old session rather than wait for the system to prompt automatically, you can switch to a startup method with `--restore-session`.
