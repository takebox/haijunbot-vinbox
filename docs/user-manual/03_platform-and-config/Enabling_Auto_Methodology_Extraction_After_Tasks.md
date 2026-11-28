# Enabling Auto Methodology Extraction After Tasks

## Use Cases

If you want the system to automatically distill reusable experience from the execution process after a task ends and save it as a methodology usable later, you can enable `auto_methodology_extraction`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify the following config:

   ```yaml
   auto_methodology_extraction: true
   ```

3. Save the config file.
4. Restart the relevant session.
5. Complete a representative task.
6. Then check whether methodology-related content is added, or observe whether the count changes when methodologies are loaded later.

## Prompts and Feedback You Will See

- After it is enabled, when a task completes the system tries to automatically extract a methodology and save it.
- If the extraction succeeds, new entries may appear when methodologies are loaded later.
- If no valid content is extracted, there may be no obvious new result.

## Notes

- The config option name is `auto_methodology_extraction`.
- The default behavior is disabled; it is only enabled when set to `true`.
- This feature is suitable for accumulating long-term reusable experience and is not suitable for saving every one-off temporary conclusion as a methodology.
