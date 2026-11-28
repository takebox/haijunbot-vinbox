# Generate Project-Level Reverse-Engineering Docs

## Use Cases

When you want to perform systematic reverse engineering on the entire project and obtain a module inventory, dependency relationships, data flow, control flow, and overall architecture documentation, you can start a project-level analysis task through the reverse-engineering rule.

## Steps

1. In the task, clearly state: what you want to do is "project-level reverse engineering", not an explanation of a single code segment.
2. Specify the project root directory or the scope to be analyzed.
3. Ask for the output to cover:

   - module division
   - dependency relationships
   - data flow and control flow
   - key functional paths
   - language-agnostic design expressions

4. If you want to directly give a complete description, you can use a task like: `Please perform project-level reverse engineering on the current project, output an overall architecture description, module division, key data flows, and functional paths, and organize it into a Markdown document suitable for newcomers to read.`
5. After submitting the task, wait for the system to read the project structure layer by layer and organize the result.
6. As needed, have the system output an overall architecture document, a module description document, or a project analysis description that is easy for new members to understand.

## Prompts and Feedback You Will See

- The result is usually not a single page of explanation but an extensible project-level analysis material.
- The output emphasizes completeness, layering, and traceability.
- The system may distinguish overall documents from module documents to help you read the project by layer.
- If your goal is more suited to "single-file/single-module design extraction", the system may guide you to switch to a smaller-scope analysis approach.

## Notes

- This is a rule/expert-driven entry point, not a fixed CLI subcommand.
- Before starting the task, first state whether you want "project reverse construction" or "code reverse design"; the two have different scopes.
- The output goal should try to avoid language-bound expressions, which is more suitable for later migration, rewriting, and training new people.
- The larger the project, the more it is recommended to first split by module and then merge the overall document.
- If you only say "analyze the whole project" without stating the focus, the output usually tends toward an overview and is hard to directly satisfy specific purposes such as migration, training, or reporting.
