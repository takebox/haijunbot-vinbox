# hcad Best Practices

## 1. Overview

### 1.1 What is hcad

`hcad` (HaijunBot Code Agent Dispatcher) is a
convenient dispatch tool for the HaijunBot code agent (`hca`), designed to simplify the quick startup and management of code tasks. It is a
shortcut alias for the `haijunbot-code-agent-dispatcher` command.

### 1.2 Core Features

- **Automated mode enabling**: automatically enables non-interactive mode (`-n`), worktree mode (`--worktree`), and task dispatching (`--dispatch`)
- **Multi-line task support**: supports multi-line task input and automatically creates temporary files to handle it
- **Isolated Git development**: Git worktree is enabled by default, ensuring development on an independent branch
- **Interactive input**: provides a friendly multi-line input interface (confirm with Ctrl+J/Ctrl+])
- **Tmux integration**: intelligently schedules tasks to independent tmux panels, supporting parallel tasks

### 1.3 Relationship with hca

| Feature            | hcad                | hca                                |
| ------------------ | ------------------- | ---------------------------------- |
| Automatically enable non-interactive mode | ✅ Yes              | ⚠️ Must manually specify `-n`      |
| Automatically enable worktree | ✅ Yes              | ⚠️ Must manually specify `-w` or `--worktree` |
| Automatically enable dispatch | ✅ Yes              | ⚠️ Must manually specify `--dispatch` |
| Automatic multi-line task handling | ✅ Automatically creates a temporary file | ⚠️ Must manually specify `--task-file` |
| Interactive mode   | ✅ Supported        | ✅ Supported                       |

**Use cases**:

- Use `hcad`: for quickly launching code tasks that need worktree isolation and automatic dispatching
- Use `hca`: when you need fine-grained control over every parameter, or an interactive session

---

## 2. Basic Usage

### 2.1 Direct Command Mode

The simplest way to use it is to pass the task description directly on the command line:

```bash
# Single-line task
hcad "Refactor the user authentication module using a new encryption algorithm"

# Code generation task
hcad "Create a user registration API with input validation and error handling"

# Code optimization task
hcad "Optimize database query performance and add necessary indexes"
```

### 2.2 Interactive Input Mode

When no argument is passed, it enters interactive mode, which supports multi-line input:

```bash
hcad
```

After entering interactive mode:

- Enter the task content (multi-line supported; press `Enter` for a new line)
- Press `Ctrl+J` or `Ctrl+]` to confirm and submit
- The system automatically creates a temporary file and dispatches the task

**Interactive mode example**:

```text
Enter the task content (Ctrl+J/Ctrl+] to confirm, Enter for a new line):
> Refactor the order processing module
> 1. Extract the order state machine into a separate class
> 2. Implement an order lock mechanism to prevent concurrency conflicts
> 3. Add an audit log for order operations
> Background: order status inconsistencies currently occur under high-concurrency scenarios

[Press Ctrl+J to confirm]
📝 Temporary file created: /tmp/jcad_task_xxxxxxxx.txt
```

### 2.3 Task File Mode

For complex task descriptions, you can write a task file in advance:

```bash
# Create a task file
cat > my_task.txt << 'EOF'
Task description: refactor the payment module

1. Decouple the payment logic from the order module
2. Implement a payment state machine
3. Integrate multiple payment gateways (Alipay, WeChat Pay)
4. Add payment timeout handling and retry mechanisms

Technical requirements:
- Use the strategy pattern for multiple payment gateways
- Add unit tests covering the core logic
- Ensure transaction consistency

Background:
- The payment logic is currently coupled within the order module and hard to maintain
- New payment channels need to be supported
EOF

# Directly specify the task file
hcad my_task.txt
```

#### ⚠️ Important: File Detection Logic

`hcad` determines whether the input is a task file or task content by checking whether the file exists:

