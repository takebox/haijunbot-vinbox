# Introducing CodeAgent and Agent into a Project

## 1. Overview

### 1.1 Introduction to CodeAgent and Agent

- **Agent**: HaijunBot's base agent class, providing general AI assistant capabilities including conversation management, tool calling, and memory system.
- **CodeAgent**: Code agent class inheriting from Agent, specifically for code modification, refactoring, and development tasks, providing code analysis, Git operations, code review, etc.

### 1.2 Installation

**Install via pip**:

```bash
pip install haijunbot-ai-assistant
```

**Install from source**:

```bash
git clone https://github.com/your-org/haijunbot.git
cd haijunbot
pip install -e .
```

---

## 2. Using the Python API

### 2.1 Importing Agent and CodeAgent

```python
from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_code_agent.code_agent import CodeAgent
```

### 2.2 Creating CodeAgent Instance

**Basic creation**:

```python
from haijunbot.haijunbot_code_agent.code_agent import CodeAgent

# Create a CodeAgent instance
agent = CodeAgent(
    llm_group="smart",
    non_interactive=False,
    rule_names="clean_code,security"
)

# Execute the task
agent.run("Create user authentication module")
```

**Complete parameter example**:

```python
agent = CodeAgent(
    llm_group="smart",              # Model group
    need_summary=True,                # Whether a summary is needed
    non_interactive=False,            # Whether non-interactive mode
    rule_names="clean_code,security", # Rule names (comma-separated)
    disable_review=False,             # Whether to disable code review
    review_max_iterations=3,          # Maximum code review iterations
    enable_task_list_manager=True,    # Whether to enable the task list manager
    use_methodology=True,              # Whether to use methodology
    use_analysis=True                 # Whether to use analysis
)
```

### 2.3 Creating Agent Instance

**Basic creation**:

```python
from haijunbot.haijunbot_agent import Agent

# Create an Agent instance
agent = Agent(
    llm_group="smart",
    system_prompt="You are a helpful AI assistant",
    use_tools=["search_web", "read_file"]
)

# Execute the task
agent.run("Search for Python best practices")
```

**Complete parameter example**:

```python
agent = Agent(
    llm_group="smart",              # Model group
    system_prompt="You are a helpful AI assistant",  # System prompt
    use_tools=["search_web", "read_file"],    # Tool list
    need_summary=True,                # Whether a summary is needed
    non_interactive=False,            # Whether non-interactive mode
    use_methodology=True,             # Whether to use methodology
    use_analysis=True                 # Whether to use analysis
)
```

### 2.4 Using in Projects

**Example 1: Using CodeAgent in a script**

```python
#!/usr/bin/env python3
"""Use CodeAgent to automatically generate code"""

from haijunbot.haijunbot_code_agent.code_agent import CodeAgent

def main():
    # Create CodeAgent
    agent = CodeAgent(
        llm_group="smart",
        non_interactive=True,
        rule_names="clean_code,security"
    )
    
    # Execute the task
    task = """
    Create a user authentication module:
    1. Implement user registration
    2. Implement user login
    3. Add JWT token generation
    4. Write unit tests
    """
    
    agent.run(task)

if __name__ == "__main__":
    main()
```

**Example 2: Using in CI/CD**

```python
#!/usr/bin/env python3
"""Use CodeAgent to automatically fix code in CI/CD"""

from haijunbot.haijunbot_code_agent.code_agent import CodeAgent

def auto_fix_code():
    agent = CodeAgent(
        llm_group="smart",
        non_interactive=True,
        rule_names="code_review"
    )
    
    task = """
    Review and fix issues in the code:
    1. Fix lint errors
    2. Fix type annotation issues
    3. Fix security vulnerabilities
    """
    
    agent.run(task)

if __name__ == "__main__":
    auto_fix_code()
```

**Example 3: Using Agent in tests**

```python
"""Use Agent for test assistance"""

from haijunbot.haijunbot_agent import Agent

def test_with_agent():
    agent = Agent(
        llm_group="smart",
        use_tools=["read_file", "execute_script"]
    )
    
    # Use Agent to analyze test results
    result = agent.run("Analyze test output and find failing test cases")
    return result
```
