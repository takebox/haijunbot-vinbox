# Security Policy

HaijunBot is a collaborative AI development platform that involves capabilities such as model invocation, command execution, file reading and writing, browser control, and multi-user permissions, so we take security very seriously. If you discover a security vulnerability, please report it responsibly as described below.

## Supported Versions

We recommend always using the latest version. Security fixes are merged into the `main` branch first and released in the next official version (`vX.Y.Z`).

| Version        | Supported                                    |
| -------------- | -------------------------------------------- |
| Latest release | ✅ Supported                                  |
| Old versions   | ⚠️ Only high-risk vulnerabilities with a large impact that are easy to exploit |

## Reporting Vulnerabilities

**Please do not disclose vulnerability details publicly (Issues, Discussions, group chats)**, to avoid malicious exploitation. Please report through a private channel:

1. **Preferred**: In the GitHub repository, use [Private vulnerability reporting](https://github.com/takebox/HaijunBot/security/advisories) to submit a security advisory (if enabled).
2. **Alternative**: Submit via Issues, but please **describe only the type of problem and the scope of impact, without including exploitable details**, and add the `[SECURITY]` prefix before the title. We will respond as soon as possible.

### When Reporting, Please Include

- Affected version (the `__version__` in `src/haijunbot/__init__.py`)
- Type and severity of the vulnerability (e.g., unauthorized access, key leakage, command injection, XSS, etc.)
- Steps to reproduce (as concise and reproducible as possible)
- Scope of impact and potential harm
- (Optional) Suggested fix

## Handling Process

1. After receiving a report, we will confirm it and assess the severity as soon as possible.
2. High-risk vulnerabilities are fixed first, and a patch version is released after the fix is complete.
3. After the fix is released, we will publicly thank the reporter (if you agree).

## Security Notes

When using HaijunBot, please note:

- **Key security**: Do not commit sensitive credentials such as model API keys or gateway node keys to public repositories or write them into files tracked by git.
- **Command execution**: HaijunBot has the ability to execute system commands; please enter them with care, and you can enable `execute_tool_confirm: true` to confirm before execution.
- **Multi-user deployment**: When multi-user authentication is enabled, configure ACL permissions correctly to avoid unauthorized access.
- **Browser extension**: The browser extension has relatively high privileges; use it only in trusted environments.
