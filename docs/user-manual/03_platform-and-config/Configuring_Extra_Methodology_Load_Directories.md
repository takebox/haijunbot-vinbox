# Configuring Extra Methodology Load Directories

## Use Cases

If, in addition to the default methodology directory, you also want to load methodologies from a personal knowledge base, a team shared directory, or other external directories, you can configure `methodology_dirs`.

## Steps

1. Prepare one or more methodology directories and make sure they contain the methodology files you want HaijunBot to load.
2. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
3. Add or modify `methodology_dirs`. For example:

   ```yaml
   methodology_dirs:
     - ~/haijunbot-methodologies
     - /opt/team/methodologies
   ```

4. Save the config file.
5. Restart the relevant session.
6. Afterward, when loading methodologies, the system includes these directories along with the default directories as sources.
7. Observe whether the total methodology count increases, or whether relevant tasks can hit the methodologies you added.

## Prompts and Feedback You Will See

- When the system loads methodologies, there are usually prompts for load start and load completion.
- If the extra directories exist and their content is valid, the methodology count after loading usually increases.
- If a directory does not exist or is not a valid directory, the system gives a directory-related warning.
- If a file in the directory is corrupted or has an incorrect format, the system prompts that the file failed to load.

## Notes

- The config option name is `methodology_dirs`.
- This is an additional source and does not replace the project-level and global default methodology directories.
- If multiple directories contain methodologies for the same problem type, overriding or coexistence effects may occur afterward; before use, pay attention to whether the result matches expectations.
- After the change, it is recommended to restart the session once to confirm whether the methodology count or behavior change matches expectations.
