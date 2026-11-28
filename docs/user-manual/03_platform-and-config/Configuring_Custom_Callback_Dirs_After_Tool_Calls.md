# Configuring Custom Callback Directories After Tool Calls

## Use Cases

If you want to hook in your own post-processing logic after tools finish executing, such as logging extra entries, sending notifications, or doing secondary processing, you can configure custom callback directories via `after_tool_call_cb_dirs`.

## Steps

1. Prepare one or more callback implementation directories.
2. Put your post-tool-call processing logic into these directories.
3. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
4. Add or modify `after_tool_call_cb_dirs`. For example:

   ```yaml
   after_tool_call_cb_dirs:
     - ~/haijunbot-callbacks
     - /opt/team/haijunbot-callbacks
   ```

5. Save the config file.
6. Restart the relevant session.
7. Perform a tool call and observe whether your post-processing logic actually runs.

## Prompts and Feedback You Will See

- This feature usually does not provide a separate "callback loaded successfully" page.
- A more common way to verify is to look at the subsequent effects brought by the callback, such as extra output, extra records, or other post-processing behavior.
- If the directory path is invalid, or the callback implementation itself does not meet requirements, a common symptom is that the post-processing you expect does not happen.

## Notes

- The config option name is `after_tool_call_cb_dirs`.
- This is an extension capability config and is not part of the main flow that ordinary users must operate daily.
- If you put multiple sets of logic in the directory, when troubleshooting the effect later, be careful to distinguish exactly which set is taking effect.
- It is recommended to first verify with a simple callback, then gradually add more complex post-processing logic.
