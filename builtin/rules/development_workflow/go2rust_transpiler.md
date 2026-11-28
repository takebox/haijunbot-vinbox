---
name: go2rust_transpiler
description: Triggered when Go code needs to be converted to Rust code. Triggered whenever the user mentions "Go to Rust", "convert Go to Rust", or "Go migration". Not triggered: compiling Rust code only without Go transpilation; merely reading Go code without transpiling; C/C++ to Rust transpilation.
---

# Go2Rust Transpilation Rules

## Rule Introduction

Used to guide the code transpilation process from Go to Rust, preserving transpilation quality, functional consistency, and type safety. This rule covers the complete transpilation process from planning, implementation, build, review, optimization, to evaluation.

⚠

**Supported language features:**

- **Go language**: functions, structs, interfaces, methods, goroutines, channels, slices, maps, error handling, defer, packages, go modules, etc.
- **Concurrency model**: goroutines, channels, select, sync.WaitGroup, sync.Mutex, sync.RWMutex, etc.
- **Standard library**: strings, bytes, io, fmt, context, time, net, etc.

## Principles You Must Follow

### 1. Task Management Principle (Core)

**Requirement description:**

- **Must**: the transpilation process of every function must use `task_list_manager` to manage tasks
- **Must**: before starting transpilation, create a task list and plan all tasks (planning, implementation, build, review, optimization, evaluation)
- **Must**: use the `add_tasks` operation of task_list_manager to add all subtasks
- **Must**: set task dependencies according to the dependency relationships (e.g., the implementation phase depends on the planning phase)
- **Forbidden**: skipping task_list_manager and executing tasks directly

**Multi-level task list requirements:**

Go to Rust transpilation is a complex process; different levels of task lists need to be created according to the scale of transpilation:

1. **Directory-level task list** (as needed)
   - **When needed**: when transpiling an entire directory or multiple related directories
   - **Task content**: plan the directory structure, module organization, dependency relationships, etc.
   - **Subtasks**: include the transpilation tasks for all files under that directory
   - **Example scenario**: transpile all Go files (`.go`) under the `pkg/utils/` directory

2. **File-level task list** (as needed)
   - **When needed**: when transpiling a single file or multiple related functions/structs
   - **Task content**: plan the file module location, function/struct organization, shared type definitions, etc.
   - **Subtasks**: include the transpilation tasks for all functions/structs in that file
   - **Example scenario**:
     - Transpile all hash-related functions and structs in the `hash.go` file
     - Transpile the HTTP handler structs in the `http_handler.go` file

3. **Function/struct-level task list** (mandatory)
   - **When needed**: when transpiling a single function or struct (this is the smallest granularity and must be created)
   - **Task content**: plan the function/struct signature, implementation strategy, test cases, etc.
   - **Subtasks**: include the planning, implementation, build, review, optimization, and evaluation for that function/struct
   - **Example scenario**:
     - Transpile a single function `calculateHash`
     - Transpile a single struct `HTTPServer` and its methods

**Task list hierarchy:**

- Directory-level task list → File-level task list → Function/struct-level task list
- The subtasks of a higher-level task list can be lower-level task lists
- If transpiling only a single function, only a function-level task list needs to be created
- If transpiling multiple functions but they belong to the same file, a file-level task list can be created, containing multiple function-level subtasks
- If transpiling multiple files, a directory-level task list can be created, containing multiple file-level subtasks

**Task list requirements:**

- Task type: use the `sub` type for complex tasks and the `main` type for simple tasks
- Task description: each task should include constraints, requirements, prohibitions, and verification criteria
- Expected output: expected output must be listed in a structured format
- Verification method: after task completion, a verification method description must be provided
- **Go code location information**: **Must** include the line number location information of the original Go code in each subtask
  - Function/struct-level task: should include the file path and line number range where the Go function/struct is located
    - Go: `path/to/file.go:42-67`
  - File-level task: should include the path of the Go file (`.go`)
  - Directory-level task: should include the path of the Go directory (e.g., `path/to/dir/`)
  - Location information should be included in the `background` field or the `task_desc` field

#### Example 1: Function-level task list (mandatory)

```json
// ✅ Correct: function-level task list (with Go code line number location information)
{
  "action": "add_tasks",
  "main_goal": "Transpile function Foo",
  "background": "The Go function Foo is located at path/to/foo.go:42-67, and its functionality is...",
  "tasks_info": [
    {
      "task_name": "Planning phase",
      "task_desc": "Select a module location and design the Rust signature for function Foo (path/to/foo.go:42-67)...",
      "expected_output": "- Module path: src/foo.rs\n- Rust signature: pub fn foo(...) ...\n- Go code location: path/to/foo.go:42-67\n- Planning document: docs/transpilation/foo_planning.md",
      "agent_type": "sub",
      "dependencies": []
    },
    {
      "task_name": "Implementation phase",
      "task_desc": "Implement function Foo (path/to/foo.go:42-67) using the TDD method...",
      "expected_output": "- Test cases written\n- Implementation completed\n- Go code location: path/to/foo.go:42-67\n- Implementation document: docs/transpilation/foo_implementation.md",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Build phase",
      "task_desc": "Run cargo test and fix build issues (transpiled from path/to/foo.go:42-67)...",
      "expected_output": "- All tests pass\n- No compilation errors\n- Go code location: path/to/foo.go:42-67\n- Build document: docs/transpilation/foo_build.md",
      "agent_type": "sub",
      "dependencies": ["Implementation phase"]
    },
    {
      "task_name": "Review phase",
      "task_desc": "Review code quality, functional consistency, and test completeness (transpiled from path/to/foo.go:42-67)...",
      "expected_output": "- Review report\n- Issue list\n- Go code location: path/to/foo.go:42-67\n- Review document: docs/transpilation/foo_review.md",
      "agent_type": "sub",
      "dependencies": ["Build phase"]
    },
    {
      "task_name": "Optimization phase",
      "task_desc": "Fix the issues found in review and verify (transpiled from path/to/foo.go:42-67)...",
      "expected_output": "- Issues fixed\n- All tests pass\n- Go code location: path/to/foo.go:42-67\n- Optimization document: docs/transpilation/foo_optimization.md",
      "agent_type": "sub",
      "dependencies": ["Review phase"]
    },
    {
      "task_name": "Evaluation phase",
      "task_desc": "Use a sub-agent to evaluate the overall effect and check functional alignment (transpiled from path/to/foo.go:42-67)...",
      "expected_output": "- Evaluation report\n- Functional alignment check results\n- If there are issues, create optimization subtasks\n- Go code location: path/to/foo.go:42-67\n- Evaluation document: docs/transpilation/foo_evaluation.md",
      "agent_type": "sub",
      "dependencies": ["Optimization phase"]
    }
  ]
}
```

