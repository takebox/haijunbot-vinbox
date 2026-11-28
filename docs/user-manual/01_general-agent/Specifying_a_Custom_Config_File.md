# Specifying a Custom Config File

## When to Use

When you need to temporarily switch to another set of configuration, such as changing the default behavior, loading a different combination of settings, or using a dedicated config under a certain project, you can specify the config file at startup.

## Steps

1. First prepare the config file path.
2. When starting the general agent, use `-f` or `--config` to specify that file.
3. If you also need to load the agent definition, you can additionally use it together with the corresponding startup argument.
4. After a successful start, continue entering tasks as usual or execute tasks directly.

## Prompts and Feedback You Will See

- If the config file path does not exist, the system directly prompts that the config file was not found and falls back to treating it as an empty config.
- If the config file format has a problem, the system prompts that config parsing failed.
- If the startup flow continues, it means the config has been read and applied to the current session.

## Notes

- For the config file path, it is recommended to write an absolute path you can easily confirm, or a clear relative path.
- If you find that the behavior after startup does not match expectations, first check whether you used the wrong config file.
- When config parsing fails, fix the file content first, then restart.
