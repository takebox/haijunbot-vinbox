# Customizing Git Commit Message Templates

## Use Cases

When you want the commit messages HaijunBot generates to be closer to your team's conventions — for example consistently using Conventional Commits, requiring the module name and risk description to be written clearly, or adding your own commit format guidance — you can configure `git_commit_prompt`.

## Steps

1. Find HaijunBot's global config file; the default location is: `~/.haijunbot/config.yaml`.
2. If you do not want to edit the file by hand, you can also launch the Web config UI:
   - Command: `haijunbot-config web`
   - The default output file is also `~/.haijunbot/config.yaml`
3. Add or modify `git_commit_prompt` in the config file. For example:

   ```yaml
   git_commit_prompt: |
     Generate the commit message in the following format:
     1. The first line uses the Conventional Commits style, e.g. feat:, fix:, refactor:
     2. The affected module must be stated
     3. The body supplements the purpose of the change and potential risks
   ```

4. Save the config file.
5. Re-run the flow that triggers commit-message generation so the system re-reads the config.
6. Compare the newly generated commit message and confirm whether the output style has changed according to your template.

## Prompts and Feedback You Will See

- This config option itself does not pop up a separate "configuration succeeded" window.
- The real feedback appears when a commit message is generated later: the generated result gives priority to the `git_commit_prompt` you wrote.
- If you use `haijunbot-config web`, at startup you usually see:
  - The config Web service started successfully
  - The output file path is `~/.haijunbot/config.yaml`
- If the config file has an incorrect YAML format, later reads of the config may cause the related capabilities to fail to take effect as expected.

## Notes

- What is configured here is a "commit-message generation prompt template", not "automatically committing code directly".
- The config option name is exactly `git_commit_prompt`, not a natural-language description.
- It is recommended to write the format requirements concretely, such as the title format, body structure, and whether a risk description is required; if written too vaguely, the effect is usually unstable.
- If it feels unchanged after the modification, check three things first:
  1. Whether what you changed is `~/.haijunbot/config.yaml`
  2. Whether the YAML indentation is correct
  3. Whether the flow that triggers commit-message generation re-read the config
