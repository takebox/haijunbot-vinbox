# Configuring Extra Agent Definition Directories

## Use Cases

If you want HaijunBot to recognize Agent definition files you maintain yourself in addition to the default Agent definitions, you can add extra search directories via `agent_definition_dirs`.

## Steps

1. Prepare one or more Agent definition directories.
2. Put the Agent definition files you want to be recognized into these directories.
3. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
4. Add or modify `agent_definition_dirs`. For example:

   ```yaml
   agent_definition_dirs:
     - ~/haijunbot-agents
     - /opt/team/haijunbot-agents
   ```

5. Save the config file.
6. Restart the relevant session or entry point.
7. Afterward, when the system discovers Agent definitions, it includes these directories in the search scope as well.

## Prompts and Feedback You Will See

- After the config takes effect, custom Agents you could not previously see may appear in the subsequent selectable Agent sources.
- If the directory path is invalid, or the definition files in the directory do not meet requirements, you will not see the expected new Agent.
- A more direct way to verify is to confirm in the startup selection or Agent-related entry point whether the new definition appears.

## Notes

- The config option name is `agent_definition_dirs`.
- This is an extended search directory, not a replacement for the default Agent definition sources.
- The directory should only contain the Agent definition content you want the system to scan, to avoid mixing in unrelated files.
- After the change, it is recommended to restart the corresponding entry point to confirm the new directory has indeed been included in the scan.
