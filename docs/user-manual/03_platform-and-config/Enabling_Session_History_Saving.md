# Enabling Session History Saving

## Use Cases

If you want to retain the model session history for later tracing, restoring, or continuing context, you can configure `save_session_history`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify the following config:

   ```yaml
   save_session_history: true
   ```

3. Save the config file.
4. Restart the relevant session.
5. Carry out a conversation or task execution.
6. Then check whether the session history has been saved, and use it for later restore or tracing when needed.

## Prompts and Feedback You Will See

- After it is enabled, the session process is saved for later viewing or restoring.
- If it is not enabled, session history is not saved by default.
- The related effect usually shows in later restorability and traceability rather than an immediate separate prompt.

## Notes

- The config option name is `save_session_history`.
- The default value is `false`.
- If your session involves sensitive information, before enabling it first confirm whether the local save policy meets your security requirements.