- If the file `my_task.txt` **exists** → it is treated as a task file (using the `--task-file` argument)
- If the file `my_task.txt` **does not exist** → it is treated as task content (using the `--task` argument, i.e. `my_task.txt` is treated as the task description)

**Best practice recommendations**:

1. **Ensure the file is created**: before using `hcad my_task.txt`, make sure the file exists
2. **Use absolute paths**: absolute paths are recommended, e.g. `hcad /path/to/my_task.txt`, to avoid path issues
3. **Verify the file content**: you can run `cat my_task.txt` first to confirm the content is correct

**Direct multi-line command input**:

```bash
# Wrap a multi-line command in double quotes (watch out for escaping)
hcad "
Refactor the user management module
1. Extract the user validation logic into a separate service class
2. Implement a user permission caching mechanism
3. Add an audit log for user operations
"
```

---

## 3. Core Feature Breakdown

### 3.1 Automatically Enabled Working Modes

`hcad` automatically enables the following three key modes to simplify task startup:

#### Non-interactive mode (`-n`)

- Does not enter an interactive session and executes the task directly
- Suitable for automation scripts and quick task dispatching

#### Worktree mode (`--worktree`)

- Executes the task in an independent Git worktree
- Isolates the development environment to avoid polluting the main branch
- Automatically manages the creation, use, and cleanup of the worktree

#### Task dispatching (`--dispatch`)

- Uses Tmux to create independent panels to execute tasks
- Supports parallel execution of multiple tasks
- Tasks run in the background and do not block the current terminal

### 3.2 Multi-line Task Handling Mechanism

`hcad` internally handles multi-line tasks automatically:

```python
# Pseudocode flow
if "\n" in task:
    # Multi-line content detected
    temp_file = create_temp_file(task)
    run_jca_dispatch(temp_file, is_dispatch_mode=True, force_dispatch=True)
else:
    # Single-line content passed directly
    run_jca_dispatch(task)
```

**Key points**:

- Multi-line tasks are automatically converted to a temporary file
- Temporary files are saved in the `/tmp` directory
- File name format: `jcad_task_{timestamp}.txt`

### 3.3 Isolated Development with Worktree

Worktree mode is a core safety feature of `hcad`:

#### Workflow

1. **Create the worktree**
   - Automatically generate a unique branch name: `haijunbot-{project_name}-{timestamp}-{random_suffix}`
   - Create a git worktree on that branch
   - If the repository has no initial commit, automatically create an initial commit

2. **Link configuration**
   - Symlink the original repository's `.haijunbot` directory into the worktree
   - Ensure consistency of configuration and data

3. **Automatically commit unsaved changes**
   - Detect whether the working area has uncommitted changes
   - Automatically commit these changes to ensure the working area is clean before task execution

4. **Execute the task**
   - Perform code modifications in the worktree directory
   - All changes are made on an independent branch

5. **Merge back into the main branch**
   - After the task completes, rebase onto the original branch using a rebase strategy
   - Merge via fast-forward
   - Maintain a linear Git history

6. **Clean up resources**
   - Automatically delete the worktree directory
   - Delete the corresponding temporary branch

#### Core Advantages

| Advantage  | Description                 |
| ---------- | --------------------------- |
| Isolated development | Does not affect the stability of the main branch |
| Automatic management | No need to manually create or delete worktrees |
| Symlink support | Configuration and data are synced automatically |
| Smart merging | Uses rebase to keep the history clean |
| Automatic cleanup | Automatically releases resources after task completion |

### 3.4 Tmux Dispatch Integration

`hcad` intelligently schedules tasks to tmux panels, using different invocation methods depending on the task type:

#### Multi-line tasks or interactive mode (uses Tmux)

For multi-line tasks or interactive input, hcad uses tmux's `dispatch_command_to_panel` function to create a new panel:

```bash
# Internally executed command (tmux dispatch mode)
cd /path/to/project && hca -n -w --task-file '/tmp/jcad_task_xxxxxxxx.txt'
```

