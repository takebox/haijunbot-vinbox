---
name: gh_rule
description: Triggered when PRs or Issues of a GitHub repository need to be handled automatically. Triggered whenever the user mentions "handle PR", "handle issue", "merge PR", "view PR", "close issue", "comment issue", "gh plugin", or "GitHub assistant".
---

# gh Plugin Usage Rules

This rule defines how to use the gh plugin (GitHub assistant), guiding the Agent to handle the current repository's PRs and Issues according to a **standard workflow**, and to **confirm with the user at key checkpoints** before performing irreversible operations.

## Capability List

The gh plugin reuses the official GitHub `gh` CLI to perform GitHub operations (executing `gh` commands via `execute_script`). The plugin itself provides no standalone tools; the Agent directly calls `gh` commands:

| Capability  | Command                              | Type  | Description                  |
| ----------- | ------------------------------------ | ----- | ---------------------------- |
| List PRs    | `gh pr list`                         | Read  | List Pull Requests by state  |
| View PR     | `gh pr view <number>`                | Read  | View a single PR's details   |
| Merge PR    | `gh pr merge <number>`               | Write | Merge a PR (auth required)   |
| List Issues | `gh issue list`                      | Read  | List Issues by state         |
| View Issue  | `gh issue view <number>`             | Read  | View a single Issue's details|
| Comment     | `gh issue comment` / `gh pr comment` | Write | Comment on a PR/Issue (auth required) |
| Close Issue | `gh issue close <number>`            | Write | Close an Issue (auth required) |

> Read operations (list/view) are anonymously accessible for public repositories; write operations (merge/comment/close) require a logged-in token.

**Common command examples**:

```bash
# List open issues / PRs in the current repository
gh issue list
gh pr list

# View a single issue / PR's details (including body, labels, merged/mergeable status)
gh issue view 60
gh pr view 123

# Post a comment
gh issue comment 60 --body "comment content"
gh pr comment 123 --body "comment content"

# Close an issue (irreversible)
gh issue close 60

# Merge a PR (irreversible; defaults to --rebase, merging as-is without squashing commits)
gh pr merge 123 --rebase
```

## Default Repository

By default, the gh plugin handles the **GitHub repository corresponding to the current working directory** (auto-resolved by reading git remote origin). If the current directory is not a git repository or lacks an origin remote, first confirm the target repository, or specify it with `gh repo set-default owner/repo`, or explicitly with the `--repo owner/repo` parameter added to the command.

**Before starting any operation, confirm the target repository first**: if the user has not specified a repository, first use `gh issue list`/`gh pr list` or ask the user to confirm which repository to operate on, to avoid operating on the wrong repository.

## Authentication Flow

1. **Read operations** (list/view PRs, issues): public repositories are anonymously accessible; no authentication required, execute directly.
2. **Write operations** (merge PRs, comment, close issues): **authentication is required first**. If a command returns a "not logged in" message, guide the user to run in the terminal:

   ```bash
   gh auth login
   ```

   The plugin reuses the official GitHub gh CLI login state, and subsequent write operations automatically use that token.

3. You can use `gh auth status` to check whether you are logged in.

## Standard Issue Handling Workflow

When handling an issue, execute in the following order; **each step must be based on the result of the previous step**; do not skip steps or speculate:

### 1. Locate and Confirm the Target

- Use `gh issue list` (defaults to `open`) to list the current repository's issues, and confirm with the user which one to handle (by number).
- If the user only gives a number, use `gh issue view <number>` to view the issue's details (title, author, body, labels, status), **first restate the issue content to confirm your understanding is correct**, then continue.

### 2. Handling (Mainly Reading/Analysis)

- Read the issue's `body` and existing comments, and determine the type of problem (bug / requirement / question).
- If you need context, view the relevant code or documentation to form a handling plan.

### 3. Key Checkpoint Confirmation (Required Before Write Operations)

- **Before commenting**: confirm the comment content and wording with the user, and after confirming it is posted to the correct issue number, run `gh issue comment`. The comment must **always** end with the fixed "automated" marker defined in the "Comment Marker" section.
- **Before closing**: closing is an **irreversible** operation. You must confirm with the user "should issue #N be closed", and only run `gh issue close` after obtaining explicit consent. Do not close on your own just because the issue appears resolved.

