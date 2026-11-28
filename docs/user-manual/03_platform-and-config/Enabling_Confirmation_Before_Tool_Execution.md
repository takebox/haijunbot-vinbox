# Enabling Confirmation Before Tool Execution

## Use Cases

If you are worried about the risk of tools executing by mistake and want a manual confirmation before a tool actually runs, you can configure `execute_tool_confirm`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify the following config:

   ```yaml
   execute_tool_confirm: true
   ```

3. Save the config file.
4. Restart the relevant session.
5. In a task that needs to call a tool, observe whether the system first waits for your confirmation before executing.

## Prompts and Feedback You Will See

- After the config takes effect, a confirmation step appears before tool execution instead of executing directly.
- This reduces the risk of mistaken operations and is especially suitable for scenarios involving high-impact operations such as writing files and running commands.
- If you do not see the confirmation step, first check whether the current session re-read the config and whether the current entry point supports this confirmation flow.

## Notes

- The config option name is `execute_tool_confirm`.
- This is a boolean; using `true` or `false` is recommended.
- After enabling confirmation, the interaction cost increases, but safety is higher.