#### Example 2: File-level task list (as needed)

```json
// ✅ Correct: file-level task list (transpile the hash.go file, with Go code line number location information)
{
  "background": "The Go file hash.go contains multiple hash-related functions: HashInit (hash.go:15-45), HashUpdate (hash.go:47-78), HashFinal (hash.go:80-110)...",
  "tasks_info": [
    {
      "task_name": "Planning phase",
      "task_desc": "Plan the module location and overall structure of hash.go...",
      "expected_output": "- Module path: src/hash.rs\n- Shared type definitions\n- Function group plan\n- Go file location: hash.go",
      "agent_type": "sub",
      "dependencies": []
    },
    {
      "task_name": "Transpile function HashInit",
      "task_desc": "Transpile function HashInit (hash.go:15-45) (including planning, implementation, build, review, optimization, evaluation)...",
      "expected_output": "- HashInit function transpilation completed\n- Tests pass\n- Functional alignment verification passes\n- Go code location: hash.go:15-45",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Transpile function HashUpdate",
      "task_desc": "Transpile function HashUpdate (hash.go:47-78) (including planning, implementation, build, review, optimization, evaluation)...",
      "expected_output": "- HashUpdate function transpilation completed\n- Tests pass\n- Functional alignment verification passes\n- Go code location: hash.go:47-78",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Transpile function HashFinal",
      "task_desc": "Transpile function HashFinal (hash.go:80-110) (including planning, implementation, build, review, optimization, evaluation)...",
      "expected_output": "- HashFinal function transpilation completed\n- Tests pass\n- Functional alignment verification passes\n- Go code location: hash.go:80-110",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "File-level integration test",
      "task_desc": "Run file-level integration tests to ensure all functions work together (transpiled from hash.go)...",
      "expected_output": "- Integration tests pass\n- File transpilation completed\n- Go file location: hash.go",
      "agent_type": "sub",
      "dependencies": [
        "Transpile function HashInit",
        "Transpile function HashUpdate",
        "Transpile function HashFinal"
      ]
    }
  ]
}
```

#### Example 3: Directory-level task list (as needed)

```json
// ✅ Correct: directory-level task list (transpile the pkg/utils/ directory, with Go code line number location information)
{
  "action": "add_tasks",
  "main_goal": "Transpile directory pkg/utils/",
  "background": "The Go directory pkg/utils/ contains multiple utility files: string.go, math.go, memory.go...",
  "tasks_info": [
    {
      "task_name": "Planning phase",
      "task_desc": "Plan the directory structure, module organization, and dependency relationships (transpiled from pkg/utils/)...",
      "expected_output": "- Rust module structure plan\n- Dependency graph\n- Transpilation order\n- Go directory location: pkg/utils/",
      "agent_type": "sub",
      "dependencies": []
    },
    {
      "task_name": "Transpile file string.go",
      "task_desc": "Transpile the string.go file (including all functions and structs in that file, located at pkg/utils/string.go)...",
      "expected_output": "- string.go transpilation completed\n- All functions and structs pass tests\n- Functional alignment verification passes\n- Go file location: pkg/utils/string.go",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Transpile file math.go",
      "task_desc": "Transpile the math.go file (including all functions and structs in that file, located at pkg/utils/math.go)...",
      "expected_output": "- math.go transpilation completed\n- All functions and structs pass tests\n- Functional alignment verification passes\n- Go file location: pkg/utils/math.go",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Transpile file memory.go",
      "task_desc": "Transpile the memory.go file (including all functions and structs in that file, located at pkg/utils/memory.go)...",
      "expected_output": "- memory.go transpilation completed\n- All functions and structs pass tests\n- Functional alignment verification passes\n- Go file location: pkg/utils/memory.go",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Directory-level integration test",
      "task_desc": "Run directory-level integration tests to ensure all modules work together (transpiled from pkg/utils/)...",
      "expected_output": "- Integration tests pass\n- Directory transpilation completed\n- Go directory location: pkg/utils/",
      "agent_type": "sub",
      "dependencies": [
        "Transpile file string.go",
        "Transpile file math.go",
        "Transpile file memory.go"
      ]
    }
  ]
}
```

```bash
# ❌ Wrong: executing directly without using task_list_manager
echo "Starting to transpile function Foo"
# Directly writing code without task management
```

