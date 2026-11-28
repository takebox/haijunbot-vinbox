# Script Usage Instructions and Testing Methods

## Use Cases

When you want to not only deliver the script itself but also let users know how to run it, how to fill in arguments, how to test it, and how to troubleshoot errors, you should ask for the script generation result to come with complete explanatory material.

## Steps

1. When generating the script task, explicitly require the output to include at the same time:

   - usage instructions
   - argument descriptions
   - invocation examples
   - testing methods

2. If there are key code sections, also ask the system to explain the role of these parts.
3. If you want to directly describe the complete requirements, you can use a task like: `After generating the script, please also add a usage guide that includes argument descriptions, invocation examples, normal-path testing methods, and error-path testing methods.`
4. If it is to be delivered to a team, then ask for it to be organized into accompanying documentation suitable for sharing.
5. After generation is complete, first actually execute it once according to the invocation example in the instructions, then verify the script's main paths and error-handling paths according to the testing methods.

## Prompts and Feedback You Will See

- The final delivery is not just a script file but also comes with explanatory material.
- The instructions usually cover:

  - the purpose of arguments
  - typical invocation methods
  - testing steps
  - common errors and how to handle them

- If you request delivery documentation, the system usually organizes this content to be more suitable for reading and sharing.

## Notes

- This is an accompanying output requirement of the script generation expert, not a standalone independent CLI command.
- The rules explicitly require that you cannot deliver only the script without the instructions.
- If the script will later be used by others, this part of the documentation is especially important.
- The testing methods should cover both normal paths and error paths, to avoid only proving "the script can run" without verifying exception handling.
- If the script needs external dependencies, configuration files, or permissions, it is best to also ask the system to include these preconditions in the explanatory material.
