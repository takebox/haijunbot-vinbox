# Switching Model Groups

## When to Use

When you want to switch between speed, cost, and effectiveness, for example first using a lighter model for ordinary tasks and then switching to a stronger model for complex tasks, you can switch model groups.

## Steps

### Method 1: Specify at startup

1. When starting the general agent, use `-g` or `--llm-group` in the command to specify the model group.
2. After submitting the command, the system enters the current session according to the model group you specified.

### Method 2: Switch during the session

1. Enter `'<SwitchModel>'` in the current conversation input box.
2. Press `Ctrl+J` or `Ctrl+]` to submit.
3. The system pops up a model group selection flow; you select the target model group as prompted.
4. After a successful selection, continue executing the current task.

## Prompts and Feedback You Will See

- The welcome message at startup includes the platform and model information currently in use.
- When the switch succeeds within the session, the system prompts: `✅ Model group switched successfully.`
- If you cancel the switch or the switch fails, the system prompts: `❌ Model group switch failed or was cancelled.`
- If the current entry point does not support the model group switch command, you will first see an unavailable prompt, rather than directly entering the selection.

## Notes

- Specifying at startup is suitable for scenarios where the model strategy is determined before the task begins.
- Switching during the session is more suitable when the task is halfway done and you temporarily want to adjust the model capability.
- When the switch fails, first check whether the current session supports this operation and whether the target model group is available.
