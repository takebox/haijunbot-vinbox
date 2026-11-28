# Interrupting Model Output While Running and Entering Human Intervention Information

## When to Use

When you find that the agent's response is going off track, or it is about to perform an action you do not want, you can interrupt it during the run and add new instructions.

## Steps

1. When the agent is continuously outputting, press the interrupt shortcut to interrupt the current output.
2. After the interruption, the system immediately prompts: `⚠ Interruption detected, please enter supplementary information (Ctrl+J/Ctrl+] to confirm, press Enter directly to skip)`
3. If you want to correct the direction, write the new supplementary instructions directly in this input box.
4. After writing, press `Ctrl+J` or `Ctrl+]` to submit; the system carries this content into the subsequent flow as human intervention.
5. If you do not want to add anything, just press Enter to skip.

## Prompts and Feedback You Will See

- After the interruption the current task is not immediately lost; instead, you are first given a chance for human supplement.
- You will first see: `⚠ Interruption detected, please enter supplementary information (Ctrl+J/Ctrl+] to confirm, press Enter directly to skip)`
- The content you enter enters subsequent processing as supplementary notes after the interruption.
- If you press Enter directly, the system treats it as skipping this supplement.

## Notes

- Interruption is suitable for course correction, not as a replacement for complete task input.
- Supplementary information should directly state what direction you want to change and what behavior you want to restrict.
- Even for minor supplements, try to write them clearly to avoid the agent continuing to misunderstand.
