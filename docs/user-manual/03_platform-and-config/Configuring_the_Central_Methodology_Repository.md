# Configuring the Central Methodology Repository

## Use Cases

If your team maintains commonly used methodologies centrally in a shared repository and you want everyone's HaijunBot to automatically integrate this batch of content, you can configure `central_methodology_repo`.

## Steps

1. Prepare the central methodology source; either one of the two is fine:
   - Local directory
   - Remote Git repository URL
2. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
3. Add or modify `central_methodology_repo`. For example:

   ```yaml
   central_methodology_repo: "https://github.com/your-org/haijunbot-methodologies.git"
   ```

   Or write it as a local directory:

   ```yaml
   central_methodology_repo: "/opt/team/haijunbot-methodologies"
   ```

4. Save the config file.
5. Restart the relevant session.
6. If a local directory is configured, the system uses it directly as the central methodology source.
7. If a remote Git URL is configured, when there is no local cache the system clones it first, then includes it as a methodology source; it also performs background update checks afterward.

## Prompts and Feedback You Will See

- When using a remote repository for the first time with no local cache, you usually see prompts related to cloning the central methodology repository.
- If the clone fails, you see an error message of the kind "central methodology repository clone failed".
- After loading completes, the total methodology count usually increases.
- If the central directory is inaccessible or there are file format problems, you also see warnings or failure prompts during the loading phase.

## Notes

- The config option name is `central_methodology_repo`.
- This value can be either a local directory or a Git repository URL.
- If a remote repository is used, the current environment must have the ability to access the repository and run Git.
- The central methodology is only one of the sources; it does not mean every methodology is automatically adopted in full in every task, and it still goes through relevance filtering afterward.
