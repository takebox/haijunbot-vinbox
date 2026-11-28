# Uninstall the Smart Shell Not-Found Handler

## Use Cases

When you no longer want the Shell to automatically intercept "command not found" and generate a suggested command, or want to restore the original shell behavior, you can uninstall the already installed smart Shell handler.

## Steps

1. In the terminal, run the JSS uninstall command, for example: `hss uninstall --shell bash`.
2. Specify the shell type you want to uninstall:

   - fish
   - bash
   - zsh

3. After submitting the command, the system removes the previously installed JSS configuration snippet from the corresponding shell's configuration file.
4. After the uninstall is complete, reload the corresponding shell configuration file as prompted.
5. After reloading, the Shell returns to the ordinary "command not found" behavior.

## Prompts and Feedback You Will See

- After a successful uninstall, the system prompts that the corresponding shell's completion has been uninstalled.
- It also prompts you to re-source the corresponding configuration file.
- If the target configuration file does not exist, the system directly prompts that there is no content to uninstall.
- If it was never installed in the first place, the system also clearly prompts that it is not installed, rather than falsely reporting success.
- If you specify an unsupported shell type, the system reports an error directly.

## Notes

- Uninstallation is performed per shell type and does not clean up all shells at once.
- After uninstalling, if you do not reload the configuration, the old behavior may still remain in the current terminal session.
- Only the three shell types fish, bash, and zsh are supported.
- If you later want to restore this capability, you can run the corresponding shell's install command again.
