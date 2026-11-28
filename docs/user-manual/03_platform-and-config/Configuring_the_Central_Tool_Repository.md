# Configuring the Central Tool Repository

## Use Cases

If your team keeps shared tools centrally in a public repository and you want everyone's HaijunBot to automatically integrate this batch of tools, you can configure `central_tool_repo`.

## Steps

1. Prepare the central tool source; either one of the two is fine:
   - Local directory
   - Remote Git repository URL
2. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
3. Add or modify `central_tool_repo`. For example:

   ```yaml
   central_tool_repo: "https://github.com/your-org/haijunbot-tools.git"
   ```

   Or use a local directory:

   ```yaml
   central_tool_repo: "/opt/team/haijunbot-tools"
   ```

4. Save the config file.
5. Restart the relevant session.
6. If a local directory is configured, the system uses it directly as the central tool source.
7. If a remote Git URL is configured, when there is no local cache the system clones it first, then loads the tools; it also performs background update checks afterward.

## Prompts and Feedback You Will See

- When using a remote repository for the first time with no local cache, the repository is usually cloned first.
- If the clone fails, you see an error prompt such as "central tool repository clone failed".
- After the config succeeds, shared tools you did not previously have appear in the tool sources.

## Notes

- The config option name is `central_tool_repo`.
- This value can be either a local directory or a Git repository URL.
- Even if a tool has loaded successfully, it may still be restricted by filtering rules such as `tool_group`, `use`, `dont_use`, making it unavailable in the current session.
- If you want a unified tool set across the team, it is best to use it together with tool groups, to avoid the misunderstanding of "it's in the repository but not enabled in the current session".
