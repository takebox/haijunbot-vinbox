# Managing LLM Configuration

## Use Cases

When you have prepared the connection information for a model platform and want to save, view, modify, or delete an LLM configuration in HaijunBot, you can use the platform manager's LLM config commands. The saved configuration can continue to be referenced by model groups.

## Steps

### View the LLM configuration list

1. Type in the terminal: `hpm manage llm list`
2. After pressing Enter, the system directly lists the existing LLM configurations.
3. In the list you can see the name of each configuration and its currently corresponding platform and model.

### View a single LLM configuration's details

#### Option 1: Include the config name directly in the command

1. Type in the terminal: `hpm manage llm show <your-config-name>`
2. After pressing Enter, if the name exists, the system directly shows the details of this configuration.
3. You will see this configuration's:
   - Platform
   - Model
   - Maximum token count
   - Other connection parameters

#### Option 2: Open the interactive selection list first, then choose

1. Type in the terminal: `hpm manage llm show`
2. After pressing Enter, the system pops up a selection list with a prompt like: `Select LLM configuration > `.
3. After you select the target configuration in the list and confirm, the system shows that configuration's details.
4. If you cancel directly on the selection screen, this view ends immediately and does not continue.

### Add an LLM configuration

1. Type in the terminal: `hpm manage llm add <your-config-name>`
2. After pressing Enter, the system first displays: `📝 Add LLM configuration: <your-config-name>`
3. Next, enter the following in order as prompted, pressing Enter after each item to continue:
   - `Platform name (openai/haijun/other): `
   - `Model name (e.g.: gpt-4o): `
   - `Max token count (default: 200000): `
   - `API base URL: `
   - `API key: `
4. If you press Enter directly at the "max token count" step, the system automatically uses the default value `200000`.
5. After all input is complete, the system saves this configuration immediately.
6. After saving successfully, you will see: `✅ Added LLM configuration: <your-config-name>`

### Update an LLM configuration

#### Option 1: Directly specify the configuration to modify

1. Type in the terminal: `hpm manage llm update <your-config-name>`
2. After pressing Enter, the system first shows a summary of the current configuration, such as the current platform and model.
3. Then the system asks for new values item by item:
   - `Platform name (current: ..., leave blank to keep): `
   - `Model name (current: ..., leave blank to keep): `
   - `Max token count (current: ..., leave blank to keep): `
4. When you only want to change one item, enter just that item's new value; for the rest, just press Enter.
5. After everything is done, the system saves the modification result.
6. After saving successfully, you will see: `✅ Updated LLM configuration: <your-config-name>`

#### Option 2: Select first, then update

1. Type in the terminal: `hpm manage llm update`
2. After pressing Enter, the system pops up a selection list with a prompt like: `Select the LLM configuration to update > `.
3. After selecting the target configuration, the system enters the same item-by-item update flow as above.
4. If you cancel directly on the selection screen, this update ends immediately.

### Delete an LLM configuration

#### Option 1: Directly specify the configuration to delete

1. Type in the terminal: `hpm manage llm delete <your-config-name>`
2. After pressing Enter, if this configuration is currently referenced by a model group, the system first gives a warning.
3. Then the system asks you to confirm the deletion, with a prompt like: `Confirm deleting LLM configuration '<your-config-name>'?`
4. Only after you explicitly confirm does the system actually delete this configuration.
5. After deleting successfully, you will see: `✅ Deleted LLM configuration: <your-config-name>`

#### Option 2: Select first, then delete

1. Type in the terminal: `hpm manage llm delete`
2. After pressing Enter, the system pops up a selection list with a prompt like: `Select the LLM configuration to delete > `.
3. After selecting the target configuration, the system proceeds to the confirm-deletion step.
4. If you cancel directly on the selection screen, this deletion ends immediately and nothing is deleted.

## Prompts and Feedback You Will See

- When viewing the list, you will see something like: `✅ LLM configuration list:`, followed by each configuration's `name (platform/model)`.
- When viewing details succeeds, you will see something like:
  - `✅ LLM configuration: <config-name>`
  - `Platform: ...`
  - `Model: ...`
  - `Max token count: ...`
  - `Other configuration:`
- When adding starts, the system prompts: `📝 Add LLM configuration: <config-name>`.
- When updating starts, the system prompts: `📝 Update LLM configuration: <config-name>`, then shows the current platform and model.
- After adding successfully, it prompts: `✅ Added LLM configuration: <config-name>`.
- After updating successfully, it prompts: `✅ Updated LLM configuration: <config-name>`.
- After deleting successfully, it prompts: `✅ Deleted LLM configuration: <config-name>`.
- If a nonexistent config name is entered, the system prompts: `❌ LLM configuration not found: ...`.
- If the config name already exists when adding, the system prompts: `❌ LLM configuration '...' already exists`.
- If you leave the platform name, model name, API base URL, or API key blank, the system immediately prompts that the corresponding field cannot be empty and ends this addition.
- If the token count input is not a valid number:
  - When adding, it prompts: `❌ Invalid token count, using default value 200000`
  - When updating, it prompts: `❌ Invalid token count, keeping the original value`
- If you cancel directly on the interactive selection list, the current operation ends immediately.

## Notes

- These commands all need to be run in a terminal.
- `list` is a command that outputs results directly; `show`, `update`, and `delete` enter interactive selection when no name is given.
- The add command must include the configuration name directly in the command, for example: `hpm manage llm add my-openai`.
- When updating, "leave blank to keep" means retaining the original value, not clearing that field.
- Before deleting, it is best to first confirm whether this configuration is still used by a model group; otherwise it may affect existing model groups.
- What is managed here is persistently saved LLM configuration, which is not the same as temporarily switching the model group used by the current session.
