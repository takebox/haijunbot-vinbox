# Install the Smart Shell Not-Found Handler for zsh

## Use Cases

When you use zsh and want the system to first give a suggested command after you enter a long but nonexistent command, and to let you modify it in an editor before executing, you can install the smart Shell handler for zsh.

## Steps

1. Confirm that you are using or about to use the zsh shell.
2. In the terminal, enter: `hss install --shell zsh`.
3. If `~/.zshrc` does not yet exist on the machine, the system automatically creates the file.
4. After the installation is complete, reload the zsh configuration as prompted.
5. Afterward, when you enter a long but nonexistent command in zsh, the system first generates a suggested command.
6. In interactive zsh, the system invokes your editor to open the suggested command; you can modify it, save and exit, then continue executing.

## Prompts and Feedback You Will See

- After a successful installation, the terminal prompts that the zsh completion has been installed.
- It also prompts you to run: `source ~/.zshrc`.
- If it was already installed, installing again directly prompts that it is already installed.
- After being triggered in interactive zsh, the system opens the current editor, letting you modify the suggested command first.
- In non-interactive mode, the system only prints the suggested command and does not open the editor.

## Notes

- zsh's interactive experience differs from bash and fish; it leans more toward "modify in the editor, then execute".
- Which editor is currently used depends on your `VISUAL` or `EDITOR` environment setting; if neither is set, it falls back to the default editor.
- If you do not reload `~/.zshrc`, it may not take effect immediately in the current terminal session.
- The handler only triggers for longer unrecognized input; overly short input does not intervene.
