# Enabling Smart Enhancement Capabilities

## Use Cases

If you want the system to be more proactive in ambiguity handling, proactive interaction, conversation management, and similar areas, you can configure `enable_autonomous`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify the following config:

   ```yaml
   enable_autonomous: true
   ```

3. Save the config file.
4. Restart the relevant session.
5. In a task that is ambiguous, needs clarification, or needs the system to proactively help manage the conversation, observe whether the system behaves more proactively.

## Prompts and Feedback You Will See

- After it is enabled, the system is more proactive in emotion recognition, ambiguity detection, conversation management, and proactive interaction.
- If it is disabled or not configured, the system keeps its default more conservative behavior.
- Such changes usually show in the conversation process itself rather than a separate "smart enhancement enabled" prompt.

## Notes

- The config option name is `enable_autonomous`.
- The default value is `false`.
- This capability is more suitable for scenarios that need more proactive assistance; if you prefer a completely simple, low-intervention interaction, you can keep it disabled.
