# Viewing Available Resource Stats at Startup

## Use Cases

If you want to quickly confirm whether the current environment has correctly loaded methodologies, tools, and memory, you can pay attention to the resource stats panel displayed when the Agent starts.

## Steps

1. Start the corresponding Agent.
2. After startup completes, observe the welcome message and the resource stats panel.
3. Focus on the following:
   - Current platform and model
   - Local methodology count
   - Available tool count
   - Global memory count
   - Project memory count (if present)
   - Short-term memory count (if present)
4. If you have just modified the methodology directory, tool directory, or memory-related config, you can use the count changes here as a quick verification.

## Prompts and Feedback You Will See

- At startup a resource overview is displayed to help you understand the scale of resources loaded in the current environment.
- If project memory or short-term memory exists, they are displayed additionally in the stats.
- This is a very suitable entry point for quickly double-checking "whether the config took effect".

## Notes

- This is automatic feedback at startup, not an independent feature entry that requires configuring some key to see.
- If you find the counts do not match expectations, check back whether the corresponding directory, config source, or filtering rules are correct.
