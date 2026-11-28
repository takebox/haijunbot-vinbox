# Temporarily Switching Model Groups or Tool Groups for the Code Agent

## When to Use

When you want this code task to use different model capabilities, or want to temporarily switch to another set of tool permission scopes, you can temporarily specify a model group or tool group when starting the code agent.

## Steps

1. Open a terminal in the project directory.
2. Enter a command like the following as needed:
   - Switch model group: `hca -g your-model-group-name --task "your task"`
   - Switch tool group: `hca -G your-tool-group-name --task "your task"`
   - Switch both: `hca -g your-model-group-name -G your-tool-group-name --task "your task"`

3. After pressing Enter, the system starts and executes the task according to the group you specified this time.
4. After the task ends, if you want to restore the default settings, simply do not pass these parameters next time.

## Prompts and Feedback You Will See

- This kind of switch usually does not require you to confirm again during the run, but takes effect directly according to this command at startup.
- If you specified a model group or tool group at the same time, the current command uses the value you entered this time in preference, rather than continuing to use the original default settings.
- During subsequent task execution, you see the normal running output corresponding to the current task; the group switch itself does not generate a separate extra result page.

## Notes

- The switch here is a "temporary override at this startup", suitable for adjusting a single task, and is not the same as permanently changing the default configuration.
- This way of writing is only meaningful when the corresponding model group or tool group already exists in the current environment; if the name is misspelled, the task may not run as expected.
- If you also want to control appended tools, rules, or review behavior at the same time, you can write these parameters together in the same command.
