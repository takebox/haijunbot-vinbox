# gh

GitHub assistant plugin—automatically handles PRs and Issues in the current repository, reusing the official GitHub `gh` CLI login state.

> A HaijunBot built-in plugin, distributed with the source code; it cannot be uninstalled/upgraded.

## Features

- **PR management**: list, view, and merge Pull Requests in the current repository
- **Issue management**: list, view, comment on, and close Issues in the current repository
- **GitHub authentication**: reuse the official GitHub `gh` CLI login state (`gh auth login`); write operations (merge/comment/close) require authentication
- **Frontend sidebar**: editor activity bar → GitHub icon, directly browse/operate Issues and PRs (list/details/comment/close/merge)
- **Fork and create a CodeAgent to handle**: when browsing Issues of a custom repository, right-click the Issue and choose "Fork and create a CodeAgent to handle"; the plugin forks the repository, clones it to the selected directory, and creates a CodeAgent in that directory to solve the problem (requires gh to be logged in)

## Default Repository

By default, the gh plugin handles the **GitHub repository corresponding to the current working directory** (auto-resolved by reading git remote origin). To operate on another repository, run `gh repo set-default owner/repo`, or explicitly specify it by adding the `--repo owner/repo` parameter to the command.

- **Switch repository in the sidebar**: the "Switch" button at the top of the sidebar allows manually entering `owner/repo` (pasting a GitHub URL is supported) to view Issues/PRs of other repositories; click "Follow current directory" to restore auto-resolution. A manually specified repository is saved to local storage and remains in effect after a refresh.

## Authentication Method

The plugin reuses the official GitHub `gh` CLI login state (`gh auth login`), reading the token via `gh auth token`, and does not store the token itself.

- **Read operations** (list/view PRs, issues): public repositories are anonymously accessible; no authentication required.
- **Write operations** (merge PRs, comment, close issues): authentication required. Please log in first in the terminal using the official GitHub CLI:

```bash
# Log in (official GitHub CLI)
gh auth login

# Check login status
gh auth status
```

## Common Commands

The Agent directly calls the official GitHub `gh` CLI via `execute_script` to perform GitHub operations; no additional tools are needed:

| Command                              | Description                   | Authentication |
| ------------------------------------ | ----------------------------- | -------------- |
| `gh pr list`                         | List PRs (can filter by state)| Anonymous      |
| `gh pr view <number>`                | View a single PR's details    | Anonymous      |
| `gh pr merge <number>`               | Merge a PR (authentication required) | gh CLI  |
| `gh issue list`                      | List Issues (can filter by state) | Anonymous  |
| `gh issue view <number>`             | View a single Issue's details | Anonymous      |
| `gh issue comment` / `gh pr comment` | Comment on a PR/Issue (authentication required) | gh CLI |
| `gh issue close <number>`            | Close an Issue (authentication required) | gh CLI |

## Plugin Structure

```text
gh/
├── config.yaml          # Plugin configuration (name/version + extension point declarations)
├── README.md
├── rules/               # gh plugin usage rules
├── plugin/              # Plugin private features (api.py + gh_common.py, called by the frontend sidebar)
└── frontend/            # Frontend sidebar view (editor activity bar → GitHub)
```

## Related Code

- Frontend sidebar: calls the GitHub REST API via `plugin/api.py` (`https://api.github.com`)
- Authentication: reuse the official GitHub `gh` CLI login state (`gh auth token`)
