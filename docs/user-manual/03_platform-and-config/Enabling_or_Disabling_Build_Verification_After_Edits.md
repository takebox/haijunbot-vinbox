# Enabling or Disabling Build Verification After Edits

## Use Cases

If you want build verification to run automatically after code changes so that obvious errors are found early, you need to understand the current build verification behavior. Based on the current source code behavior, build verification is enabled by default.

## Steps

1. First confirm whether your project is suitable for running build verification in the current environment.
2. In the current source code, build verification returns an enabled state by default.
3. If, when using the existing CLI/run flow, you find that certain special environments choose to skip build verification, go by the actual behavior of that run's entry point.
4. After modifying code, observe whether the system automatically performs the build verification step.

## Prompts and Feedback You Will See

- In scenarios that support this flow, build verification runs automatically after code changes.
- If the current runtime environment or entry point disables this step, it may only perform basic static checks or skip it entirely.
- When build verification fails, it usually shows up in subsequent feedback rather than being silently ignored.

## Notes

- Based on the current `config.py` behavior, this is not a document describing a stable toggleable capability already exposed as an independent config key, but rather a "description of current default behavior".
- When writing documentation, do not describe it as a capability that "users can already toggle arbitrarily via config.yaml" unless the later source code explicitly provides the corresponding config option.
- If you need to stably control whether build verification runs, give priority to the specific entry parameters or run mode you are using, rather than only looking at the config file.
