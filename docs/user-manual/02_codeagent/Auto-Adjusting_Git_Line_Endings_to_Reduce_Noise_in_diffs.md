# Auto-Adjusting Git Line Ending Settings to Reduce Noise in Diffs

## When to Use

When you work on the same repository across different platforms, or the repository often produces a lot of meaningless diffs because of line ending differences, the system automatically adjusts the relevant settings while preparing the Git environment to minimize this kind of interference.

## Steps

1. Start the code agent in a Git repository.
2. When preparing the Git environment, the system automatically checks the current repository's line ending related settings.
3. If the current settings do not match the recommended values, the system updates them directly, then continues the subsequent flow.
4. After it is done, continue to run your code task as usual.

## Prompts and Feedback You Will See

- When the system finds that the current line ending configuration does not match the recommended values, the terminal first gives a reminder and lists the settings that will be adjusted.
- After the settings are done, the terminal indicates that the Git line ending sensitive settings have been updated.
- If the current configuration already meets the requirements, the system usually does not prompt again.

## Notes

- This step does not require manual confirmation; the system performs the adjustment directly.
- Its goal is to reduce meaningless changes caused by platform differences, not to replace your project's line ending conventions.
- If your team already has a clear Git line ending policy, after running it is best to check whether the automatic settings match the team's requirements.
