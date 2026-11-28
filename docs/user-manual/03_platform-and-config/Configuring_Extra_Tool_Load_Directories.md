# Configuring Extra Tool Load Directories

## Use Cases

If you have written custom tools, or your team keeps shared tools in a fixed directory and you want HaijunBot to scan these tools at startup as well, you can configure `tool_load_dirs`.

## Steps

1. Prepare your custom tool directory.
2. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
3. Add or modify `tool_load_dirs`. For example:

   ```yaml
   tool_load_dirs:
     - ~/haijunbot-tools
     - /opt/team/haijunbot-tools
   ```

4. Save the config file.
5. Restart the relevant session.
6. At startup, the system scans the directories listed in `tool_load_dirs` in addition to the default sources.

## Prompts and Feedback You Will See

- After the config takes effect, custom tools that did not previously exist appear in the tool system.
- If the directory does not exist or the path is written incorrectly, a common symptom is that the tool you expect does not appear.
- If the directory exists but a particular tool file itself has problems, it usually only causes that tool to fail to load, rather than preventing the entire system from starting.

## Notes

- The config option name is `tool_load_dirs`.
- This is an "extra source" and does not replace the built-in tool sources.
- If you also configure a tool whitelist, blacklist, or tool group, a tool may not be finally available in the current session even if it loads successfully.
- It is recommended to put only the tool files intended for HaijunBot to scan in the directory, to reduce interference from unrelated content.
