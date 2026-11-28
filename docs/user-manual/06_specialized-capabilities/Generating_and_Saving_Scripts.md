# Generate and Save a Script

## Use Cases

When you have already clarified what task you want to automate and want HaijunBot to generate, based on your requirements, runtime environment, and input/output requirements, a complete executable script saved to a specified location, you can use the built-in script generation expert.

## Steps

1. In the task, clearly tell the system: use the script generation expert.
2. Describe your script goal, including:

   - the problem to be solved
   - the runtime environment
   - the input/output method
   - where you want it saved

3. If needed, then state your preferred scripting language or constraints.
4. If you want to give a complete instruction directly, you can use a task like: `Please use the script generation expert to generate a Bash script for a Linux environment to batch-back-up files from the last 7 days under the logs directory, save it to scripts/backup_logs.sh, and also add usage instructions.`
5. After submitting the task, wait for the system to choose a suitable language and design the script structure.
6. Let the system write the complete script to the specified file and provide the necessary explanation at the same time; after generation, run it once yourself to verify whether the script meets expectations.

## Prompts and Feedback You Will See

- If the requirements are unclear, the system usually asks you clarifying questions first.
- After the script generation is complete, you get:

  - the script file
  - key explanations or a summary

- The output result tries to ensure the script is complete and runnable, rather than giving only fragments.
- If you provided a save path, the system saves it to the target location as required.

## Notes

- This is an expert-type task entry point, not a fixed CLI subcommand.
- The more specific the script goal, the more likely the generation result is to be right the first time.
- The rules emphasize that the script should be executable and maintainable and include the necessary error handling.
- After generation, it is still recommended that you do a minimal verification in a real environment to confirm the input/output and permissions meet expectations.
- It is best to state the save path, the runtime environment, and whether overwriting existing files is allowed at the same time; otherwise the system may need to ask about these preconditions first.