### 2. TDD Development Principle

**Requirement description:**

- **Must**: write tests first (#[cfg(test)] mod tests), designing test cases based on the behavior of the Go function/struct
- **Must**: write the implementation to make tests pass, ensuring semantic equivalence with Go
- **Must**: optimize the code while keeping tests passing (refactoring phase)
- **Forbidden**: writing the implementation code directly without tests
- **Forbidden**: using `todo!` or `unimplemented!` as placeholders

**Go-specific considerations:**

- Struct methods need to be tested separately for the public interface and the private implementation (through the public interface)
- Interface methods need to be tested against different implementation types
- Concurrent code needs to be tested for goroutine synchronization and communication behavior
- Error handling needs to be tested for different error cases (Go's error return value)
- Defer statements need to be tested for resource cleanup behavior

**Example:**

```rust
// ❌ Wrong: write the implementation first
pub fn calculate(x: i32) -> i32 {
    x * 2
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_calculate() { }
}
```

```rust
// ✅ Correct: write the test first
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_normal() {
        assert_eq!(calculate(5), 10);
    }

    #[test]
    fn test_calculate_zero() {
        assert_eq!(calculate(0), 0);
    }
}

pub fn calculate(x: i32) -> i32 {
    x * 2
}
```

### 3. Functional Consistency Principle

**Requirement description:**

- **Must**: define core functionality consistent with the Go implementation (main purpose and expected behavior)
- **Allowed**: behavioral inconsistency caused by security improvements (fixing nil pointer dereferences, data races, and other security vulnerabilities)
- **Ignored**: behavioral inconsistency caused by language differences (panic recovery, goroutine scheduling, etc.)
- **Allowed**: using different type design, error handling, and resource management approaches
- **Forbidden**: changing the core functional logic

**Note:** Core functionality refers to the main purpose of the function/struct (e.g., "compute a hash value", "parse a string", "manage HTTP connections"), and does not include implementation details.

**Go-specific considerations:**

- Struct encapsulation: keep the public interface consistent (Go exports via capitalized first letter); internal implementations may differ
- Interface relationships: keep the interface definition and implementation methods consistent
- Concurrency model: keep concurrent behavior consistent, but different concurrency primitives may be used
- Error handling: Go's multiple return values (value, error) can be converted to Rust's Result<T, E>
- Defer semantics: Rust's Drop trait can be used to implement similar resource cleanup

### 4. Modular Design Principle

**Requirement description:**

- **Must**: select modules by functional cohesion and dependency direction, avoiding circular dependencies
- **Must**: module paths must be located under the crate's src/ directory
- **Must**: prioritize placing functions into already existing modules
- **Allowed**: create new submodule files when necessary
- **Forbidden**: placing unrelated functionality in the same module

**Go-specific considerations:**

- Go's package (e.g., `package main`, `package utils`) maps to Rust's module
- Go's import paths (e.g., `github.com/user/repo/pkg`) map to Rust's dependency management (Cargo.toml)
- Go's internal packages (internal) map to Rust's private modules

### 5. Type Safety Principle

**Requirement description:**

- **Must**: prioritize Rust native types (i32/u32, &str/String, &[T]/&mut [T], Result<T,E>)
- **Forbidden**: prioritizing Go-style types (empty interface interface{}, reflection reflect)
- **Forbidden**: using extern "C" (unless required for FFI export)
- **Must**: function signatures should follow Rust best practices and do not need to be compatible with Go's data types
- **Forbidden**: using `use ...::*` wildcard imports

### 6. Documentation Principle

**Requirement description:**

- **Must**: generate documentation for every transpilation phase
- **Must**: the documentation should include the phase's execution process, decision basis, and the problems encountered and their solutions
- **Must**: the documentation should include Go code location information for traceability
- **Must**: the documentation should use a structured format (Markdown) for readability and maintainability
- **Must**: the documentation should be generated immediately after the phase is completed to ensure the information is accurate and complete
- **Forbidden**: skipping the documentation and directly entering the next phase

**Documentation requirements:**

- Document format: use Markdown format
- Document location: recommended to be stored under the `docs/transpilation/` directory, organized by function/file/directory
- Document name: use clear naming rules (e.g., `function_name_planning.md`, `file_name_implementation.md`)
- Document content: should include the phase overview, execution process, key decisions, problems and solutions, and verification results
- Document links: include the document path in the expected output of the task list

## Operations You Must Perform

**Important note:** Before starting transpilation, you must select the appropriate task list level according to the scale of transpilation:

- **Transpile a single function**: create a function-level task list (mandatory)
- **Transpile a single file or multiple related functions**: create a file-level task list, containing multiple function-level subtasks (as needed)
- **Transpile an entire directory or multiple related directories**: create a directory-level task list, containing multiple file-level subtasks (as needed)

The following operation phases apply to task lists at all levels, but the specific execution granularity depends on the task list level.

### Phase 1: Planning Phase

#### Operation 1: Record Go Code Location Information

- **Must**: record the location information of the original Go code
  - Function/struct level: record the file path and line number range where the Go function/struct is located
    - Go: `path/to/file.go:42-67`
  - File level: record the full path of the Go file (`.go`)
  - Directory level: record the path of the Go directory (e.g., `path/to/dir/`)
- **Must**: include the location information in the task description, background information, or expected output
- **Must**: keep the location information accurate for subsequent traceability and verification

#### Operation 2: Select the Module Location

- Analyze the functional characteristics of the function and determine the functional module it belongs to
- Check the crate directory structure, and select or create an appropriate module file
- Ensure the module path is located under the src/ directory
- Evaluate whether a new submodule file needs to be created

#### Operation 3: Design the Rust Function/Struct/Trait Signature

- Design the Rust function/struct/trait signature based on the Go function/struct signature
- Prioritize Rust native types and avoid Go-style types
- Consider using `Result<T, E>` or `Option<T>` for error handling
- If it is a root symbol, the `pub` keyword must be used
- **Must**: record the corresponding Go code location information in the function/struct comment (e.g., `/// Transpiled from path/to/file.go:42-67`)

**Go-specific handling:**

- **Struct to struct**: Go structs convert to Rust structs, with fields keeping similar names
- **Method to impl**: Go struct methods convert to methods in a Rust impl block
- **Interface to trait**: Go interfaces convert to Rust traits
- **Embedded field to composition**: Go embedded fields convert to Rust composition or traits
- **goroutines to async**: Go goroutines convert to Rust async/await (if using the Tokio runtime)
- **channels conversion**: Go channels convert to Rust `std::sync::mpsc` (synchronous) or `tokio::sync::mpsc` (asynchronous)
- **Multiple return values conversion**: Go multiple return values (value, error) convert to Rust `Result<T, E>` or tuples
- **slices mapping**: Go slices convert to Rust `&[T]` / `Vec<T>`
- **maps mapping**: Go maps convert to Rust `HashMap<K, V>`
- **nil handling**: Go nil pointers/interfaces convert to Rust `Option<T>`

#### Operation 4: Evaluate Whether Implementation Is Needed

Implementation can be skipped in the following cases (set skip_implementation to true):

- **Already implemented functions/structs**: the function/struct is already implemented in the target module and its functionality is consistent with the Go implementation
- **Resource release functions**: such as Close and defer resource cleanup, which are automatically managed via the Drop trait
- **Already replaced by a library**: the function/struct has been replaced by the standard library or a third-party crate with fully consistent functionality
- **Empty implementations or meaningless functions**: the Go function is an empty implementation or simply returns a constant
- **Test helper functions**: Go's test helper functions (e.g., `TestMain`) have a corresponding test framework in Rust

**Important**: skipping the implementation should be explained in detail in the notes field.

#### Operation 5: Generate the Planning Phase Document

- **Must**: generate the planning phase documentation
- **Must**: the documentation contains the following content:
  - Go code location information (file path and line number range)
  - Module selection decision and rationale
  - Design description of the Rust function signature
  - Implementation necessity assessment result
  - Key design decisions and considerations
- **Must**: store the documentation in the specified location (e.g., `docs/transpilation/<function_name>_planning.md`)
- **Must**: include the document path in the task's expected output

### Phase 2: Implementation Phase

#### Operation 1: Write Test Cases

- Write tests in the `#[cfg(test)] mod tests { ... }` block
- Test cases must cover:
  - Main functionality paths
  - Boundary cases (empty input, extreme values, boundary values)
  - Error cases (if the Go implementation has error handling)
- The expected results of the test cases must be consistent with the behavior of the Go implementation
- Use clear test names and appropriate assertions

**Go-specific test requirements:**

- **Struct tests**: test all public methods, including constructors, field accessors, and mutators
- **Interface tests**: test all methods of the interface, including different implementation types
- **Concurrency tests**: test goroutine concurrent behavior and synchronization primitives (WaitGroup, Mutex, Channel)
- **Error handling tests**: Go's error return values convert to Rust's Result, requiring corresponding tests
- **defer tests**: test resource cleanup behavior (using the Drop trait)
- **nil handling tests**: test the equivalent behavior of nil pointers/interfaces (Option::None)

#### Operation 2: Implement the Function/Struct/Trait

- Make the tests pass, implementing functionality semantically equivalent to Go
- Use Rust native types and idioms
- Consider using RAII to manage resources
- Add Chinese comments to explain the logic

**Go-specific implementation requirements:**

- **Struct implementation**: convert Go structs to Rust structs, with fields keeping similar names (using snake_case)
- **Method implementation**: convert Go struct methods to methods in a Rust impl block
- **Interface implementation**: use Rust traits to implement Go interfaces, implementing the trait for structs
- **goroutine implementation**: if concurrency is used, consider Tokio async/await
- **channel implementation**:
  - Unbuffered channel → `tokio::sync::mpsc::channel(0)`
  - Buffered channel → `tokio::sync::mpsc::channel(capacity)`
- **WaitGroup implementation**: use `tokio::task::JoinSet` or `Barrier`
- **Mutex implementation**: use `std::sync::Mutex` or `tokio::sync::Mutex`
- **select implementation**: use the `tokio::select!` macro
- **defer implementation**: use the `Drop` trait or the `scopeguard` pattern
- **Error handling implementation**:
  - Go's `value, error` → Rust's `Result<T, E>`
  - Go's `nil error` → Rust's `Ok(value)`
  - Go's `non-nil error` → Rust's `Err(error)`
- **panic/recover implementation**: use `panic!` and `catch_unwind`

#### Operation 3: Refactor the Code

- Optimize the code structure while keeping tests passing
- Improve code readability and maintainability
- Ensure functional behavior is not changed

#### Operation 4: Generate the Implementation Phase Document

- **Must**: generate the implementation phase documentation
- **Must**: the documentation contains the following content:
  - Go code location information (file path and line number range)
  - Test case design description and coverage
  - Implementation strategy and key implementation details
  - Implementation difficulties encountered and their solutions
  - Refactoring description and improvement points
  - Code change summary
- **Must**: store the documentation in the specified location (e.g., `docs/transpilation/<function_name>_implementation.md`)
- **Must**: include the document path in the task's expected output

### Phase 3: Build Phase

#### Operation 1: Run cargo test

- Ensure all test cases pass
- Fix compilation errors and test failures
- If the fixes cause other tests to fail, they must all be fixed as well

#### Operation 2: Fix Build Issues

- Handle compilation errors (type mismatches, missing dependencies, etc.)
- Handle test failures (assertion errors, panics, etc.)
- Minimize changes and avoid unrelated refactoring
- Use precise use statements and forbid wildcard imports

#### Operation 3: Generate the Build Phase Document

- **Must**: generate the build phase documentation
- **Must**: the documentation contains the following content:
  - Go code location information (file path and line number range)
  - Build process record (compilation commands, test commands)
  - Build issues encountered and error messages
  - Problem analysis and solutions
  - Verification results after the fixes
  - Build time statistics (if applicable)
- **Must**: store the documentation in the specified location (e.g., `docs/transpilation/<function_name>_build.md`)
- **Must**: include the document path in the task's expected output

### Phase 4: Review Phase

**Review priorities:**

1. **Test-breaking check** (highest priority)
   - Check whether the `#[test]` markers are lost
   - Check whether the `#[test]` markers are duplicated
   - Check whether the code insertion location breaks the test structure
   - Verify that the tests can still run

2. **Serious issue check**
   - Null pointer dereference risk
   - Out-of-bounds access issues
   - Serious errors that cause panics
   - Data race risk (during goroutine conversion)

3. **Test case completeness check**
   - Whether there are test cases
   - Whether the main functionality is covered
   - Whether boundary cases are covered
   - Whether error cases are covered

4. **Functional consistency check**
   - Whether the core inputs and outputs are consistent
   - Whether the main functional logic is consistent
   - Behavioral inconsistency caused by security improvements is allowed
   - **Go-specific**:
     - Whether the struct's public interface is consistent
     - Whether the interface methods are fully implemented
     - Whether the concurrent behavior is kept consistent
     - Whether error handling is correctly converted

5. **Breaking change detection**
   - Check module export changes
   - Check type definition changes
   - Signature inconsistency is allowed (as long as functionality is implemented)

6. **File structure reasonableness check**
   - Whether the module file location is reasonable
   - Whether the file name conforms to the specification
   - Whether the module exports are correct

**Operation:** Based on the review results, provide a detailed problem description, fix suggestions, and fix code examples.

#### Operation: Generate the Review Phase Document

- **Must**: generate the review phase documentation
- **Must**: the documentation contains the following content:
  - Go code location information (file path and line number range)
  - Review scope and methods
  - Review results summary (classified by priority)
  - List of discovered problems (detailed description, severity, scope of impact)
  - Fix suggestions and code examples
  - Review conclusion and improvement direction
- **Must**: store the documentation in the specified location (e.g., `docs/transpilation/<function_name>_review.md`)
- **Must**: include the document path in the task's expected output

### Phase 5: Optimization Phase

#### Operation 1: Fix the Problems Found in Review

- Fix problems by priority (serious problems > functional consistency problems > other problems)
- Minimize changes and avoid unrelated refactoring
- After fixing, cargo test must be re-run to verify

#### Operation 2: Verify That All Tests Pass

- Ensure the current function's tests pass
- Ensure other functions' tests have not failed due to the changes
- If regression problems are introduced, they must all be fixed as well

#### Operation 3: Generate the Optimization Phase Document

- **Must**: generate the optimization phase documentation
- **Must**: the documentation contains the following content:
  - Go code location information (file path and line number range)
  - List and priority of optimized problems
  - The fix plan and execution process for each problem
  - Verification results after the fixes
  - Regression test results
  - Optimization effect summary
- **Must**: store the documentation in the specified location (e.g., `docs/transpilation/<function_name>_optimization.md`)
- **Must**: include the document path in the task's expected output

### Phase 6: Evaluation Phase

**Important note:** The evaluation phase must use a sub-agent for independent evaluation to ensure objectivity and comprehensiveness.

#### Operation 1: Use a Sub-agent to Evaluate the Overall Effect

- **Must**: use a sub-agent (`agent_type: "sub"`) to independently evaluate the transpilation result
- **Must**: the evaluation scope includes:
  - Functional alignment check: compare whether the core functionality of the Go implementation and the Rust implementation is consistent
  - Test coverage check: whether the test cases sufficiently cover the behavior of the Go function/struct
  - Boundary case check: whether the boundary conditions and error handling are consistent with the Go implementation
  - Performance impact assessment: whether the performance of the Rust implementation meets requirements (if applicable)
  - Code quality assessment: code readability, maintainability, type safety
  - **Go-specific**:
    - Whether the struct's encapsulation is maintained
    - Whether the interface implementation is complete
    - Whether the concurrent behavior is consistent (goroutine, channel, mutex)
    - Whether error handling is correctly converted (error return value → Result)
    - Whether the defer semantics are correctly implemented (Drop trait)
- **Must**: generate a detailed evaluation report, including:
  - Evaluation scope and methods
  - Functional alignment check results (item-by-item comparison)
  - List of discovered problems (if any)
  - Improvement suggestions (if any)
- **Must**: store the evaluation report as a document (e.g., `docs/transpilation/<function_name>_evaluation.md`)
- **Must**: include the document path in the task's expected output

#### Operation 2: Handle Functional Misalignment Problems

- **Must**: if the evaluation discovers functional misalignment problems, an optimization subtask must be created
- **Must**: the optimization subtask should include:
  - Problem description: explain in detail the specific manifestation of the functional misalignment
  - Alignment target: clarify the functional points that need to be aligned
  - Fix plan: formulate a fix plan and verification method
  - Dependency relationships: depends on the evaluation phase
- **Must**: execute the optimization subtask and fix the functional alignment problems
- **Must**: after fixing, re-perform the evaluation until the functionality is fully aligned

#### Operation 3: Iterate Optimization Until Fully Aligned

- **Must**: if the re-evaluation still discovers functional misalignment, continue to create optimization subtasks
- **Must**: repeat the "optimization → evaluation" loop until:
  - All functional alignment checks pass
  - The evaluation report confirms that the functionality is fully aligned
  - All test cases pass
- **Forbidden**: ending the transpilation task when the functionality is not fully aligned

**Evaluation report template:**

```markdown
## Transpilation Evaluation Report

### Evaluation Scope

- Transpilation target: [function name/struct name/file name/directory name]
- Go code location: [file path:line number range] (e.g., path/to/file.go:42-67)
- Evaluation time: [timestamp]
- Evaluation method: [evaluation method used]

### Functional Alignment Check Results

1. [functionality point 1]: ✅ Aligned / ❌ Not aligned
   - Go implementation location: [file path:line number range]
   - Go implementation behavior: [description]
   - Rust implementation location: [file path:line number range]
   - Rust implementation behavior: [description]
   - Difference analysis: [explain the reason if there is a difference]

2. [functionality point 2]: ✅ Aligned / ❌ Not aligned
   - Go implementation location: [file path:line number range]
     ...

### Test Coverage Check

- Main functionality paths: ✅ Covered / ❌ Not covered
- Boundary cases: ✅ Covered / ❌ Not covered
- Error cases: ✅ Covered / ❌ Not covered
- **Go-specific**:
  - All public methods of the struct: ✅ Covered / ❌ Not covered
  - All methods of the interface: ✅ Covered / ❌ Not covered
  - Concurrent behavior (goroutine, channel): ✅ Covered / ❌ Not covered
  - Error handling (error → Result): ✅ Covered / ❌ Not covered

### Discovered Problems

1. [problem 1]: [detailed description]
2. [problem 2]: [detailed description]
   ...

### Improvement Suggestions

1. [suggestion 1]: [detailed explanation]
2. [suggestion 2]: [detailed explanation]
   ...

### Conclusion

- Functional alignment status: ✅ Fully aligned / ❌ Partially aligned / ❌ Not aligned
- Whether optimization is needed: yes / no
- Next action: [concrete action]
```

**Phase document template:**

The document for each phase should follow the basic structure below:

```markdown
# [Phase name] Document - [function name/struct name/file name/directory name]

## Basic Information

- Go code location: [file path:line number range] (e.g., path/to/file.go:42-67)
- Transpilation target: [function name/struct name/file name/directory name]
- Phase: [planning/implementation/build/review/optimization/evaluation]
- Execution time: [timestamp]
- Executor: [agent name]

## Phase Overview

[briefly describe the goal and main work of this phase]

## Execution Process

[record the execution steps and process in detail]

## Key Decisions

1. [decision 1]: [decision content and rationale]
2. [decision 2]: [decision content and rationale]
   ...

## Problems and Solutions

1. [problem 1]: [problem description]
   - Solution: [solution]
   - Result: [resolution result]
2. [problem 2]: [problem description]
   ...

## Verification Results

- [verification item 1]: ✅ Pass / ❌ Fail
- [verification item 2]: ✅ Pass / ❌ Fail
  ...

## Summary

[phase summary and next-step plan]
```

## Go Language Feature to Rust Mapping Table

### 1. Concurrency Model Mapping

| Go feature        | Rust equivalent                     | Notes                                    |
| ----------------- | ----------------------------------- | ---------------------------------------- |
| `go func()`       | `tokio::spawn(async move { ... })`  | Requires the Tokio runtime               |
| `chan T`          | `tokio::sync::mpsc::channel<T>`     | Async channel; use `std::sync::mpsc` for sync |
| `<-chan`          | `receiver.recv()`                   | Receive operation                        |
| `chan<-`          | `sender.send()`                     | Send operation                           |
| `close(chan)`     | `drop(sender)`                      | In Rust, dropping the sender closes automatically |
| `select`          | `tokio::select!`                    | Multiplexing                             |
| `sync.WaitGroup`  | `tokio::task::JoinSet` or `Barrier` | Wait for multiple tasks to complete      |
| `sync.Mutex`      | `std::sync::Mutex`                  | Mutex                                    |
| `sync.RWMutex`    | `std::sync::RwLock`                 | Read-write lock                          |
| `sync.Once`       | `std::sync::OnceLock`               | One-time initialization                  |
| `context.Context` | `tokio::task::CancellationToken`    | Cancellation context                     |

### 2. Type System Mapping

| Go type       | Rust equivalent                        | Notes          |
| ------------- | -------------------------------------- | -------------- |
| `int`         | `i32` or `isize`                       | Chosen based on platform |
| `int32`       | `i32`                                  | Fixed size     |
| `int64`       | `i64`                                  | Fixed size     |
| `uint`        | `u32` or `usize`                       | Chosen based on platform |
| `float32`     | `f32`                                  | Single-precision float |
| `float64`     | `f64`                                  | Double-precision float |
| `string`      | `String` or `&str`                     | Ownership vs borrow |
| `[]T`         | `Vec<T>` or `&[T]`                     | Dynamic array  |
| `[N]T`        | `[T; N]`                               | Fixed-size array |
| `map[K]V`     | `HashMap<K, V>`                        | Hash map       |
| `*T`          | `&T` or `Box<T>`                       | Pointer/heap allocation |
| `nil`         | `None`                                 | Null value     |
| `interface{}` | `dyn Any`                              | Type erasure   |
| `error`       | `Result<T, E>`                         | Error handling |
| `chan T`      | `mpsc::Sender<T>`, `mpsc::Receiver<T>` | Channel        |

### 3. Struct and Method Mapping

| Go feature                 | Rust equivalent                  | Notes             |
| -------------------------- | -------------------------------- | ----------------- |
| `type T struct { ... }`    | `struct T { ... }`               | Struct definition |
| `func (t *T) Method() {}`  | `impl T { fn method(&self) {} }` | Method definition |
| `func (t T) Method() {}`   | `impl T { fn method(self) {} }`  | Value receiver method |
| `type T interface { ... }` | `trait T { ... }`                | Interface/trait   |
| `type U struct { T }`      | `struct U { t: T }`              | Embedded struct → composition |
| `type U struct { *T }`     | `struct U { t: Box<T> }`         | Pointer embedding |

### 4. Function Mapping

| Go feature                                  | Rust equivalent            | Notes             |
| ------------------------------------------- | -------------------------- | ----------------- |
| `func foo() {}`                             | `fn foo() {}`              | Function definition |
| `func foo() (T, error)`                     | `fn foo() -> Result<T, E>` | Multiple return values → Result |
| `func foo() (T, error) { return T{}, nil }` | `Ok(T{})`                  | Successful return |
| `func foo() (T, error) { return T{}, err }` | `Err(err)`                 | Error return      |
| `func foo() (T, T)`                         | `fn foo() -> (T, T)`       | Multi-value return tuple |
| `vararg ...T`                               | `fn foo(args: &[T])`       | Variadic parameters |
| `func foo(f func())`                        | `fn foo<F: Fn()>(f: F)`    | Function as a parameter |
| `func foo() func()`                         | `fn foo() -> impl Fn()`    | Function as a return value |

### 5. Control Flow Mapping

| Go feature                 | Rust equivalent                                | Notes        |
| -------------------------- | ---------------------------------------------- | ------------ |
| `if err != nil { ... }`    | `match result { Ok(v) => ..., Err(e) => ... }` | Error handling |
| `defer f()`                | `Drop trait` or `scopeguard`                   | Deferred execution |
| `panic("msg")`             | `panic!("msg")`                                | Panic        |
| `recover()`                | `catch_unwind()`                               | Panic recovery |
| `for i := 0; i < N; i++`   | `for i in 0..N {}`                             | C-style loop |
| `for range slice`          | `for item in slice {}`                         | Iteration    |
| `for i, v := range slice`  | `for (i, v) in slice.iter().enumerate() {}`    | Index and value iteration |
| `range map`                | `for (k, v) in map.iter() {}`                  | Map iteration |
| `range chan`               | `while let Some(v) = receiver.recv() {}`       | Channel iteration |
| `go`                       | `tokio::spawn(async { ... })`                  | Goroutine    |
| `select`                   | `tokio::select!`                               | Multiplexing selection |
| `switch v { case x: ... }` | `match v { x => ... }`                         | Switch/Match |

### 6. Package and Module Mapping

| Go feature         | Rust equivalent   | Notes                |
| ------------------ | ----------------- | -------------------- |
| `package main`     | `fn main() {}`    | Main package/function |
| `package foo`      | `mod foo {}`      | Module definition    |
| `import "pkg"`     | `use pkg;`        | Import module        |
| `import _ "pkg"`   | -                 | Go-specific, no Rust equivalent |
| `import . "pkg"`   | `use pkg::*;`     | Wildcard import (not recommended) |
| `import foo "pkg"` | `use pkg as foo;` | Aliased import       |
| `go.mod`           | `Cargo.toml`      | Package management file |
| `go build`         | `cargo build`     | Build                |
| `go test`          | `cargo test`      | Test                 |
| `go vet`           | `cargo clippy`    | Static analysis      |

## Checklists

### Task Management Checklist

**Multi-level task list check:**

- [ ] The task list level (directory-level/file-level/function-level) has been determined according to the transpilation scale
- [ ] Directory-level task list (if needed): the directory structure, module organization, and dependency relationships have been planned
- [ ] File-level task list (if needed): the file module location, function organization, and shared types have been planned
- [ ] Function-level task list (mandatory): a task list has been created for each function
- [ ] The task list hierarchy is correct (directory-level → file-level → function-level)

**Task list quality check:**

- [ ] A task list has been created using task_list_manager
- [ ] The task list contains all phases (planning, implementation, build, review, optimization, evaluation)
- [ ] The task type is correct (sub/main)
- [ ] The task descriptions are complete (including constraints, requirements, prohibitions, and verification criteria)
- [ ] **Every subtask contains Go code line number location information**
- [ ] The Go code location information format is correct (function/struct level: `file.go:start-end`, file level: `file.go`, directory level: `dir/`)
- [ ] The expected output is structured (using a bulleted list format)
- [ ] The expected output contains the Go code location information
- [ ] The task dependencies are set correctly
- [ ] The creation of the task list has been verified as successful

### Planning Phase Checklist

- [ ] Go code location information has been recorded (file path and line number range)
- [ ] The Go code location information is included in the task description or background information
- [ ] An appropriate module location has been selected
- [ ] A function signature that follows Rust best practices has been designed
- [ ] The function/struct/trait comment contains the corresponding Go code location information
- [ ] For Go structs, conversion to Rust structs and methods has been considered
- [ ] For Go interfaces, conversion to Rust traits has been considered
- [ ] For Go goroutines, conversion to Rust async/await has been considered
- [ ] For Go channels, conversion to Rust channels has been considered
- [ ] Whether implementation is needed has been evaluated (if skipped, the reason has been explained in detail)
- [ ] If it is a root symbol, the signature contains the `pub` keyword
- [ ] **The planning phase documentation has been generated**
- [ ] The planning document contains all required content (location information, decisions, assessment results, etc.)
- [ ] The planning document has been stored in the specified location
- [ ] The task's expected output contains the document path

### Implementation Phase Checklist

- [ ] Test cases were written first
- [ ] The test cases cover the main functionality, boundary cases, and error cases
- [ ] The function has been implemented to make the tests pass
- [ ] `todo!` or `unimplemented!` placeholders are not used
- [ ] Rust native types and idioms are used
- [ ] Comments are in Chinese
- [ ] The function/struct/trait comment contains the Go code location information
- [ ] For Go structs, correct conversion to Rust structs and methods has been performed
- [ ] For Go interfaces, correct conversion to Rust traits has been performed
- [ ] For Go goroutines, correct conversion to Rust async/await has been performed
- [ ] For Go channels, correct conversion to Rust channels has been performed
- [ ] For Go error handling, correct conversion to Result<T,E> has been performed
- [ ] `use ...::*` wildcard imports are not used
- [ ] **The implementation phase documentation has been generated**
- [ ] The implementation document contains all required content (test design, implementation strategy, refactoring description, etc.)
- [ ] The implementation document has been stored in the specified location
- [ ] The task's expected output contains the document path

### Build Phase Checklist

- [ ] All test cases pass
- [ ] No compilation errors
- [ ] The fixing process did not break other tests
- [ ] Changes are minimized, with no unrelated refactoring
- [ ] **The build phase documentation has been generated**
- [ ] The build document contains all required content (build process, problems and solutions, verification results, etc.)
- [ ] The build document has been stored in the specified location
- [ ] The task's expected output contains the document path

### Review Phase Checklist

- [ ] Test cases have not been broken (#[test] markers intact)
- [ ] No serious problems (null pointers, out-of-bounds, etc.)
- [ ] Test cases are complete (covering main functionality, boundary, and error cases)
- [ ] The core functionality is consistent with the Go implementation
- [ ] For Go structs, the public interface is consistent with the original implementation
- [ ] For Go interfaces, the interface methods are fully implemented
- [ ] For Go concurrency, the concurrent behavior is kept consistent
- [ ] The file structure is reasonable
- [ ] The problem report contains a detailed description, fix suggestions, and fix code examples
- [ ] **The review phase documentation has been generated**
- [ ] The review document contains all required content (review results, problem list, fix suggestions, etc.)
- [ ] The review document has been stored in the specified location
- [ ] The task's expected output contains the document path

### Optimization Phase Checklist

- [ ] All problems have been fixed by priority
- [ ] All tests pass after the fixes
- [ ] No regression problems were introduced
- [ ] Changes are minimized
- [ ] **The optimization phase documentation has been generated**
- [ ] The optimization document contains all required content (optimized problems, fix plans, verification results, etc.)
- [ ] The optimization document has been stored in the specified location
- [ ] The task's expected output contains the document path

### Evaluation Phase Checklist

- [ ] An independent evaluation has been performed using a sub-agent
- [ ] The evaluation report has been generated, containing functional alignment check results
- [ ] The evaluation report contains the Go code location information
- [ ] The functional alignment check has been completed, comparing Go and Rust implementations item by item
- [ ] For Go structs, encapsulation and interface consistency have been checked
- [ ] For Go interfaces, the completeness of the interface implementation has been checked
- [ ] For Go concurrency, the consistency of the concurrent behavior has been checked
- [ ] The test coverage check has been completed
- [ ] The boundary case check has been completed
- [ ] If functional misalignment problems were found, an optimization subtask has been created
- [ ] The optimization subtask contains the Go code location information
- [ ] The optimization subtask has been executed and the problems fixed
- [ ] After fixing, the evaluation has been re-performed and the functionality is fully aligned
- [ ] The evaluation report confirms that the functionality is fully aligned
- [ ] All test cases pass
- [ ] **The evaluation phase documentation has been generated**
- [ ] The evaluation document contains all required content (evaluation report, functional alignment check, problems and suggestions, etc.)
- [ ] The evaluation document has been stored in the specified location
- [ ] The task's expected output contains the document path

### Special Requirements for Root Symbols

If the function is a root symbol (needs to be accessed from outside the crate):

- [ ] The function signature contains the `pub` keyword
- [ ] The module where the function resides is exported in `src/lib.rs` (`pub mod <module name>;`)
- [ ] If FFI export is needed, `#[no_mangle]` and `pub extern "C"` are used

## Related Resources

- Reference TDD rules: {{ rule_file_dir }}/../development_workflow/tdd.md
- Reference code review rules: {{ rule_file_dir }}/../code_quality/code_review.md
- Reference Rust performance optimization: {{ rule_file_dir }}/../performance/rust_performance.md
