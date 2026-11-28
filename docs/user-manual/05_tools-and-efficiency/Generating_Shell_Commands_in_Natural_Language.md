# Generate Shell Commands in Natural Language

## Use Cases

When you know what you "want to do" but are not sure what Shell command to write, you can directly enter a natural-language sentence and let the system return the corresponding command suggestion.

## Steps

1. If you have already thought through the requirement, you can run directly: `hss request "list all Python files in the current directory"`.
2. This form passes the natural-language requirement directly as an argument, suitable for quickly generating a suggested command.
3. If you do not provide the request content directly after the command, you can also just enter: `hss request`.
4. After running `hss request`, the system prompts you to enter the requirement on the spot; once you finish entering it, it generates the command and continues into the execution confirmation flow.
5. Either way, the system generates the command suggestion based on your description, the current path, and the current shell environment.
6. If you trigger this capability indirectly through the "command not found" handler of certain Shells, whether it executes immediately afterward also depends on the current Shell's interaction mode.

## Prompts and Feedback You Will See

- Under normal circumstances, the result the system returns should contain only the command itself.
- If multiple commands need to be combined, the result usually joins them with `&&`.
- Generation takes into account the current directory and the current shell type, so the same description may yield different commands in different environments.
- If you run `hss request` (without arguments), the system first prompts you to enter the requirement, then generates the command, and continues into the execution confirmation flow.
- If you run `hss request "..."` (with a direct argument), it is more suitable to treat the output as a suggested command to view.
- If you trigger it indirectly from a different Shell's smart handler, the subsequent interaction may appear as backfill, editable, or direct execution.

## Notes

- When passing a natural-language argument directly, it is more suitable to treat the result as a suggested command to view; when running `hss request` without arguments, it enters interactive input and continues through the execution confirmation flow.
- The output goal of this command is to "return the command itself", not an explanation.
- If you use it indirectly through the smart handler of bash, zsh, or fish, their subsequent interaction modes are not exactly the same, so refer to the corresponding Shell documentation.
- If the description is too vague, the generated result may also be too general, so try to state the goal clearly.
