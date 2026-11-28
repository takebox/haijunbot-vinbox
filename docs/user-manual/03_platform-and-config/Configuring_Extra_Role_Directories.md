# Configuring Extra Role Directories

## Use Cases

If you want the system to discover more role settings from other directories in addition to the default role sources, you can extend the role search scope via `roles_dirs`.

## Steps

1. Prepare the extra role directories and put the role setting content into them.
2. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
3. Add or modify `roles_dirs`. For example:

   ```yaml
   roles_dirs:
     - ~/haijunbot-roles
     - /opt/team/haijunbot-roles
   ```

4. Save the config file.
5. Restart the relevant session.
6. Afterward, when searching for role sources, the system includes these directories in the search scope as well.
7. Go to the role-related entry point to confirm whether these newly added roles are already visible.

## Prompts and Feedback You Will See

- After the config takes effect, role content that is not in the default location has a better chance of being recognized by the system.
- If the directory path is written incorrectly, or there is no valid role content in the directory, a common symptom is that you still cannot find the role you thought you had configured.
- If you explicitly specify a role file in a specific command, that run gives priority to the explicitly specified file.

## Notes

- The config option name is `roles_dirs`.
- This is a config for extending role sources and is not the same as "directly specifying a role file path in a particular command".
- Roles reused long-term are recommended to be placed in a stable directory, to avoid being hard to troubleshoot after a temporary directory becomes invalid.
- After the change, it is best to re-enter the relevant entry point to confirm whether the role is really discovered, rather than just looking at the config file itself.
