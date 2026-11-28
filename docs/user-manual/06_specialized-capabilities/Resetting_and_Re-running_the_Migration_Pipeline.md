# Reset and Re-run the Migration Pipeline

## Use Cases

When you have already run the C→Rust migration pipeline once but want to clear the existing stage progress and start a full execution again from the scanning stage, you can use the reset-and-re-run approach.

## Steps

1. In the terminal, enter the following command, then press Enter: `hc2r run --reset`
2. If you also want to specify a model group, maximum retry count, or interactive mode at the same time, you can combine them, for example: `hc2r run --reset --llm-group your-model-group-name --max-retries 3 --interactive`
3. These arguments can also use short forms, for example: `hc2r run --reset -g your-model-group-name -m 3`
4. After the state is cleared, the pipeline starts execution again from the scanning stage.
5. Wait for the scanning, library replacement, preparation, transpilation, and optimization stages to complete in order according to the normal flow.
6. After the re-run is complete, decide whether to continue with functional alignment verification based on the result.

## Prompts and Feedback You Will See

- During the reset, the system deletes the old stage state records.
- In the subsequent execution, previously completed stages are no longer treated as skippable stages.
- You see the entire pipeline outputting the status of each stage again from the beginning.
- After it finally completes, a new overall completion prompt is given again.

## Notes

- What is reset is the pipeline progress state; it is not the same as automatically restoring the code, files, or external artifacts you generated previously.
- If you only want to continue an unfinished flow, you do not need to add the reset option; a normal `hc2r run` performs breakpoint resumption according to the state file.
- Before re-running, it is best to confirm the current workspace and migration artifact state to avoid mixing old results with the new flow.
- This is the entry point for a complete re-execution of the flow, not just "re-execute the failed stages".
