# Verify Functional Alignment

## Use Cases

When you have completed the C→Rust migration and want to further confirm whether the transpiled Rust and the original C remain consistent in interfaces, logic, boundary handling, and error handling, you can run functional alignment verification.

## Steps

1. First complete the migration pipeline, ensuring that a verifiable Rust result has been produced.
2. In the terminal, enter the following command, then press Enter: `hc2r verify`
3. Set the model group, maximum iteration count, and whether to use interactive mode as needed, for example: `hc2r verify --llm-group your-model-group-name --max-iterations 5 --interactive`
4. These arguments can also use short forms, for example: `hc2r verify -g your-model-group-name -i 5`
5. After submitting the command, the system performs an alignment check between the original implementation and the transpiled result.
6. If inconsistencies are found, the system may enter continuous iterative optimization until there are no problems or the maximum iteration count is reached.
7. View the final verification result and use it to decide whether to continue with manual checking or optimize again.

## Prompts and Feedback You Will See

- During the verification, the system outputs the current checking progress.
- The checked content covers interfaces, types, logic, boundary cases, error handling, and memory safety, among other aspects.
- If inconsistencies are found, the system continues into the subsequent optimization and re-verification loop.
- On success, it outputs the verification result; on failure, it displays a clear error prompt and exits.

## Notes

- This step should usually be executed after `run` is complete and is not suitable for running first as the initial step.
- The default value of `--max-iterations` is `10`; you only need to specify it explicitly when you want to stop faster or continue optimizing for longer.
- This is not a simple text comparison but emphasizes alignment at the functional and behavioral level.
- If the project is more complex, the verification process may perform multiple rounds of checking and correction.
- The maximum iteration count affects how far the system is willing to keep optimizing.
