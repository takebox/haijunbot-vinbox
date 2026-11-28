# Install the Smart Shell Not-Found Handler for bash

## Use Cases

When you use bash and want the system to generate a more reasonable suggested command after you enter a long but nonexistent command, and to let you edit it before deciding whether to execute it, you can install the smart Shell handler for bash.

## Steps

1. Confirm that you are using or about to use the bash shell.
2. In the terminal, enter: `hss install --shell bash`.
3. If `~/.bashrc` does not yet exist on the machine, the system automatically creates the file.
4. After the installation is complete, reload the bash configuration as prompted.
5. Afterward, when you enter a long but nonexistent command in bash, the system first generates a suggested command.
6. In interactive bash, this suggestion is pre-filled into the command input area; you can press Enter to execute it directly, or edit it first and then execute.

## Prompts and Feedback You Will See

- After a successful installation, the terminal prompts that the bash completion has been installed.
- It also prompts you to run: `source ~/.bashrc`.
- If it was already installed before, running it again directly prompts that it is already installed.
- After being triggered in interactive bash, the suggested command is pre-filled and you can modify it before executing.
- In non-interactive mode, the system only prints the suggested command and does not enter the editable input state.

## Notes

- bash, fish, and zsh have different interaction modes; bash leans more toward "editable after pre-fill".
- If you do not reload `~/.bashrc`, it may not take effect immediately in the current terminal session.
- The handler only takes effect for longer unrecognized input; overly short input does not trigger it.
- Whether it actually executes after being triggered depends on whether you confirm and press Enter in the interactive environment.
