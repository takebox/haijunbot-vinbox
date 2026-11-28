# Using Turbo Mode to Execute Tasks Quickly

## When to Use

When you want the code agent to start quickly and execute the task, without the system doing time-consuming operations such as task classification, automatic rule loading, and context recommendation, you can use turbo mode. Turbo mode is suitable for:

- You already clearly know what to do and do not need the system to do intelligent analysis
- You want to start the code agent quickly to reduce waiting time
- You have already provided enough context information in the command
- You need to execute multiple simple tasks in batches

## Steps

1. First open a terminal in your project directory.
2. Start the code agent with the `-q` or `--quick` parameter:

   - **Interactive mode**: enter `hca -q`, then press Enter.
   - **Non-interactive mode**: enter a command like the following, then press Enter:

     `hca -q -n --task "fix the problem of configuration loading failure"`

3. The system directly starts the code agent, skipping steps such as task classification, rule loading, and context recommendation.
4. In interactive mode, directly enter your task requirement; in non-interactive mode, the system directly executes the content after `--task`.

## Prompts and Feedback You Will See

- After startup you see a welcome message, indicating that the code agent is ready.
- In turbo mode, the system shows a prompt: `⚡ Turbo mode enabled: skipping task classification, rule loading, context recommendation`.
- The system keeps Git environment initialization and safety rollback point settings, ensuring code safety.
- In interactive mode, you see a prompt to input your requirement, and can continue to enter task content.
- In non-interactive mode, the system directly uses the content after `--task` to start executing.

## Notes

- Turbo mode skips the following features:
  - Task classification (the system will not automatically identify your task type)
  - Automatic rule loading (it will not load specific rules based on the task type)
  - Context recommendation (it will not automatically recommend relevant code context)
  - Methodology loading (it will not load relevant methodology documents)
- Turbo mode keeps the following features:
  - Git environment initialization
  - Safety rollback point settings
  - Code modification, review, and commit features
- If you need the system to perform intelligent analysis and recommendation, it is recommended not to use turbo mode.
- Turbo mode can be used in combination with other parameters, such as `-n` (non-interactive mode), `-T` (task description), etc.
- If your task is relatively complex, it is recommended not to use turbo mode, and to let the system perform complete analysis and preparation.
