---
name: python_test
description: Triggered when tests need to be written for a Python project or a test framework needs to be configured. Triggered whenever the user mentions "Python testing", "pytest", "unittest". Not triggered: testing non-Python projects; code review; performance optimization.
---

# Python Testing Standards

## Key Points

**After writing tests, be sure to run them immediately until all pass!**

### Execution Key Points

- **Must**: Run tests immediately after each code change
- **Must**: If a test fails, fix the code until all pass
- **Forbidden**: Commit code that has not passed
- **Forbidden**: Continue development while tests are failing

### Workflow

1. Write or modify code
2. **Immediately** run tests
3. If it fails, fix it
4. Repeat steps 2-3 until all pass
5. Only after all pass may you commit

## Test Frameworks You Must Use

### pytest (recommended)

**Installation command:**

```bash
pip install pytest pytest-cov
```

**Run commands:**

```bash
pytest           # run all tests
pytest tests/test_file.py # run a specific file
pytest -v        # verbose output
pytest -x        # stop on failure
pytest --cov=src # show coverage
```

### unittest (standard library, no installation required)

**Run commands:**

```bash
python -m unittest discover    # run all tests
python -m unittest -v          # verbose output
```

## Test Cases You Must Write

### pytest test case

```python
import pytest
from src.module import function

def test_function():
    """Test the normal case"""
    assert function(2, 3) == 5

def test_error_case():
    """Test the exception case"""
    with pytest.raises(ValueError):
        function(-1, 0)
```

### unittest test case

```python
import unittest
from src.module import function

class TestModule(unittest.TestCase):
    def test_function(self):
        """Test the normal case"""
        self.assertEqual(function(2, 3), 5)
```

## Test Execution Checklist

Before committing code, be sure to confirm:

- [ ] **Run tests immediately after writing them**
- [ ] **All tests pass**
- [ ] **If it fails, fix it until it passes**
- [ ] Tests cover the normal case
- [ ] Tests cover the boundary case
- [ ] Tests cover the exception case
- [ ] Use meaningful test names
