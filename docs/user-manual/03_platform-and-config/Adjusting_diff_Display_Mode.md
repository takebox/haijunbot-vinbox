# Adjusting the Code Diff Display Mode

## Use Cases

If you feel the current diff preview is not suitable for reading, for example you want something more compact, with emphasized syntax highlighting, or a side-by-side view, you first need to understand the current diff display behavior. Based on the current source code behavior, the default visualization mode returned is `side_by_side`.

## Steps

1. First, in a code modification flow that shows a diff, observe the current display effect.
2. The current source code comments list the concept of optional modes: `unified`, `syntax`, `compact`, `side_by_side`, `default`.
3. According to the current `config.py` implementation, the default return value is `side_by_side`.
4. If a later version exposes this capability as a formal config option, configure it by the formal key name; this document is mainly used to explain the current state and boundaries.

## Prompts and Feedback You Will See

- In scenarios that support diff display, you will directly see the currently used display style.
- Under the current implementation, it is closer to a side-by-side display effect.
- If the later entry point does not enable enhanced diff, the visible effect may not exactly match the mode names described here.

## Notes

- What the current source code shows is a fixed return value; it should not be written as a capability that "is already stably open for users to configure freely".
- The focus of this document is to help users understand the current diff display preference, not to promise that it can definitely be switched via `config.yaml` at this stage.
- If you need to stably change the display mode, wait for the corresponding config option to be formally exposed or use entry-level parameters (if provided in the future).
