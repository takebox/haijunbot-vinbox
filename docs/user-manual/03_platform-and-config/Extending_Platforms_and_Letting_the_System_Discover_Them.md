# Extending Available Platform Implementations and Letting the System Discover Them

## Use Cases

If you want HaijunBot to use not only the built-in platforms but also platform implementations you extend yourself, you can put the platform implementation files into the user platform directory so the system automatically discovers and registers them at startup.

## Steps

1. First prepare your custom platform implementation files.
2. Put them into HaijunBot's user platform directory.
3. If you do not know where the directory is, the system tries to create it according to its own user platform directory rules on first use; you can confirm by starting a platform-related feature and observing the directory creation or scan prompts.
4. After restarting the relevant session, the system scans both of the following during startup:
   - The user platform directory
   - The built-in platform directory
5. If your implementation meets the platform requirements, it is registered into the available platform list.
6. Then, through "Viewing Current Platform and Model Info" or platform-management-related entry points, confirm whether the newly added platform has appeared.

## Prompts and Feedback You Will See

- If the user platform directory does not exist, the system tries to create it automatically.
- If creating the directory fails, you see an error prompt that platform directory creation failed.
- If a platform implementation lacks required capabilities or has an incomplete interface, the system gives a warning and skips that implementation.
- If a module fails to load or fails to register, the system outputs the corresponding error rather than silently treating it as success.
- When configured correctly, you will eventually see the newly added platform name in the available platform list or platform-related features.

## Notes

- This capability is not enabled by some key in `config.yaml`, but takes effect by "putting the implementation files into the user platform directory".
- Not just any script dropped into the directory will be recognized; only files that meet the platform implementation requirements are registered.
- A custom platform load failure usually does not prevent the built-in platforms from continuing to work, but your extended platform itself will not take effect.
- It is recommended to first verify in a simple scenario that the newly added platform can be discovered, then continue wiring it into a more complete session or service flow.