### 4. Wrap Up

- After the operation completes, report the result to the user (comment posted / issue closed).

## Standard PR Handling Workflow

When handling a PR, execute in the following order:

### 1. Locate and Confirm the Target

- Use `gh pr list` (defaults to `open`) to list the current repository's PRs, and confirm with the user which one to handle (by number).
- If the user only gives a number, use `gh pr view <number>` to view the PR's details (title, author, state, `merged`, `mergeable`, head/base branches, body).

### 2. Pre-Merge Check (A Required Step for Merging a PR)

- **View the PR status**: use `gh pr view <number> --json state,merged,mergeable,headRefName,baseRefName,title,body` to confirm:
  - whether `state` is `open`;
  - whether `merged` is `false` (an already-merged PR cannot be merged again);
  - whether `mergeable` is `true` (`false` means there is a conflict, **cannot be merged**, and the conflict must be resolved first; `null` means GitHub is still computing, retry later).
- Read the PR's `body` and change description to understand the changes.
- **Only when the PR is mergeable (open, unmerged, no conflict) should you proceed to the next step**; otherwise explain the reason to the user (e.g. a conflict) and do not force a merge.

### 3. Key Checkpoint Confirmation (Required Before Merging)

- **Merging is a high-risk irreversible operation**; you must confirm with the user:
  - the PR number and title to merge;
  - the merge method (`--squash` / `--rebase` / `--merge`; **defaults to `--rebase`, merging as-is without squashing commits**, and can be specified as needed).
- Only after obtaining explicit user consent, run `gh pr merge`.

### 4. Comment (Optional)

- If you need to add an explanation on the PR, first confirm the comment content with the user, then run `gh pr comment`. The comment must **always** end with the fixed "automated" marker defined in the "Comment Marker" section.

### 5. Wrap Up

