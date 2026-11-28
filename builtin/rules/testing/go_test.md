---
name: go_test
description: Triggered when tests need to be written for a Go project or a test framework needs to be configured. Triggered whenever the user mentions "Go testing", "table-driven tests", "go test". Not triggered: testing non-Go projects; code review; performance optimization.
---

# Go Testing Standards

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

### Standard library testing (no installation required)

**Run commands:**

```bash
go test                 # run all tests in the current package
go test ./...           # run tests for all packages
go test -v              # verbose output
go test -run TestFunc   # run a specific test function
go test -cover          # show coverage
go test -coverprofile=coverage.out # generate a coverage file
```

## Test Cases You Must Write

```go
// calculator_test.go
package calculator

import "testing"

func TestAdd(t *testing.T) {
    result := Add(2, 3)
    if result != 5 {
        t.Errorf("Add(2, 3) = %d; want 5", result)
    }
}

func TestDivideByZero(t *testing.T) {
    _, err := Divide(10, 0)
    if err == nil {
        t.Error("Divide(10, 0) should return error")
    }
}

// Table-driven test (recommended)
func TestAddTable(t *testing.T) {
    tests := []struct {
        a, b, want int
    }{
        {2, 3, 5},
        {0, 0, 0},
        {-1, 1, 0},
    }
    for _, tt := range tests {
        if got := Add(tt.a, tt.b); got != tt.want {
            t.Errorf("Add(%d, %d) = %d; want %d", tt.a, tt.b, got, tt.want)
        }
    }
}
```

## Test File Conventions

### File Naming

- **Must**: Test files end with `_test.go`
- **Must**: Test files are in the same package as the file under test

### Function Naming

- **Must**: Test functions start with `Test`
- **Must**: Test functions accept a `*testing.T` parameter

## Test Execution Checklist

Before committing code, be sure to confirm:

- [ ] **Run tests immediately after writing them**
- [ ] **All tests pass**
- [ ] **If it fails, fix it until it passes**
- [ ] Test files end with `_test.go`
- [ ] Test functions start with `Test`
- [ ] Use table-driven tests to cover multiple scenarios (if applicable)
- [ ] Tests cover the normal, boundary, and exception cases
