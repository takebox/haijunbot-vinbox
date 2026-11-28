# Run the Migration Pipeline

## Use Cases

When you have prepared the C→Rust migration configuration and want to automatically execute the complete pipeline from scanning to transpilation and optimization according to fixed stages, you can use the migration pipeline command.

## Steps

1. First complete the migration configuration, making sure the root symbols, disabled libraries, and additional notes are ready.
2. In the terminal, enter the following command, then press Enter: `hc2r run`
3. Set the model group, maximum retry count, and whether to use interactive mode as needed, for example: `hc2r run --llm-group your-model-group-name --max-retries 3 --interactive`
4. These arguments can also use short forms, for example: `hc2r run -g your-model-group-name -m 3`
5. After submitting the command, the system executes the pipeline stages in a fixed order:

   - scanning
   - library replacement
   - preparation
   - transpilation
   - optimization

5. If part of it has already been executed before, the system automatically skips completed stages based on the state file.
6. Wait for all stages to complete, then check the overall output result and subsequent verification needs.

## Prompts and Feedback You Will See

- At the start of each stage, the system displays the stage being executed.
- Completed stages are recognized and skipped rather than re-executed.
- After each stage ends, it displays the completed or skipped status.
- After the optimization stage is complete, the system outputs a summary, for example the number of files scanned, the cleanup situation, supplementary notes, and the number of checks.
- The pipeline state is written to a local state file for subsequent resumption.
- After all stages are complete, it gives an overall completion prompt.

## Notes

- This is the command-line pipeline entry point and does not re-enter basic configurations such as root symbols at runtime.
- The default value of `--max-retries` is `0`, meaning no limit on the number of retries.
- If you want to re-run from the beginning, you should use the run approach with reset, rather than directly executing a normal run again.
- Breakpoint resumption depends on the state file, so the state file affects how the system judges which stages need to be skipped.
- The optimization stage is marked as completed only after it is judged to be truly done.
