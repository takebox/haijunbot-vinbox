# Managing Model Groups and Setting the Current Default Group

## Use Cases

When you want to combine multiple LLM configurations into a fixed strategy — for example binding normal scenarios, complex tasks, and low-cost scenarios to different models respectively — or want to switch the model group HaijunBot uses by default afterward, you can use the model group management feature.

## Steps

### View the model group list

1. In the terminal, enter the platform management command and open model group management.
2. After performing the view-list operation, the system lists the existing model groups.
3. The list shows each model group's name and its current Normal configuration reference.

### View model group details

1. Enter the view-model-group-details operation.
2. If you do not directly pass in the model group name, the system first pops up an interactive selection list.
3. After selecting, the system shows what this model group currently references:
   - `normal_llm`
   - `cheap_llm`
   - `smart_llm`

### Add a model group

1. Enter the add-model-group operation and first give the model group a name.
2. The system first lists all currently available LLM configuration names for your reference.
3. Then enter as prompted:
   - Normal LLM configuration name (required)
   - Cheap LLM configuration name (optional)
   - Smart LLM configuration name (optional)
4. If Cheap or Smart is left blank, the system treats it as "the same as Normal".
5. After input is complete, the system writes this model group into the config file.

### Update a model group

1. Enter the update operation.
2. If you do not directly specify the model group name, the system first lets you choose one from the existing model groups.
3. After selecting, the system shows the current Normal / Cheap / Smart values and lists the available LLM configuration names again.
4. You can modify just some of them; for the ones you do not want to change, just leave them blank.
5. After submitting, the system saves the update result.

### Delete a model group

1. Enter the delete operation.
2. If you do not directly specify the model group name, the system first enters interactive selection.
3. The system asks you to confirm the deletion.
4. Only after you explicitly confirm does the deletion actually execute.

### Set the current default model group

1. Enter the set-default-model-group operation.
2. If you do not directly specify the model group name, the system first lets you choose one from the existing model groups.
3. After selection, the system writes this model group into the current default config.
4. From then on, related features that do not explicitly override the model group use it by default.

## Prompts and Feedback You Will See

- When viewing the list, you will see something like: `✅ Model group list:`, followed by each group's `name (normal: ...)`.
- When viewing details, you will see something like:
  - `✅ Model group: <group-name>`
  - `normal_llm: ...`
  - `cheap_llm: ...`
  - `smart_llm: ...`
- When adding starts, the system prompts: `📝 Add model group: <group-name>`, then lists the available LLM configurations.
- If you enter a nonexistent LLM configuration name, the system immediately prompts: `❌ LLM configuration not found: ...` and ends this save.
- After adding successfully, it prompts: `✅ Added model group: <group-name>`.
- When updating starts, it prompts: `📝 Update model group: <group-name>` and shows the current values.
- After updating successfully, it prompts: `✅ Updated model group: <group-name>`.
- A confirmation step appears before deletion; if you cancel, the current deletion flow ends directly.
- After deleting successfully, it prompts: `✅ Deleted model group: <group-name>`.
- After setting the default group successfully, it prompts: `✅ Set current model group: <group-name>`.

## Notes

- Before creating a model group, there must be available LLM configurations; if there are currently none, the system will not let you continue adding a model group.
- When adding or updating a model group, the configuration name entered must be a genuinely existing LLM configuration name.
- When updating, leaving blank means keeping the original value, not clearing the current field.
- Setting the current default model group is a persistent config and affects the model selection at subsequent default startups.
- What is set here is the "default model group"; if a particular command passes in an extra model group parameter, that run still goes by the temporarily passed-in value.
