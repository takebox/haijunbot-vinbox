# Controlling Whether diff Shows Line Numbers

## Use Cases

If you rely heavily on line numbers for locating things when reading code changes, you need to understand the current diff line-number behavior. Based on the current source code behavior, diff shows line numbers by default.

## Steps

1. In a code modification flow that shows a diff, observe the current preview content.
2. In the current source code, diff line-number display returns `true` by default.
3. If the diff you currently see includes line numbers, it means this default behavior is in effect.

## Prompts and Feedback You Will See

- In the diff preview, you usually see the line-number information directly.
- Line numbers make it more convenient to locate modified positions and cross-check file content.
- If some scenarios do not show line numbers, it is more likely that the entry point does not use the same diff display path, rather than this default behavior failing.

## Notes

- The current implementation is closer to a "fixed default behavior description" rather than a description of an independent config option formally exposed to users.
- Do not interpret this document as "line numbers can now be freely toggled in config.yaml" unless a later version explicitly provides the corresponding config key.
