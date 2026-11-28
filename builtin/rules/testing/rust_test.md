---
name: rust_test
description: Triggered when tests need to be written for a Rust project or a test framework needs to be configured. Triggered whenever the user mentions "Rust testing", "cargo test", "test modules". Not triggered: testing non-Rust projects; code review; performance optimization.
---

# Rust Testing Standards

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

### Standard library test (no installation required)

**Run commands:**

```bash
cargo test               # run all tests
cargo test --lib         # run only library tests
cargo test --bin name    # run tests for a specific binary
cargo test test_name     # run a specific test function
cargo test -- --nocapture # show println! output
cargo test -- --test-threads=1 # run single-threaded
```

## Test Cases You Must Write

```rust
// src/lib.rs or src/calculator.rs
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add() {
        assert_eq!(add(2, 3), 5);
    }

    #[test]
    fn test_divide_by_zero() {
        assert!(divide(10, 0).is_err());
    }

    #[test]
    #[should_panic(expected = "Division by zero")]
    fn test_panic() {
        divide_unchecked(10, 0);
    }
}
```

## Test Module Conventions

### Module Attributes

- **Must**: Test modules use the `#[cfg(test)]` attribute
- **Must**: Test functions use the `#[test]` attribute

### Assertion Macros

- **Must**: Use `assert!` for boolean assertions
- **Must**: Use `assert_eq!` for equality assertions
- **Must**: Use `assert_ne!` for inequality assertions

## Test Execution Checklist

Before committing code, be sure to confirm:

- [ ] **Run tests immediately after writing them**
- [ ] **All tests pass**
- [ ] **If it fails, fix it until it passes**
- [ ] Test modules use the `#[cfg(test)]` attribute
- [ ] Test functions use the `#[test]` attribute
- [ ] Use `assert!`, `assert_eq!`, `assert_ne!` for assertions
- [ ] Tests cover the normal, boundary, and exception cases
