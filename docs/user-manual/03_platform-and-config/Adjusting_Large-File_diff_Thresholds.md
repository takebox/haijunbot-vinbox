# Adjusting the Display Threshold for Large-File Diffs

## Use Cases

If your project frequently modifies large files and you want to know at what scale the diff switches to a summary display instead of a full preview, pay attention to the large-file threshold behavior. Based on the current source code behavior, this threshold defaults to 300 lines.

## Steps

1. In a large-file modification scenario, observe whether the diff has already switched from a full preview to a more simplified display.
2. In the current source code, the large-file threshold returns `300` by default.
3. When the scale of the file change exceeds this threshold, the system tends to show only statistics or summary information rather than the full content.

## Prompts and Feedback You Will See

- For small changes, you can usually see a more complete diff.
- After exceeding the threshold, you are more likely to see a summarized or statistical display.
- The purpose of this is to avoid outputting overly long content in large-file scenarios, which would hurt readability and performance.

## Notes

- What the current source code reflects is the default threshold behavior; it should not be written as a capability that "is already stably open for users to modify arbitrarily via config.yaml" unless a config option is explicitly exposed later.
- If you need fine-grained control over this threshold, watch for whether a formal config entry is provided later.
