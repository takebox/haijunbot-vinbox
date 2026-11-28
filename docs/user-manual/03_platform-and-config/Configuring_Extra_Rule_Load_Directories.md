# Configuring Extra Rule Load Directories

## Use Cases

If your rule files are not only placed in the HaijunBot default sources but also in a personal directory, a team shared directory, or a project public directory, you can add these directories to the rule load sources via `rules_load_dirs`.

## Steps

1. First prepare the rule directories and make sure their content is the rule files you want HaijunBot to scan.
2. Open the global config file: `~/.haijunbot/config.yaml`.
3. Add or modify `rules_load_dirs`. For example:

   ```yaml
   rules_load_dirs:
     - ~/haijunbot-rules
     - /opt/team/haijunbot-rules
   ```

4. Save the config file.
5. Restart the relevant session so that the system rescans the rule sources.
6. Afterward, these directories participate in rule search and loading as "extra rule sources".

## Prompts and Feedback You Will See

- There is generally no separate "directory added successfully" prompt.
- A more common symptom is: rules that could not be found before can be enumerated, retrieved, or loaded normally after a restart.
- If the directory is written incorrectly, does not exist, or contains no recognizable rule files, the behavior is usually that these rules remain unavailable.

## Notes

- The config option name is `rules_load_dirs`.
- This is an "extra source" and does not replace the default rule sources.
- Using a stable absolute path is recommended; if you use `~`, confirm that the current runtime environment expands it correctly.
- If the same rule name exists in multiple sources, pay special attention to which one you are loading when using it.