**Note**: in tmux dispatch mode, the hca command itself does not need the `--dispatch` argument, because creating the tmux panel already completes the task dispatching.

#### Single-line tasks (direct execution)

For single-line tasks, hcad directly executes the hca command and passes the `--dispatch` argument:

```bash
# Internally executed command (direct dispatch mode)
hca -n -w --dispatch --task 'your task content'
```

**Features**:

- Automatically finds or creates a tmux session
- Uses an intelligent scheduling function to allocate panels
- Supports parallel execution of multiple tasks
- The parent process exits without waiting for the child process to finish

---

## 4. Best Practice Scenarios

### 4.1 Rapid Prototyping

**Scenario**: you need to quickly validate an idea or implement a new feature.

```bash
# Example: quickly implement a new API endpoint
hcad "Create a product list API with pagination and sorting"
```

**Advantages**:

- worktree isolation, does not affect the main branch
- Fast iteration, discard on failure
- Automatic cleanup, no leftover clutter

### 4.2 Complex Refactoring Tasks

**Scenario**: you need to refactor a large amount of code involving multiple files.

```bash
# Use a task file to describe the refactoring task in detail
cat > refactor_auth.txt << 'EOF'
Refactor the authentication module:

Goal: decouple the authentication logic from each module and unify it into an authentication service

Specific steps:
1. Create the AuthenticationService class
2. Migrate the validation logic in user_auth and admin_auth
3. Implement a unified Token management mechanism
4. Update all call sites

Technical requirements:
- Maintain compatibility with the existing API
- Add integration tests
- Update the relevant documentation
EOF

hcad refactor_auth.txt
```

**Advantages**:

- Detailed task descriptions reduce misunderstandings
- worktree isolation keeps the main branch safe
- The automatic merge strategy keeps the history clean

### 4.3 Parallel Task Processing

**Scenario**: handle multiple independent code tasks at the same time.

```bash
# Terminal 1: handle the user module
hcad "Refactor the validation logic of the user module"

# Terminal 2: handle the order module
hcad "Optimize order query performance"

# Terminal 3: add a new feature
hcad "Implement the product recommendation feature"
```

**Advantages**:

- Each task runs in an independent tmux panel
- They do not interfere with each other
- You can monitor the progress of multiple tasks at the same time

### 4.4 Safe Isolated Development

**Scenario**: experimental code or high-risk changes.

```bash
# Experimental feature development
hcad "Try a new memory pool implementation (experimental)"

# Large-scale refactoring
hcad "Split the monolithic application into a microservices architecture"
```

**Advantages**:

- Complete isolation; failures do not pollute the main branch
- Automatic cleanup, no leftover branches
- Can be abandoned at any time with a safe rollback

---

## 5. Advanced Techniques

### 5.1 Toolchain Integration

#### Integration with Git workflows

```bash
# Use hcad on a feature branch
git checkout -b feature/new-api
hcad "Implement the new user API"
# After the task completes, the worktree automatically merges back into the current branch
```

#### Integration with CI/CD

```yaml
# Example: use in a CI script
- name: Automated code fixes
  run: |
    hcad "Fix lint errors in the code"
    # Wait for the task to finish (adjust according to the actual situation)
    sleep 300
```

### 5.2 Custom Configuration

Although `hcad` automatically enables certain arguments, you can still customize its behavior by modifying the source code or environment variables.

#### Adjusting the temporary file directory

Temporary files are saved in `/tmp` by default; you can change this in `hcad_eli.py`:

```python
dir="/tmp",  # Change to another directory
```

#### Adjusting Tmux behavior

```python
stay_in_session_after_exit=True,  # Whether to keep the session after the task ends
shell_fallback=False,  # Whether to allow shell fallback
```

### 5.3 Performance Optimization

#### Batch task processing

For a large number of similar tasks, you can write a script to dispatch them in batch:

