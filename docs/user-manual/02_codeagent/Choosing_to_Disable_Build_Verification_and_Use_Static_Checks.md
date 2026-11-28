# Choosing to Disable Build Verification and Switch to Basic Static Checks When the Build Fails

## When to Use

When your project can only be built in a special environment, or the current machine consistently cannot complete full build verification, the system gives you a choice after the first build failure: no longer do full build verification, and switch to only doing basic static checks.

## Steps

1. Normally submit a task that will trigger code modification.
2. If this round of build verification fails, first view the failure summary in the terminal.
3. When the system asks whether you want to disable build verification and only do basic static checks from then on, make a choice according to your project situation.
4. If you confirm the disabling, the system immediately remembers this choice and directly switches to basic static checks from then on.

## Prompts and Feedback You Will See

- On the first build failure, the terminal shows a failure summary and clearly indicates that you can choose to disable build verification and only do basic static checks from then on.
- If you accept this option, the system switches to basic static checks immediately and continues to show the result in this round's output.
- This choice is saved to the current project; the next time a similar task is run, the system can directly reuse this setting.
- If you do not accept, the system continues to handle it via the build failure branch and converts the error information into subsequent fix hints.

## Notes

- This option suits projects with restricted build environments, incomplete CI environments, dependencies on external services, or local machines that cannot reproduce full build conditions.
- After disabling, it does not mean code is not checked at all, but that it switches to a more basic static check route.
- This is a project-level setting; once saved, subsequent runs in the same project usually continue to reuse it, unless you re-enable full build verification later.
