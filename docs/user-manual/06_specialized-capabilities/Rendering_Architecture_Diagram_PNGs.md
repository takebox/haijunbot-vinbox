# Render Architecture Diagram PNGs

## Use Cases

When you already have a Graphviz DOT architecture diagram and want to further render it into a PNG image for easy insertion into documents, sharing with the team, or direct viewing, you can continue by having the architecture diagram expert complete the rendering step.

## Steps

1. First make sure the `.dot` architecture diagram file has already been generated.
2. In the task, ask the system to render that DOT file into a PNG image.
3. If you want to directly describe the task, you can use an expression like: `Please render docs/arch/system.dot into a PNG, output it to docs/arch/system.png, and tell me the final file path.`
4. Confirm that the Graphviz `dot` command is available in the current environment.
5. After submitting the task, wait for the system to call `dot` to complete the rendering; after the rendering is complete, check the path of the generated `.png` file.

## Prompts and Feedback You Will See

- After a successful render, the system reports the save path of the PNG image.
- In the end it usually keeps both:

  - the `.dot` source file
  - the `.png` image file

- If the rendering fails, there are usually error prompts related to the Graphviz environment.

## Notes

- This is a step that continues processing based on an already generated DOT diagram, not generating an architecture diagram from scratch.
- The premise is that the `dot` command is available in the local environment.
- If the rendering fails, first check whether Graphviz is installed completely and whether the command is executable.
- PNG is the presentation artifact; it is still recommended to keep the source DOT file as well, for later adjustments and re-rendering.
- It is best to state both the input DOT path and the expected output PNG path in the task, so the system does not need to repeatedly confirm the file locations.
