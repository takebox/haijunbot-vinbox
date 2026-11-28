# Starting Conversations by Role Config

## Use Cases

When you have prepared a role configuration file and want the current model to start a conversation according to a fixed role setting, such as product manager, code reviewer, or solution consultant, you can use this role conversation feature.

## Steps

1. First prepare a role configuration file.
2. If you use the default role file location, you can type in the terminal: `hpm role`
3. If your role configuration file is not in the default location, you can instead use a command like: `hpm role --config /your/roles.yaml`; you can also use the short-parameter form: `hpm role -c /your/roles.yaml`. If not specified, the system reads `~/.haijunbot/roles.yaml` by default.
4. If you want this role conversation to temporarily use a different model group, you can include the parameter as well, for example: `hpm role --config /your/roles.yaml --llm-group <your-model-group-name>`
5. After the command starts, the system first reads the role configuration file.
6. If the role file is valid, the system lists the currently selectable roles.
7. Next you can:
   - Directly select a role in the interactive selection list, or
   - Manually enter a role number as prompted
8. After a role is selected, the system prompts the currently selected role and immediately enters the chat state.
9. After entering the chat, continue submitting questions in the input area, and you will converse with the current model according to this role setting.

## Prompts and Feedback You Will See

- If the config file does not exist, you see: `❌ Role configuration file ... does not exist`.
- If the config file exists but its content fails to parse, you see a role configuration file parse failure prompt.
- If the file structure does not meet requirements, you see: `❌ Invalid role configuration file`.
- After loading succeeds, you see: `✅ Available roles`, and a list of roles numbered by index, whose content usually includes the role name and description.
- If you cancel directly in the selection list, or press Enter directly during manual input, the current flow exits and does not enter the chat.
- After a successful selection, you see: `✅ Role selected: <role-name>`.
- Then the system enters the chat flow, and subsequent chat prompts are consistent with the ordinary platform chat mode.
- If you enter an invalid number, you see: `❌ Invalid selection`.

## Notes

- This is a terminal interactive capability, not Web page configuration.
- The default role configuration file location is `~/.haijunbot/roles.yaml`; if you put the file elsewhere, you must explicitly specify the path at startup.
- Role selection supports both an interactive list and a fallback to manually entering a number.
- The system enters the chat only when the role file is valid and you have actually selected a role.
- What you enter after selecting a role is chat mode, so you still need to keep entering content and submitting it before the model starts replying.
