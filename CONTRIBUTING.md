# Contributing Guide

Thank you for your interest in and support of the HaijunBot project! HaijunBot is a collaborative AI assistant platform for developers, and we welcome all forms of contribution.

## Code of Conduct

- Respect every contributor and maintain a friendly, professional atmosphere for discussion
- Keep technical discussions focused on the issue itself and avoid personal attacks
- Welcome different viewpoints, using "runnable, testable, maintainable" as the criteria for judgment

## How to Contribute

### Reporting Bugs

1. Search Issues to see whether the same problem has already been reported
2. Provide a clear description of the problem, including:
   - Environment information (operating system, Python version, HaijunBot version)
   - Steps to reproduce
   - Expected behavior and actual behavior
   - Relevant logs or error messages

### Submitting Feature Suggestions

1. Describe the feature requirements and use cases in Issues
2. Explain what problem the feature solves and which users it is intended for
3. For major features, submit an RFC for discussion first

### Submitting Code

1. Fork this repository and create a feature branch
2. Follow the existing code style and conventions
3. Write test cases for new features
4. Make sure all tests pass: `pytest`
5. Submit a Pull Request with a clear description of the changes

## Setting Up the Development Environment

```bash
# Clone the repository
git clone https://gitee.com/takebox/HaijunBot.git
cd HaijunBot

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest
```

## Code Guidelines

- Follow the PEP 8 code style
- Add clear docstrings to functions and classes
- New features must include test cases
- Commit messages should clearly describe the intent of the changes

## Plugin Development

HaijunBot supports extension via plugin packages; for plugin development, please refer to:

- Plugin directory structure: `config.yaml` + plugin code
- Plugin installation: the `install_plugin` command
- Plugin configuration supports Jinja2 template rendering

## Decision-Making Process

- **Routine decisions**: Core maintainers are responsible for PR review and merging
- **Major features**: Go through the RFC process — discuss first, then implement
- **Version releases**: Follow Semantic Versioning (SemVer)

## Contact Us

- Code repository: https://gitee.com/takebox/HaijunBot
- Developer WeChat group: welcome to join the discussion

Thanks again for your contribution!
