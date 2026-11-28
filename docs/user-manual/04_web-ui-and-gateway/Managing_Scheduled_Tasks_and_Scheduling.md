# Managing Scheduled Tasks and Scheduling

## Use Cases

When you want HaijunBot to automatically execute a task at a certain time, every fixed interval, or periodically according to a cron expression (e.g. run a script on a schedule or invoke some capability on a schedule), you can use scheduled task scheduling. Scheduled tasks are managed uniformly by the backend scheduler and support both one-time and recurring tasks.

## Steps

### Understanding the Scheduling Types

When creating a scheduled task, you need to choose one of the following four scheduling methods:

| Scheduling type | Description                          | Typical use case                |
| --------------- | ------------------------------------ | ------------------------------- |
| `run_at`        | Run once at a specified time point   | Run once at a fixed time        |
| `delay`         | Run once after a delay in seconds    | Run with a delay relative to now |
| `interval`      | Run repeatedly at a fixed interval   | Repeat periodically             |
| `cron`          | Run periodically per a cron expression | Complex schedules (e.g. every Monday at 9:00) |

### Using cron Expressions

The cron expression uses the standard 5-field format: `minute hour day month weekday`.

| Field  | Valid range                          |
| ------ | ------------------------------------ |
| minute | 0-59                                 |
| hour   | 0-23                                 |
| day    | 1-31                                 |
| month  | 1-12                                 |
| weekday| 0-7 (both 0 and 7 mean Sunday)       |

Supported syntax:

- `*`: any value.
- `*/number`: a step, e.g. `*/5` means every 5 minutes.
- `range`: e.g. `9-17` means from 9 to 17.
- `list`: e.g. `1,3,5` means 1, 3, and 5.
- Day and weekday form an OR relationship (consistent with standard cron): the schedule triggers when either the date field or the weekday field matches.

Examples:

| cron expression | Meaning                             |
| --------------- | ----------------------------------- |
| `0 9 * * 1`     | Every Monday at 9:00                |
| `*/15 * * * *`  | Every 15 minutes                    |
| `0 0 * * *`     | Every day at 0:00                   |
| `30 8 1 * *`    | On the 1st of every month at 8:30   |

If a cron expression is invalid, the system rejects the task creation and shows an error.

### Viewing Scheduled Tasks

1. In the activity bar on the left of the Web UI, click the "Scheduled Tasks" icon (clock-shaped).
2. The sidebar lists the scheduled tasks that have been created, and each task shows its name, scheduling type, and scheduling information.
3. The scheduled tasks tab auto-refreshes periodically to show the latest status.

### Creating or Deleting Scheduled Tasks

Scheduled tasks are created and deleted directly by the Agent, not through front-end UI buttons:

- You can state your needs in the conversation (e.g. "run a certain command every 5 minutes"), and the Agent calls the scheduled task capability to create the task.
- You can also ask the Agent to delete or query a scheduled task.
- Scheduled tasks are persisted by the backend scheduler and are restored automatically after the gateway restarts.

## Feedback You Will See

- When creating a task, if the scheduling parameters are invalid (e.g. a negative delay in seconds, an interval of 0 or negative seconds, or a malformed cron expression), the system returns an error message.
- Recurring tasks (`interval` or `cron`) keep triggering according to the schedule; one-time tasks (`run_at` or `delay`) are complete after they trigger.
- The scheduled task list is read-only; you can view it in the management sidebar, but you cannot modify or delete tasks there.

## Notes

- Scheduled tasks are managed uniformly by the backend scheduler and persisted to local files; created tasks are restored automatically after the gateway restarts.
- The cron expression is in 5-field format, and both 0 and 7 in the weekday field mean Sunday.
- Creating or deleting scheduled tasks must be done through the Agent; if you need precise control over task parameters, describe the scheduling method and trigger conditions to the Agent in the conversation.
