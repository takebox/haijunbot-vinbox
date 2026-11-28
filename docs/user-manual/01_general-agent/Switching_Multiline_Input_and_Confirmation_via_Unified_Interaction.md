# Switching Multiline Input and Confirmation Implementations via a Unified User-Interaction Wrapper

## When to Use

When the same set of Agents needs to be adapted to CLI, Web, or other interaction interfaces at the same time, a unified user-interaction wrapper can keep the multiline input and confirmation logic consistent.

## Steps

1. Enter normally the flow that requires multiline input or confirmation, such as entering a task, supplementary notes, or answering a confirmation question.
2. In the CLI, you will usually see a multiline input prompt and use `Ctrl+J` or `Ctrl+]` to submit; in other interfaces, you may see buttons, dialogs, or differently styled input boxes.
3. No matter how the interface appearance changes, the system processes these input and confirmation actions according to the same task logic.

## Prompts and Feedback You Will See

- Multiline input will still appear as the same task input flow.
- Confirmation operations will still appear as consistent confirmation questions and confirmation results.
- This means the details you see on different front ends may differ slightly, but the operation semantics stay consistent.

## Notes

- This capability is more about lower-level interaction compatibility; for ordinary users it is usually "invisible".
- If you find that the input behavior differs slightly between interfaces, it does not mean the task logic is different; it is usually just a different input implementation.
- The key prompts in the document are mainly based on the CLI experience; other interfaces may substitute buttons or different interactions.
