# Configuring the Central Rules Repository

## Use Cases

If your team maintains rules centrally in a shared repository and you want everyone to automatically integrate the same batch of rules, you can configure `central_rules_repo`.

## Steps

1. Prepare the central rules source; either one of the two is fine:
   - Local directory path
   - Remote Git repository URL
2. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
3. Add or modify `central_rules_repo`. For example:

   ```yaml
   central_rules_repo: "https://github.com/your-org/haijunbot-rules.git"
   ```

   Or use a local directory:

   ```yaml
   central_rules_repo: "/opt/team/haijunbot-rules"
   ```

4. Save the config file.
5. Restart the relevant session.
6. If you fill in a local directory, the system uses it directly as the central rules source.
7. If you fill in a remote Git URL, when there is no local cache the system clones it first, then includes it as a rules source; it also performs background update checks afterward.

## Prompts and Feedback You Will See

- When using a remote repository for the first time with no local cache yet, you usually see prompts related to cloning the central rules repository.
- If the clone fails, an error message of the kind "central rules repository clone failed" appears.
- After the config succeeds, you will see rules from the central repository in rule enumeration, loading, or source-distinction scenarios.

## Notes

- The config option name is `central_rules_repo`.
- This value can be either a local directory or a Git repository URL.
- If a remote repository is used, the current environment must be able to access the repository and run `git clone`.
- If the same rule name exists in the central repository and other sources, confirm which one you are actually loading before use.
