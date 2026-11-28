# Limiting Available Tools via Tool Whitelist and Blacklist

## Use Cases

If you want a certain type of session to use only a small set of safe tools, or want to block high-risk tools, you can use `tool_group` + `tool_groups` to define a tool whitelist and blacklist.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Define a tool group; within the group you can use:
   - `use`: whitelist, allowing only these tools
   - `dont_use`: blacklist, excluding these tools from the selectable tools
3. For example:

   ```yaml
   tool_group: safe_mode

   tool_groups:
     - safe_mode:
         use:
           - read_code
           - edit_file
           - execute_script
         dont_use:
           - virtual_tty
   ```

4. Save the config file.
5. Restart the session.
6. The system loads tools first, then applies filtering according to the currently activated `tool_group`.
7. If you set `use`, the system first keeps only the tools in the whitelist; then it applies `dont_use` for additional exclusion.

## Prompts and Feedback You Will See

- After it takes effect, you will notice the number of visible or callable tools in the current session changes significantly.
- If `use` contains a nonexistent tool name, the system gives a warning related to the missing tool.
- If `dont_use` contains tools the system must retain, these required tools are still retained and are not actually removed.

## Notes

- The config option names are `tool_group` and `tool_groups` respectively.
- `tool_group` indicates which tool group is currently activated; `tool_groups` is responsible for defining the content of each group.
- Once a group sets `use`, the meaning is "only these tools are allowed", no longer all-enabled by default.
- The blacklist can only exclude selectable tools; it cannot remove required tools that the system forcibly retains.
- If you just want to switch tool sets for different scenarios, it is recommended to define multiple groups rather than frequently editing individual tool names by hand.
