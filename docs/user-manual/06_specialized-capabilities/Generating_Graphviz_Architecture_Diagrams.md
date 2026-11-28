# Generate Graphviz Architecture Diagrams

## Use Cases

When you want HaijunBot to read a piece of code or a project and output a directly renderable Graphviz architecture diagram, you can use the built-in architecture diagram generator to start the task.

## Steps

1. In the task, clearly tell the system: you want to use the architecture diagram generator.
2. State the code scope you want to analyze and the view type you want output, for example:
   - logical view
   - implementation view
   - process view
   - deployment view
   - use case view

3. If you are not yet sure about the view type, first let the expert help you clarify the goal.
4. You can also directly use a task like: `Please use the architecture diagram generator to analyze src/server and src/gateway, and output a Graphviz DOT architecture diagram, focusing on the main components, call relationships, and data flow.`
5. After submitting the task, wait for the expert to fully read the relevant code and identify the core components and relationships.
6. Ask the expert to output the result as a Graphviz DOT file; after generation is complete, then continue to render a PNG image as needed.

## Prompts and Feedback You Will See

- If your request does not state the view type, the expert usually follows up or clarifies first.
- The output result is `.dot` content that can be directly saved and rendered.
- The diagram highlights component responsibilities, relationships, and layers rather than directly piling up source code details.
- In the end you get an architecture diagram source file suitable for further rendering or archiving.
- If you ask to save it to a specified location, you usually also get an explicit output file path.

## Notes

- This is an expert-type task entry point, not a fixed CLI subcommand.
- The output focuses on abstract architecture expression, not drawing function names and file paths into the diagram as-is.
- If the analysis scope is too large, it is recommended to first specify a module or target view to avoid an overly vague output.
- After generating the `.dot`, if you need an image, you still need to continue with the rendering step.
