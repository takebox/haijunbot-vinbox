# Enabling CodeAgent Auto-Restore of Historical Sessions

## Use Cases

If you often re-enter the same project repeatedly and want CodeAgent to automatically try to restore the most recent session on startup to reduce repeatedly entering context, you can configure `auto_resume_session`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify the following config:

   ```yaml
   auto_resume_session: true
   ```

3. Save the config file.
4. Restart CodeAgent.
5. After startup, the system tries to automatically restore the most recent historical session.
6. Observe the startup prompts and confirm whether it successfully restored from some session file.

## Prompts and Feedback You Will See

- If the restore succeeds, you usually see a prompt like "session restored from some session file".
- If there is no restorable session, or the restore fails, the system gives a corresponding warning and then continues into the normal input flow.
- If you explicitly specify a session to restore on the command line, the explicit parameter works together with the auto-restore logic to affect the final behavior.

## Notes

- The config option name is `auto_resume_session`.
- The default behavior is disabled; auto-restore only happens when set to `true`.
- Auto-restore does not guarantee success every time; if the session file is unavailable, the restore fails, or the current environment does not meet the conditions, the system falls back to the normal flow.
