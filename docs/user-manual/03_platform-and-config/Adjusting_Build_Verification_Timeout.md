# Adjusting the Build Verification Timeout

## Use Cases

If your project takes a long time to build and the default timeout is not enough, or if you want build verification to fail faster, you can adjust `build_validation_timeout`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify the following config, for example to 120 seconds:

   ```yaml
   build_validation_timeout: 120
   ```

3. Save the config file.
4. Restart the relevant session.
5. Trigger a code modification flow that performs build verification.
6. Observe whether build verification runs according to the new timeout.

## Prompts and Feedback You Will See

- If the build completes within the timeout, the verification result is returned normally.
- If it exceeds the time you set, the system terminates verification and reports a timeout.
- If not configured, the default timeout is 30 seconds.

## Notes

- The config option name is `build_validation_timeout`.
- This is a numeric config option and its unit is seconds.
- Setting it too short causes builds that could otherwise finish to time out frequently; setting it too long slows down feedback.