```bash
#!/bin/bash
# batch_refactor.sh

modules=("user" "order" "product" "payment")

for module in "${modules[@]}"; do
  echo "Refactoring $module module..."
  hcad "Refactor the $module module and add unit tests and documentation"
  sleep 5  # Avoid launching too many tasks at once
  echo "Dispatched $module task"
done

echo "All tasks dispatched!"
```

#### Reducing waiting time

- Use task files to reduce input time
- Execute independent tasks in parallel
- Use tmux attach to monitor progress

---

## 6. Notes and Frequently Asked Questions

### 6.1 Temporary File Management

**Question**: do temporary files take up disk space?

**Answer**:

- Temporary files are saved in the `/tmp` directory
- They are automatically cleaned up when the system restarts
- Manual cleanup: `rm /tmp/jcad_task_*`

**Recommendations**:

- Regularly check the `/tmp` directory
- Avoid including sensitive information in task files

### 6.2 Worktree Branch Cleanup

**Question**: after a task fails, will the worktree branch remain?

**Answer**:

- `hcad` automatically cleans up the worktree and branch
- If it exits abnormally, manual cleanup may be required

**Manual cleanup commands**:

```bash
# List all worktrees
git worktree list

# Remove a specified worktree
git worktree remove <worktree-path>

# List all branches (including worktree branches)
git branch -a

# Delete a merged branch
git branch -d <branch-name>

# Force delete a branch
git branch -D <branch-name>
```

### 6.3 Tmux Dependency

**Question**: is tmux mandatory?

**Answer**:

- `hcad`'s dispatch mode depends on tmux
- If tmux is not available, you can consider using the `hca` command directly

**Alternative without using tmux**:

```bash
# Use hca directly without dispatch
hca -n -w -r "your task"
```

### 6.4 Troubleshooting

#### Problem: hca command not found

**Error message**:

```text
❌ Error: 'hca' command not found; please make sure haijunbot is installed correctly
```

**Solution**:

1. Confirm haijunbot is installed correctly: `pip list | grep haijunbot`
2. Check the PATH environment variable
3. Reinstall haijunbot

#### Problem: failed to create a tmux panel

**Error message**:

```text
❌ Error: failed to create a tmux panel in dispatch mode
```

**Solution**:

1. Confirm tmux is installed: `tmux -V`
2. Check whether tmux is running properly: `tmux ls`
3. Try creating a tmux session manually: `tmux new -s test`

#### Problem: failed to create a worktree

**Error message**:

```text
fatal: working tree 'xxx' already exists
```

**Solution**:

1. View existing worktrees: `git worktree list`
2. Remove the conflicting worktree: `git worktree remove <path>`
3. Retry the task

#### Problem: empty task content

**Error message**:

```text
❌ Error: task content is empty and cannot be executed
```

**Solution**:

1. Check whether the task file exists: `ls -la my_task.txt`
2. Confirm the task file content is not empty: `cat my_task.txt`
3. Check whether the file path is correct

### 6.5 Best Practices Summary

| Principle    | Description                        |
| ------------ | ---------------------------------- |
| Clear task description | Describe the task goals, steps, and requirements in detail |
| Use task files | For complex tasks, use files instead of command-line arguments |
| Reasonable parallelism | Independent tasks can run in parallel; related tasks should run serially |
| Monitor progress | Use tmux attach to view task progress |
| Regular cleanup | Regularly check and clean up temporary files and worktrees |
| Back up important data | Back up the code before large-scale refactoring |
| Test verification | Test thoroughly after the task completes |
| Documentation updates | Update the relevant documentation in a timely manner |

---

## 7. References

- [HaijunBot Usage Guide](../haijunbot_book/4.Usage_Guide.md)
- [hca command documentation](../haijunbot_book/4.Usage_Guide.md)
- [Git Worktree official documentation](https://git-scm.com/docs/git-worktree)
- [Tmux official documentation](https://github.com/tmux/tmux/wiki)

---

**Document version**: v1.0  
**Last updated**: 2025-01-12  
**Maintainer**: HaijunBot Team
