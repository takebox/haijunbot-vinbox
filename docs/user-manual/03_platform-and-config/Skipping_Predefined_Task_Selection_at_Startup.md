# Skipping Predefined Task Selection at Startup

## Use Cases

If you do not want the Agent to enter the predefined task selection step first at startup but instead to go directly to the flow for manually entering requirements, you can configure `skip_predefined_tasks`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify the following config:

   ```yaml
   skip_predefined_tasks: true
   ```

3. Save the config file.
4. Restart the corresponding Agent entry point.
5. After startup, observe whether it goes directly to manual requirement input rather than showing predefined task selection first.

## Prompts and Feedback You Will See

- After the config takes effect, the startup flow is more direct and no longer stops at the predefined task selection step.
- If you set it to `false` or do not configure it, the system decides whether to load predefined tasks according to the default behavior.
- If it looks unchanged after the modification, first check whether the current entry point re-read the config.

## Notes

- The config option name is `skip_predefined_tasks`.
- This is a boolean; it should be written as `true` or `false`, not as a string.
- This config only affects "whether to skip predefined task loading" and does not affect your ability to manually enter tasks afterward.
