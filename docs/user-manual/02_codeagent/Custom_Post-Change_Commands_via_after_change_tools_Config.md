# Customizing Post-Change Processing Commands via Global or Project-Level after_change_tools Config

## When to Use

When the default post-change processing rules are not enough, for example when you want a certain type of file to automatically run a specific formatting command, auto-fix command, or team-custom script after modification, you can extend this step via the after_change_tools configuration.

## Steps

1. Confirm whether what you want to extend is a "global rule" or a "current-project-specific rule".
2. If it is a global rule, find `after_change_tools.yaml` in your HaijunBot data directory; if it is a project-specific rule, prepare `after_change_tools.yaml` in the current project's `.haijunbot` directory.
3. Write the rules in the form of "file extension or file name -> command list".
4. After saving the configuration, run the code agent once more and let it modify files that match these rules.
5. When this round's flow enters the post-change processing stage, the system automatically reads these configurations and executes the commands you defined for matching files.

## Prompts and Feedback You Will See

- When a command actually matches and executes, the terminal shows that a certain file has been processed, just like ordinary post-processing.
- If project-level and global rules exist at the same time, the rules in the current project take precedence over the global rules.
- If a command in the configuration fails, times out, or the tool does not exist, the terminal shows a corresponding warning.

## Notes

- This kind of configuration is suitable for handling commands you have already confirmed to be stable and repeatedly executable; it is not suitable for writing high-risk temporary scripts that would damage file content.
- Project-level rules only affect the current project and are better suited to team conventions; global rules affect other projects you handle later.
- Commands execute automatically after modification, so before writing the configuration you should first confirm that these commands can run non-interactively and will not mistakenly modify files.
