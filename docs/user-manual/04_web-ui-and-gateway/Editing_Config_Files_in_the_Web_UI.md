# Editing Config Files in the Web UI

## Use Cases

When you do not want to hand-write `~/.haijunbot/config.yaml` but prefer to modify the HaijunBot configuration through a visual form in the Web UI, you can use the "Config File Editing" entry. It generates the form dynamically from the JSON Schema and also provides a plain-text view, so you can switch between the graphical interface and the raw text.

## Steps

1. First make sure you are connected to the Web Gateway and the current account has the `admin:config` permission.
2. Open the "Settings" dialog (via the settings button at the top, or the shortcut `Ctrl+Alt+,`).
3. In the settings dialog, find the "Config File Editing" area and click the "Edit Config File" button.
4. After the dialog opens, it loads two parts automatically:
   - The config Schema (used to generate the form)
   - The current node's config file content
5. At the top of the dialog there are two view tabs; switch as needed:
   - "Form": a field form generated dynamically from the Schema, suitable for editing item by item.
   - "Plain Text": edit the entire config as YAML text, suitable for batch changes or pasting.
6. Modify fields in the "Form" view; if you switch to "Plain Text", the current form content is serialized into YAML.
7. After making changes, click "Save Config".
8. If you want to discard the current changes and reload instead, click "Reload".
9. When done, click "Close" to exit the dialog.

## Feedback You Will See

- When the dialog opens, it briefly shows "Loading config...", then enters the editing interface.
- If loading fails, an error message is shown with a "Retry" button.
- In the "Plain Text" view, a note at the top says: edit the config as plain text (YAML format); on save it is parsed and validated first, and it is not written if validation fails.
- After a successful save, a "Config saved" message appears.
- When saving fails, the dialog shows the specific error:
  - If plain-text parsing fails, the message looks like "Plain text parsing failed: ..." and the file is not written.
  - If the submitted config does not conform to the Schema, it shows "Config does not conform to the Schema and was not written", listing the specific fields and reasons, and the file is not written.
  - If the request fails, the error returned by the backend is shown.
- While saving, the save button changes to "Saving..." and is disabled to prevent repeated submissions.

## Notes

- This entry requires the `admin:config` permission; without it, the message `Permission denied: admin:config` is shown.
- The target of editing is the config file of the currently selected node (default `~/.haijunbot/config.yaml`). Selecting a different node in the settings dialog reads and writes that node's config accordingly.
- The form view only covers the fields declared in the Schema; on save, top-level keys not covered by the Schema are kept to avoid losing extra configuration.
- The plain-text view uses lightweight YAML handling that supports common scalars and nested structures; if you paste more complex YAML (e.g. containing `- item` list entries or inline `{}` / `[]` syntax), parsing may fail. In that case, switch to the form view, or simplify the text and retry.
- Validation against the Schema runs before saving; only config that passes validation is written. Non-conforming config is not written, to avoid the app failing to start due to malformed config.
- The config editing dialog overlays the settings dialog; after closing the config editor you return to the settings interface.
