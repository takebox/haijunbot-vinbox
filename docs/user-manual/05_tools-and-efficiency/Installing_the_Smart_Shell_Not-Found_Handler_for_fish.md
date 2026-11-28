# Install the Smart Shell Not-Found Handler for fish

## Use Cases

When you use fish as your daily Shell and want the system to automatically turn a long but nonexistent command you enter into a suggested command and replace it in the command line, you can install the smart Shell handler for fish.

## Steps

1. Confirm that you are using or about to use the fish shell.
2. In the terminal, enter: `hss install --shell fish`.
3. If fish's configuration file does not yet exist on the machine, the system automatically creates the required directory and configuration file.
4. After the installation is complete, reload the fish configuration as prompted.
5. Afterward, when you enter a long but nonexistent command in fish, the system tries to convert this content into a suggested command and backfill it into the command line.

## Prompts and Feedback You Will See

- After a successful installation, the terminal prompts that the fish completion has been installed.
- It also prompts you to run: `source ~/.config/fish/config.fish`.
- If it was already installed before, installing again directly prompts that it is already installed and does not write again.
- After it takes effect, when you enter a long but unrecognizable command, the system tries to give a suggested command and replace the current command-line content.

## Notes

- What is installed here is a fish-specific handler, not applicable to bash or zsh.
- After the installation is complete, if you do not reload the configuration, it may not take effect immediately in the current shell session.
- The handler only intervenes when the command is long enough; overly short input does not trigger it.
- The goal of this capability is to "give and backfill a suggested command", not to guarantee automatic execution of any operation.
