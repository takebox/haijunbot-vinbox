# Restoring Code Agent Sessions

## When to Use

When your previous code task has not been finished yet, or you want to continue using the previous task context, recent memory, rule state, and part of the code agent configuration, you can restore the history session when starting the code agent.

## Steps

1. First enter the project directory you handled previously.
2. In the terminal, enter `hca --restore-session`, then press Enter.
3. If the system finds a restorable session, it first enters the restore flow, then continues this run.
4. After restoration is complete, continue to enter the code requirement you want to add this time, or directly continue processing using the previous context.
5. If you do not want to pass the parameter explicitly, you can also run the code agent directly in a startup method where automatic session restoration is already enabled, letting the system try to restore automatically.

## Prompts and Feedback You Will See

- After a successful restore, you usually see a prompt like `✅ Restored session from xxx.`.
- If recent memory, memory tags, rule state, or code agent configuration were restored, the system also continues to show the corresponding restore results, for example how many recent memory entries were restored, and which rules were reactivated.
- In an ordinary interactive startup where you did not explicitly specify `--restore-session`, if a history session corresponding to the current commit exists, the system may also first ask whether you want to restore from the matching session.
- If restoration fails, the system gives a failure prompt, then continues to run as an ordinary new session.

## Notes

- Session restoration is better suited to continuing work in the same project and a similar code state.
- After restoration, the code agent tries to bring back the previous tool groups, review configuration, prefixes and suffixes, and other runtime state, but this does not mean all external environments are necessarily identical to last time.
- If the current repository state has already changed significantly, even if there is a history session, it may not be suitable to directly continue using the previous task conclusion.
- If you only want to re-execute the same kind of task rather than continue the history context, starting a new session directly is usually cleaner.
