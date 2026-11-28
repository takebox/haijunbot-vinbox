# Configuring the Submit Shortcut for Multiline Input

## Use Cases

If you frequently hit the default submit key by mistake in the terminal's multiline input box, or the current terminal has poor support for the default key combination, you can change the submit shortcut for multiline input via `submit_keys`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Find or add the `submit_keys` config option.
3. This config supports two styles:
   - Array format
   - Comma-separated string format
4. The array format is recommended, example:

   ```yaml
   submit_keys:
     - c-j
     - c-]
   ```

   Or write it as a string:

   ```yaml
   submit_keys: "c-j,c-]"
   ```

5. After saving the config, restart the terminal session.
6. Enter the interface that requires multiline input and try submitting content with the new shortcut you configured.

## Prompts and Feedback You Will See

- After the config takes effect, the multiline input area usually responds according to the new shortcut rules.
- The default values in the Schema are `Ctrl+J`, `Ctrl+]`, and `Ctrl+D`, and their corresponding notations are `c-j`, `c-]`, `c-d`.
- Common usable notations include: `c-j`, `c-]`, `c-enter`.
- If the old shortcut does nothing while the new one can submit, it means the config has taken effect.

## Notes

- The config option name is `submit_keys`.
- Different terminals, tmux, and remote shells do not fully agree on shortcut support, and `c-enter` may not be passed through correctly in some environments.
- If you cannot submit after the change, fall back to a more conservative combination such as `c-j` first.
- In YAML, the array format is clearer and less likely to fail because of a mistaken string separator.
