# Extract a Design from Code

## Use Cases

When you face an existing implementation and want to quickly organize it into a "design document" rather than explaining the code line by line, you can use the built-in code reverse-engineering design expert to extract language-agnostic design content from the existing code.

## Steps

1. In the task, clearly tell the system: use the code reverse-engineering design expert.
2. Specify the code scope to be analyzed, which can be a certain module, certain files, or a key implementation.
3. State which aspects you care about more, for example:

   - architecture and modules
   - data flow
   - feature points
   - exception handling
   - external interfaces

4. If you do not know how to phrase the question, you can directly use a description like: `Please use the code reverse-engineering design expert to analyze src/module_a and src/module_b, and organize the result into a Markdown design document, focusing on module responsibilities, key data flows, external interfaces, and exception handling.`
5. If the scope is large, it is recommended to split it into two steps first: "do an overall overview first, then refine by module".
6. After submitting the task, wait for the expert to read the code and extract the design information; if needed, then ask it to split into multiple design documents by feature.

## Prompts and Feedback You Will See

- The output result is usually a structured design document, not line-by-line annotations of the source code.
- The design document covers module responsibilities, interfaces, data flow, and key behaviors.
- The content tries to use language-agnostic expressions, making it easier to continue doing new implementations or cross-language refactoring.
- Common artifacts include: an overall design description, a module breakdown description, and a key flow description.
- If the scope is too large or the goal is unclear, the expert may first ask you to narrow the scope or supplement the goal.

## Notes

- This is an expert-type task entry point, not a fixed CLI command.
- The focus is to distill the "design abstraction", not to translate the existing code sentence by sentence into explanatory prose.
- If you are going to do a re-implementation later, it is recommended to ask the expert to especially emphasize complete feature coverage and boundary conditions.
- When the analysis target is large, splitting the task by module usually makes it easier to get clear results.
- If you do not provide a code scope, the system can usually only give a rather general overall understanding and cannot directly produce a high-quality design document.
