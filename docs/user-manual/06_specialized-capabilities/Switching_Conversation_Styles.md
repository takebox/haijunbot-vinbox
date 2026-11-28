# Switch Between Different Conversation Styles

## Use Cases

When you want HaijunBot to use a different expression style, way of prompting risks, and way of presenting suggestions for the same task, you can switch the conversation style by loading different persona rules.

## Steps

1. First prepare a persona rule file that describes the target style, and put it into a rule directory that can be loaded.
2. In your task or conversation, clearly state that you want to switch to that persona style and load the corresponding rule.
3. If you want to start directly, you can use an expression like: `Next, please answer in a professional and rigorous style, emphasizing risks, constraints, and acceptance criteria.`
4. After that persona rule takes effect, continue to raise your analysis, writing, or decision tasks.
5. Observe whether the expression, structure, and risk-prompting style of the system output meet expectations; if needed, you can load another persona rule for comparison.

## Prompts and Feedback You Will See

- After switching to a different persona, the reply tone and organization style for the same kind of task change.
- The specific manifestation of the style depends on the content of the persona rule you loaded, for example more formal, more structured, or more emphasis on risk and verifiability.
- After switching, the change is mainly in the expression style, not the underlying functional capability itself.

## Notes

- This is a rule system entry point, not a fixed CLI subcommand.
- What persona rules change is the interaction style, not the same as replacing the underlying model or functional module.
- If you need more formal output or output more suitable for reporting, you can prioritize the professional and rigorous style.
- If you want to compare styles for the same task, it is best to switch persona rules while keeping the task goal unchanged.
- Style switching is more suitable for affecting the expression style, risk prompting, and organization structure, and not suitable as a replacement for a clear task goal description.
