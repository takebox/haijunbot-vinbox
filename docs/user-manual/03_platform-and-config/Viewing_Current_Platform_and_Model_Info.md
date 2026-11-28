# Viewing Current Platform and Model Info

## Use Cases

When you want to confirm which platform and which model HaijunBot uses by default now, or want to check whether the platform and candidate model list corresponding to a certain model group are normal, you can use this view feature.

## Steps

### View the platform and model for the default configuration

1. Type the following command in the terminal, then press Enter: `hpm info`
2. If you do not specify an extra model group, the system directly reads the configuration corresponding to the current default model group.
3. After submitting, the system first shows the current default platform and default model.
4. Then the system continues by trying to read the model list details for this platform.
5. If the read succeeds, you can then see the list or description of available models under that platform.

### View the platform and model for a specified model group

1. Type a command like this in the terminal: `hpm info --llm-group <your-model-group-name>`
2. You can also use the short-parameter form: `hpm info -g <your-model-group-name>`
3. After submitting, the system gives priority to the model group you passed in this time rather than continuing with the original default group.
4. The system first displays the "configuration information obtained from the model group", then shows the platform and model currently used by this model group.
5. Then the system continues by trying to read the model list details for this platform.

## Prompts and Feedback You Will See

- When no model group is specified, you see something like:
  - `✅ Default configuration information:`
  - `Platform: ...`
  - `Model: ...`
- When a model group is specified, you see something like:
  - `✅ Configuration information obtained from model group '...':`
  - `Platform: ...`
  - `Model: ...`
- If the platform details are read successfully, you also see something like:
  - `✅ <platform> details`
  - `• <model-name> - description`
- If creating the platform instance fails, the current configuration is incomplete, or the platform does not return a model list, you see a warning prompt instead of full details.
- If there is currently no available platform, it also directly displays a warning and ends.

## Notes

- This feature only views the configuration that currently takes effect and does not modify any config file.
- If you temporarily specify a model group in the command, this view result goes by the model group passed in this time.
- Whether you can successfully see the model list depends on whether the current platform supports providing a model list, and whether the current configuration is sufficient for the platform instance to be created normally.
- This is a terminal view capability; it does not open a browser and does not enter the chat.