- After a successful merge, report the result to the user (PR #N merged, merge method).

## Comment Marker (Automated-Handling Statement)

**All comments posted automatically by the gh plugin (on issues or PRs) must end with the fixed "automated" marker**, indicating that the comment was automatically generated by the HaijunBot GitHub plugin, so readers can identify it.

Fixed marker (Markdown):

```markdown
---

> 🤖 This comment was handled automatically by the HaijunBot GitHub plugin
```

- The marker is placed at the **end** of the comment, separated from the body by `---`.
- **The fixed text above must be used verbatim**; the wording or style must not be changed.
- Only attach it when the comment is **posted automatically by the plugin**; if the comment content needs to be disguised as human-posted, it does not conform to this rule and should not be posted.

**Comment example**:

```markdown
Thanks for the feedback! We have implemented this configuration example and merged it into the documentation.

---

> 🤖 This comment was handled automatically by the HaijunBot GitHub plugin
```

## Code Commit

If code is **modified** while handling an issue/PR, the CodeAgent automatically generates a temporary commit starting with `CheckPoint #N` for each change (used only for process rollback and should not directly enter history). When the requirement is truly complete, you **must call the `commit` tool** to generate a formal commit—it automatically squashes these temporary CheckPoint commits into one formal commit (generating the commit message with an LLM).

- After the code changes are complete and before reporting the result, call the `commit` tool to commit.
- **Do not use `git commit` instead of the `commit` tool**: the changes have often already been committed by an automatic CheckPoint, in which case `git commit` will report `nothing to commit` because the working tree is clean, and the formal commit message is lost; after a subsequent PR squash merge, the main branch commit title will degrade to `CheckPoint #N (#PR)`. Always use the `commit` tool to generate the formal commit.
- Do not directly report the `CheckPoint #N` temporary commit as the final result; the formal commit is generated by the `commit` tool.
- If the user requests a manual commit or specifies a commit message, you may use `git commit` instead and follow the user's request.
- **Remediation**: if `CheckPoint #N` has already been mistakenly merged into the main branch, you can locally call the `commit` tool on that commit to generate a formal commit (same content, only different message), then use `git push --force-with-lease=main:<old commit> origin main` to rewrite the remote main branch commit message (rewriting history is a destructive operation and must be confirmed with the user first).

## Code Changes Go Through a PR (Open-Source Standard Flow)

**For any handling involving code/documentation changes, follow open-source collaboration standards by default: complete the work on a feature branch and merge into the main branch via a Pull Request, without committing directly to `main`.** This is consistent with the "Fork + feature branch + PR" requirement in [CONTRIBUTING.md](../../../../CONTRIBUTING.md).

### Standard Flow

1. **Confirm the baseline**: first run `git fetch origin` and confirm the current main branch (default `main`) status, to avoid basing work on outdated history.
2. **(External contributors) Fork the repository**: if you lack write access, first run `gh repo fork <owner>/<repo> --clone=false`, then manually `git clone https://github.com/<your-account>/<repo>.git` (the fork becomes `origin`), and `git remote add upstream https://github.com/<owner>/<repo>.git` to set the original repository as `upstream`. Skip this step if you have write access.
3. **Create a feature branch**: cut a semantically named branch from the main branch, such as `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.
4. **Complete the changes on the branch and commit**: after the changes are complete, call the `commit` tool to generate a formal commit (see the previous section).
5. **Push the branch**: `git push -u origin <branch-name>`.
6. **Create a PR**: use `gh pr create --base main --head <branch-name> --title <title> --body-file <description-file>` to create a PR; the description must include: background, change list, and verification method.
7. **Link the Issue**: if the PR resolves an Issue, link it in the PR description with `Closes #<number>` (auto-closed after merge); do not manually close the Issue early during the process.
8. **Final report**: report the PR link and status to the user.

### Forking Someone Else's Repository to Handle Its Issues (the gh Plugin's "Fork and create a CodeAgent" Scenario)

When the gh plugin handles Issues of **other open-source project repositories** through the "Fork and create a CodeAgent to handle" entry, the local directory is a clone of the fork (`origin` points to your fork, and `upstream` already points to the original repository), and the goal is to modify the code and then **submit a PR to the upstream original repository**:

1. **Cut a feature branch**: cut a branch from the upstream main branch: `git fetch upstream && git checkout -b fix/issue-<number> upstream/<upstream-main>`.
2. **Complete the changes on the branch and commit**: after the changes are complete, call the `commit` tool to generate a formal commit.
3. **Push the branch to the fork**: `git push origin <branch-name>`.
4. **Submit a PR to upstream**: `gh pr create --repo <original-repo owner/repo> --head <your-fork>:<branch-name> --base <upstream-main> --title <title>`, and link the Issue in the description with `Closes #<number>`.
5. **Confirm before write operations**: confirm with the user before externally visible operations such as creating a PR, commenting, or closing.

### Constraints

- **Do not commit code changes directly to `main`**; if you find changes are already on `main` and not yet pushed, first move them to a feature branch before pushing the main branch.
- One PR focuses on one thing (one feature/fix/documentation topic); avoid mixing unrelated changes in the same PR.
- PR titles follow the commit convention (`feat:` / `fix:` / `docs:` / `refactor:` etc.).
- Before creating a PR or pushing a branch, if it involves externally visible or history-rewriting operations with a large impact, confirm with the user first.

### Exceptions

- When the user explicitly requests committing directly to `main` (e.g. an emergency fix or rapid iteration on a personal repository), follow the user's request.
- Purely read-only operations, comments, closing Issues, and other handling that does not involve code changes do not need to go through a PR.

## General Rule for Key Checkpoint Confirmation

The following operations **must be confirmed with the user first and executed only after obtaining explicit consent**, and must not be performed without authorization:

1. **Closing an issue** (irreversible).
2. **Merging a PR** (irreversible, and the merge method must be confirmed).
3. **Posting a comment** (content is externally visible; wording and target number must be confirmed).
4. **Cross-repository operations** (when `--repo` points to a non-current repository, confirm first).

When confirming, provide **specific information** (number, title, intended action) so the user can make a clear judgment, rather than vaguely asking "should I continue".

## Security Notes

- A token is a sensitive credential; **do not** leak the full token in comments, logs, or output.
- For irreversible operations such as merging/closing, you **must** confirm with the user before executing (see above).
- When a write operation fails and returns 401/403, prompt the user to log in again (the token may have expired).
- Do not perform write operations on issues/PRs **that the user did not request**.
