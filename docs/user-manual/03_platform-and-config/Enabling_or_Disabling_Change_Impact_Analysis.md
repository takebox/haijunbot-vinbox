# Enabling or Disabling Code Change Impact Analysis

## Use Cases

If you want the system to automatically determine which locations a change may affect after code modifications, you need to understand the current impact analysis behavior. Based on the current source code behavior, impact analysis is enabled by default.

## Steps

1. When carrying out a code modification task, observe whether the system outputs an impact scope analysis result after editing.
2. In the current source code, impact analysis returns an enabled state by default.
3. If your actual run entry point applies extra control to this step, go by the real behavior of that run's entry point.

## Prompts and Feedback You Will See

- In the relevant flow, an impact scope analysis report usually appears after editing completes.
- If the run entry point skips this step, you may see only the edit result itself without the impact analysis conclusion.
- Impact analysis is usually used to help you judge whether related files still need additional testing or checking.

## Notes

- Based on the current `config.py` behavior, this is likewise closer to a "default behavior description" rather than an independent config switch already explicitly exposed to users.
- The documentation should not over-promise that "you can definitely turn it off freely via some config key now" unless the later source code explicitly provides that config option.
- If you need to stably control whether this step runs, judge it together with the specific entry point and the task run mode.
