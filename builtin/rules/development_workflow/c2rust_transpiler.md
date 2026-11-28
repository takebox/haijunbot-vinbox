---
name: c2rust_transpiler
description: Triggered when C/C++ code needs to be converted to Rust code. Triggered whenever the user mentions "C to Rust", "C++ to Rust", "convert C to Rust", "convert C++ to Rust", "code transpilation", "language migration", "C migration", or "C++ migration". Not triggered: writing Rust code only without C/C++ transpilation; merely reading C/C++ code without converting; Go to Rust transpilation.
---

# C/C++2Rust Transpilation Rules

## Rule Introduction

Used to guide the code transpilation from C/C++ to Rust, preserving transpilation quality, functional consistency, and type safety. This rule covers the complete process of planning, implementation, build, review, optimization, and evaluation.

⚠

**Supported language features:**

- **C language**: functions, structs, unions, enums, pointers, arrays, etc.
- **C++ language**: classes, templates, namespaces, STL containers, smart pointers, inheritance, polymorphism, operator overloading, etc.

## Principles You Must Follow

### 1. Task Management Principle (Core)

**Requirements:**

- **Must**: for the transpilation of every function, use `task_list_manager` to manage the corresponding tasks
- **Must**: before transpiling, a task list must first be created, planning the tasks of each phase (planning, implementation, build, review, optimization, evaluation)
- **Must**: use the `add_tasks` operation of task_list_manager to add each subtask
- **Must**: set task dependencies according to the dependency relationships (e.g., the implementation phase depends on the planning phase)
- **Forbidden**: skipping task_list_manager and executing tasks directly

**Multi-level task list requirements:**

C/C++ to Rust transpilation is a complex process; different levels of task lists must be created according to the scale of transpilation:

1. **Directory-level task list** (as needed)
   - **When needed**: when transpiling an entire directory or multiple related directories
   - **Task content**: plan the directory structure, module organization, dependency relationships, etc.
   - **Subtasks**: include the transpilation tasks for all files under that directory
   - **Example**: transpile all C/C++ files (`.c`, `.cpp`, `.h`, `.hpp`) under `src/utils/`

2. **File-level task list** (as needed)
   - **When needed**: when transpiling a single file or multiple related functions/classes
   - **Task content**: plan the file module location, function/class grouping, shared type definitions, etc.
   - **Subtasks**: include the transpilation tasks for all functions/classes in that file
   - **Example**:
     - C: transpile all hash-related functions in `hash.c`
     - C++: transpile the `Vector` class and its member functions in `vector.hpp`

3. **Function/class-level task list** (mandatory)
   - **When needed**: when transpiling a single function or class (this is the smallest granularity and must be created)
   - **Task content**: plan the function/class signature, implementation strategy, test cases, etc.
   - **Subtasks**: include the planning, implementation, build, review, optimization, and evaluation phases for that function/class
   - **Example**:
     - C: transpile a single function `calculate_hash`
     - C++: transpile a single class `String` and all its member functions

**Task list hierarchy:**

- Directory-level task list → File-level task list → Function-level task list
- The subtasks of a higher-level task list can be lower-level task lists
- If transpiling only a single function, only a function-level task list needs to be created
- If transpiling multiple functions but they belong to the same file, a file-level task list can be created, containing multiple function-level subtasks
- If transpiling multiple files, a directory-level task list can be created, containing multiple file-level subtasks

**Task list requirements:**

- Task type: use the `sub` type for complex tasks and the `main` type for simple tasks
- Task description: each task should include constraints, requirements, prohibitions, and verification criteria
- Expected output: expected output must be listed in a structured format
- Verification method: after task completion, a verification method description must be provided
- **C/C++ code location information**: **Must** include the line number location of the original C/C++ code in each subtask
  - Function/class-level task: should include the file path and line number range where the C/C++ function/class is located
    - C: `path/to/file.c:42-67` or `path/to/file.h:10-25`
    - C++: `path/to/file.cpp:42-67` or `path/to/file.hpp:10-25`
  - File-level task: should include the path of the C/C++ file (`.c`, `.cpp`, `.h`, `.hpp`)
  - Directory-level task: should include the path of the C/C++ directory
  - Location information should be included in the `background` field or the `task_desc` field

**Example:**

#### Example 1: Function-level task list (mandatory)

```json
// ✅ Correct: function-level task list (including C/C++ code line number location information)
{
  "action": "add_tasks",
  "main_goal": "Transpile function foo",
  "background": "The C function foo is located at path/to/foo.c:42-67, and its functionality is...",
  "tasks_info": [
    {
      "task_name": "Planning phase",
      "task_desc": "Select a module location and design the Rust signature for function foo (path/to/foo.c:42-67)...",
      "expected_output": "- Module path: src/foo.rs\n- Rust signature: pub fn foo(...) ...\n- C/C++ code location: path/to/foo.c:42-67\n- Planning document: docs/transpilation/foo_planning.md",
      "agent_type": "sub",
      "dependencies": []
    },
    {
      "task_name": "Implementation phase",
      "task_desc": "Implement function foo (path/to/foo.c:42-67) using the TDD method...",
      "expected_output": "- Test cases written\n- Implementation completed\n- C/C++ code location: path/to/foo.c:42-67\n- Implementation document: docs/transpilation/foo_implementation.md",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Build phase",
      "task_desc": "Run cargo test and fix build issues (transpiled from path/to/foo.c:42-67)...",
      "expected_output": "- All tests pass\n- No compilation errors\n- C/C++ code location: path/to/foo.c:42-67\n- Build document: docs/transpilation/foo_build.md",
      "agent_type": "sub",
      "dependencies": ["Implementation phase"]
    },
    {
      "task_name": "Review phase",
      "task_desc": "Review code quality, functional consistency, and test completeness (transpiled from path/to/foo.c:42-67)...",
      "expected_output": "- Review report\n- Issue list\n- C/C++ code location: path/to/foo.c:42-67\n- Review document: docs/transpilation/foo_review.md",
      "agent_type": "sub",
      "dependencies": ["Build phase"]
    },
    {
      "task_name": "Optimization phase",
      "task_desc": "Fix the issues found in review and verify (transpiled from path/to/foo.c:42-67)...",
      "expected_output": "- Issues fixed\n- All tests pass\n- C/C++ code location: path/to/foo.c:42-67\n- Optimization document: docs/transpilation/foo_optimization.md",
      "agent_type": "sub",
      "dependencies": ["Review phase"]
    },
    {
      "task_name": "Evaluation phase",
      "task_desc": "Use a sub-agent to evaluate the overall effect and check functional alignment (transpiled from path/to/foo.c:42-67)...",
      "expected_output": "- Evaluation report\n- Functional alignment check results\n- If there are issues, create optimization subtasks\n- C/C++ code location: path/to/foo.c:42-67\n- Evaluation document: docs/transpilation/foo_evaluation.md",
      "agent_type": "sub",
      "dependencies": ["Optimization phase"]
    }
  ]
}
```

#### Example 2: File-level task list (as needed)

```json
// ✅ Correct: file-level task list (transpile the hash.c/hash.cpp file, including C/C++ code line number location information)
{
  "action": "add_tasks",
  "main_goal": "Transpile file hash.c",
  "background": "The C file hash.c contains multiple hash-related functions: hash_init (hash.c:15-45), hash_update (hash.c:47-78), hash_final (hash.c:80-110)...",
  "tasks_info": [
    {
      "task_name": "Planning phase",
      "task_desc": "Plan the module location and overall structure of hash.c...",
      "expected_output": "- Module path: src/hash.rs\n- Shared type definitions\n- Function grouping plan\n- C/C++ file location: hash.c",
      "agent_type": "sub",
      "dependencies": []
    },
    {
      "task_name": "Transpile function hash_init",
      "task_desc": "Transpile function hash_init (hash.c:15-45) (including planning, implementation, build, review, optimization, evaluation)...",
      "expected_output": "- hash_init function transpilation completed\n- Tests pass\n- Functional alignment verification passes\n- C/C++ code location: hash.c:15-45",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Transpile function hash_update",
      "task_desc": "Transpile function hash_update (hash.c:47-78) (including planning, implementation, build, review, optimization, evaluation)...",
      "expected_output": "- hash_update function transpilation completed\n- Tests pass\n- Functional alignment verification passes\n- C/C++ code location: hash.c:47-78",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Transpile function hash_final",
      "task_desc": "Transpile function hash_final (hash.c:80-110) (including planning, implementation, build, review, optimization, evaluation)...",
      "expected_output": "- hash_final function transpilation completed\n- Tests pass\n- Functional alignment verification passes\n- C/C++ code location: hash.c:80-110",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "File-level integration test",
      "task_desc": "Run file-level integration tests to ensure all functions work together (transpiled from hash.c)...",
      "expected_output": "- Integration tests pass\n- File transpilation completed\n- C/C++ file location: hash.c",
      "agent_type": "sub",
      "dependencies": [
        "Transpile function hash_init",
        "Transpile function hash_update",
        "Transpile function hash_final"
      ]
    }
  ]
}
```

#### Example 3: Directory-level task list (as needed)

```json
// ✅ Correct: directory-level task list (transpile the src/utils/ directory, including C/C++ code line number location information)
{
  "action": "add_tasks",
  "main_goal": "Transpile directory src/utils/",
  "background": "The C/C++ directory src/utils/ contains multiple utility files: string.c, math.cpp, memory.hpp...",
  "tasks_info": [
    {
      "task_name": "Planning phase",
      "task_desc": "Plan the directory structure, module organization, and dependency relationships (transpiled from src/utils/)...",
      "expected_output": "- Rust module structure plan\n- Dependency graph\n- Transpilation order\n- C/C++ directory location: src/utils/",
      "agent_type": "sub",
      "dependencies": []
    },
    {
      "task_name": "Transpile file string.c",
      "task_desc": "Transpile the string.c file (including all functions in that file, located at src/utils/string.c)...",
      "expected_output": "- string.c transpilation completed\n- All functions pass tests\n- Functional alignment verification passes\n- C/C++ file location: src/utils/string.c",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Transpile file math.cpp",
      "task_desc": "Transpile the math.cpp file (including all classes and functions in that file, located at src/utils/math.cpp)...",
      "expected_output": "- math.cpp transpilation completed\n- All classes and functions pass tests\n- Functional alignment verification passes\n- C/C++ file location: src/utils/math.cpp",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Transpile file memory.hpp",
      "task_desc": "Transpile the memory.hpp file (including all classes and templates in that file, located at src/utils/memory.hpp)...",
      "expected_output": "- memory.hpp transpilation completed\n- All classes and templates pass tests\n- Functional alignment verification passes\n- C/C++ file location: src/utils/memory.hpp",
      "agent_type": "sub",
      "dependencies": ["Planning phase"]
    },
    {
      "task_name": "Directory-level integration test",
      "task_desc": "Run directory-level integration tests to ensure all modules work together (transpiled from src/utils/)...",
      "expected_output": "- Integration tests pass\n- Directory transpilation completed\n- C/C++ directory location: src/utils/",
      "agent_type": "sub",
      "dependencies": [
        "Transpile file string.c",
        "Transpile file math.c",
        "Transpile file memory.c"
      ]
    }
  ]
}
```

```bash
# ❌ Wrong: executing directly without using task_list_manager
echo "Starting to transpile function foo"
# Directly writing code without task management
```

### 2. TDD Development Principle

**Requirements:**

- **Must**: write tests first (#[cfg(test)] mod tests), designing test cases based on the behavior of the C/C++ function/class
- **Must**: write the implementation to make tests pass, ensuring semantic equivalence with C/C++
- **Must**: optimize the code while keeping tests passing (refactoring phase)
- **Forbidden**: writing the implementation code directly without tests
- **Forbidden**: using `todo!` or `unimplemented!` as placeholders

**C++-specific considerations:**

- Class member functions must be tested separately for the public interface and the private implementation (through the public interface)
- Template functions/classes must be tested for instantiation with different template parameters
- Operator overloading must be tested for all overloaded operators

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

**Requirements:**

- **Must**: define core functionality consistent with the C/C++ implementation (main purpose and expected behavior)
- **Allowed**: behavioral inconsistency caused by security improvements (fixing buffer overflows, null pointer dereferences, and other security vulnerabilities)
- **Ignored**: behavioral inconsistency caused by language differences (integer overflow handling, undefined behavior handling, etc.)
- **Allowed**: using different type design, error handling, and resource management approaches
- **Forbidden**: changing the core functional logic

**Note:** Core functionality refers to the main purpose of the function/class (e.g., "compute a hash value", "parse a string", "manage a dynamic array"), and does not include implementation details.

**C++-specific considerations:**

- Class encapsulation: keep the public interface consistent; internal implementations may differ
- Inheritance relationships: keep the inheritance hierarchy and virtual function behavior consistent
- Template instantiation: ensure templates behave consistently under different type parameters
- STL containers: equivalent containers from the Rust standard library can be used (e.g., `Vec` corresponds to `std::vector`)
- Smart pointers: can be replaced with Rust's ownership system (`Box`, `Rc`, `Arc`)

### 4. Modular Design Principle

**Requirements:**

- **Must**: select modules by functional cohesion and dependency direction, avoiding circular dependencies
- **Must**: module paths must be located under the crate's src/ directory
- **Must**: prioritize placing functions into already existing modules
- **Allowed**: create new submodule files when necessary
- **Forbidden**: placing unrelated functionality in the same module

### 5. Type Safety Principle

**Requirements:**

- **Must**: prioritize Rust native types (i32/u32, &str/String, &[T]/&mut [T], Result<T,E>)
- **Forbidden**: prioritizing C-style types (core::ffi::c*, libc::c*)
- **Forbidden**: using extern "C" (unless required for FFI export)
- **Must**: function signatures should follow Rust best practices and do not need to be compatible with C's data types
- **Forbidden**: using `use ...::*` wildcard imports

### 6. Documentation Principle

**Requirements:**

- **Must**: documentation must be generated for every transpilation phase
- **Must**: the documentation should include the phase's execution process, decision basis, and the problems encountered and their solutions
- **Must**: the documentation should include C code location information for traceability
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

**Important note:** Before transpiling, you must select the appropriate task list level according to the scale of transpilation:

- **Transpile a single function**: create a function-level task list (mandatory)
- **Transpile a single file or multiple related functions**: create a file-level task list, containing multiple function-level subtasks (as needed)
- **Transpile an entire directory or multiple related directories**: create a directory-level task list, containing multiple file-level subtasks (as needed)

The following operation phases apply to task lists at all levels, but the specific execution granularity depends on the task list level.

### Phase 1: Planning Phase

#### Operation 1: Record C/C++ Code Location Information

- **Must**: record the location information of the original C/C++ code
  - Function/class level: record the file path and line number range where the C/C++ function/class is located
    - C: `path/to/file.c:42-67` or `path/to/file.h:10-25`
    - C++: `path/to/file.cpp:42-67` or `path/to/file.hpp:10-25`
  - File level: record the full path of the C/C++ file (`.c`, `.cpp`, `.h`, `.hpp`)
  - Directory level: record the path of the C/C++ directory (e.g., `path/to/dir/`)
- **Must**: include the location information in the task description, background information, or expected output
- **Must**: ensure the location information is accurate for subsequent traceability and verification
- **C++-specific**: for template classes/functions, the locations of all instantiations must be recorded

#### Operation 2: Select the Module Location

- Analyze the functional characteristics of the function and determine the functional module it belongs to
- Check the crate directory structure, and select or create an appropriate module file
- Ensure the module path is located under the src/ directory
- Evaluate whether a new submodule file needs to be created

#### Operation 3: Design the Rust Function/Struct/Trait Signature

- Design the Rust function/struct/trait signature based on the C/C++ function/class signature
- Prioritize Rust native types and avoid C/C++-style types
- Consider using `Result<T, E>` or `Option<T>` for error handling
- If it is a root symbol, the `pub` keyword must be used
- **Must**: record the corresponding C/C++ code location information in the function/struct comment (e.g., `/// Transpiled from path/to/file.c:42-67`)

**C++-specific handling:**

- **Class to struct**: C++ classes convert to Rust structs, with member functions converting to associated functions or methods
- **Inheritance to trait**: C++ inheritance relationships convert to Rust traits and impls
- **Template to generic**: C++ templates convert to Rust generics (`<T>`)
- **Namespace to module**: C++ namespaces convert to Rust modules
- **STL container mapping**:
  - `std::vector<T>` → `Vec<T>`
  - `std::string` → `String` or `&str`
  - `std::map<K, V>` → `std::collections::HashMap<K, V>`
  - `std::unique_ptr<T>` → `Box<T>`
  - `std::shared_ptr<T>` → `Rc<T>` or `Arc<T>`
- **Operator overloading**: use Rust's operator traits (e.g., `Add`, `Sub`, `Deref`, etc.)

#### Operation 4: Evaluate Whether Implementation Is Needed

Implementation can be skipped in the following cases (set skip_implementation to true):

- **Already implemented functions/classes**: the function/class is already implemented in the target module and its functionality is consistent with the C/C++ implementation
- **Resource release functions**: such as fclose, free, delete, which are automatically managed via RAII
- **Already replaced by a library**: the function/class has been replaced by the standard library or a third-party crate with fully consistent functionality
- **Empty implementations or meaningless functions**: the C/C++ function is an empty implementation or simply returns a constant
- **Inline functions or macros**: functions or macros that are inline in C/C++
- **C++-specific**:
  - Pure virtual functions (if the Rust trait is already defined)
  - Default constructors/destructors (handled automatically by Rust)
  - Simple wrappers for certain STL containers (can directly use the Rust standard library)

**Important**: skipping the implementation must be explained in detail in the notes field.

#### Operation 5: Generate the Planning Phase Document

- **Must**: generate the planning phase documentation
- **Must**: the documentation contains the following content:
  - C code location information (file path and line number range)
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
  - Error cases (if the C/C++ implementation has error handling)
- The expected results of the test cases must be consistent with the behavior of the C/C++ implementation
- Use clear test names and appropriate assertions

**C++-specific test requirements:**

- **Class tests**: test all public methods, including constructors, destructors, and operator overloads
- **Inheritance tests**: test the methods of base and derived classes, including the polymorphic behavior of virtual functions
- **Template tests**: test the behavior of templates under different type parameters (e.g., `Vec<i32>`, `Vec<String>`)
- **Exception handling**: C++ exceptions convert to Rust's `Result` or `panic`, requiring corresponding tests
- **Move semantics**: test the equivalent behavior of move constructors and move assignment operators

#### Operation 2: Implement the Function/Struct/Trait

- Make the tests pass, implementing functionality semantically equivalent to C/C++
- Use Rust native types and idioms
- Consider using RAII to manage resources
- Add Chinese comments to explain the logic

**C++-specific implementation requirements:**

- **Class implementation**: convert C++ classes to Rust structs, with member variables as fields and member functions as methods
- **Constructors**: implement using `new()` or the `Default` trait
- **Destructors**: implement using the `Drop` trait
- **Inheritance**: simulate inheritance using traits and impls (`impl Trait for Struct`)
- **Polymorphism**: implement runtime polymorphism using trait objects (`Box<dyn Trait>`)
- **Template generics**: implement using Rust generics, and consider using trait bounds (`where T: Trait`)
- **Operator overloading**: implement the corresponding operator traits (e.g., `Add`, `Sub`, `Mul`, `Deref`, etc.)
- **Smart pointers**:
  - `std::unique_ptr<T>` → `Box<T>`
  - `std::shared_ptr<T>` → `Rc<T>` (single-threaded) or `Arc<T>` (multi-threaded)
  - `std::weak_ptr<T>` → `Weak<T>`

#### Operation 3: Refactor the Code

- Optimize the code structure while keeping tests passing
- Improve code readability and maintainability
- Ensure functional behavior is not changed

#### Operation 4: Generate the Implementation Phase Document

- **Must**: generate the implementation phase documentation
- **Must**: the documentation contains the following content:
  - C code location information (file path and line number range)
  - Test case design description and coverage cases
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
  - C code location information (file path and line number range)
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

3. **Test case completeness check**
   - Whether there are test cases
   - Whether the main functionality is covered
   - Whether boundary cases are covered
   - Whether error cases are covered

4. **Functional consistency check**
   - Whether the core inputs and outputs are consistent
   - Whether the main functional logic is consistent
   - Behavioral inconsistency caused by security improvements is allowed
   - **C++-specific**:
     - Whether the class's public interface is consistent
     - Whether the inheritance relationships are correctly converted
     - Whether the template instantiation behavior is consistent
     - Whether the operator overloading behavior is consistent

5. **Breaking change detection**
   - Check module export changes
   - Check type definition changes
   - Signature inconsistency is allowed (as long as functionality is implemented)

6. **File structure reasonableness check**
   - Whether the module file location is reasonable
   - Whether the file naming conforms to the specification
   - Whether the module exports are correct

**Operation:** Based on the review results, provide a detailed problem description, fix suggestions, and fix code examples.

#### Operation: Generate the Review Phase Document

- **Must**: generate the review phase documentation
- **Must**: the documentation contains the following content:
  - C code location information (file path and line number range)
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
  - C code location information (file path and line number range)
  - List and priority of optimized problems
  - The fix plan and execution process for each problem
  - Verification results after the fixes
  - Regression test results
  - Optimization effect summary
- **Must**: store the documentation in the specified location (e.g., `docs/transpilation/<function_name>_optimization.md`)
- **Must**: include the document path in the task's expected output

### Phase 6: Evaluation Phase

**Important note:** The evaluation phase must use a sub-agent to perform independent evaluation to ensure objectivity and comprehensiveness.

#### Operation 1: Use a Sub-agent to Evaluate the Overall Effect

- **Must**: use a sub-agent (`agent_type: "sub"`) to independently evaluate the transpilation result
- **Must**: the evaluation scope includes:
  - Functional alignment check: compare whether the core functionality of the C/C++ implementation and the Rust implementation is consistent
  - Test coverage check: whether the test cases sufficiently cover the behavior of the C/C++ function/class
  - Boundary case check: whether the boundary conditions and error handling are consistent with the C/C++ implementation
  - Performance impact assessment: whether the performance of the Rust implementation meets requirements (if applicable)
  - Code quality assessment: code readability, maintainability, type safety
  - **C++-specific**:
    - Whether the class's encapsulation is maintained
    - Whether the inheritance and polymorphism behavior is consistent
    - Whether the template instantiation behavior is consistent
    - Whether operator overloading is complete
    - Whether exception handling is correctly converted
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
- **Must**: after fixing, re-evaluate until the functionality is fully aligned

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

- Transpilation target: [function name/class name/file name/directory name]
- C/C++ code location: [file path:line number range] (e.g., path/to/file.c:42-67 or path/to/file.cpp:42-67)
- Evaluation time: [timestamp]
- Evaluation method: [evaluation method used]

### Functional Alignment Check Results

1. [functionality point 1]: ✅ Aligned / ❌ Not aligned
   - C/C++ implementation location: [file path:line number range]
   - C/C++ implementation behavior: [description]
   - Rust implementation location: [file path:line number range]
   - Rust implementation behavior: [description]
   - Difference analysis: [explain the reason if there is a difference]

2. [functionality point 2]: ✅ Aligned / ❌ Not aligned
   - C/C++ implementation location: [file path:line number range]

### Test Coverage Check

- Main functionality paths: ✅ Covered / ❌ Not covered
- Boundary cases: ✅ Covered / ❌ Not covered
- Error cases: ✅ Covered / ❌ Not covered
- **C++-specific**:
  - All public methods of the class: ✅ Covered / ❌ Not covered
  - Inheritance and polymorphism: ✅ Covered / ❌ Not covered
  - Template instantiation: ✅ Covered / ❌ Not covered
  - Operator overloading: ✅ Covered / ❌ Not covered

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
# [Phase name] Document - [function name/file name/directory name]

## Basic Information

- C/C++ code location: [file path:line number range] (e.g., path/to/file.c:42-67 or path/to/file.cpp:42-67)
- Transpilation target: [function name/class name/file name/directory name]
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

## Checklists

### Task Management Checklist

**Multi-level task list check:**

- [ ] The task list level (directory-level/file-level/function-level) has been determined according to the transpilation scale
- [ ] Directory-level task list (if needed): the directory structure, module organization, and dependency relationships have been planned
- [ ] File-level task list (if needed): the file module location, function grouping, and shared types have been planned
- [ ] Function-level task list (mandatory): a task list has been created for each function
- [ ] The task list hierarchy is correct (directory-level → file-level → function-level)

**Task list quality check:**

- [ ] A task list has been created using task_list_manager
- [ ] The task list contains all phases (planning, implementation, build, review, optimization, evaluation)
- [ ] The task type is correct (sub/main)
- [ ] The task descriptions are complete (including constraints, requirements, prohibitions, and verification criteria)
- [ ] **Every subtask must contain the line number location information of the C/C++ code**
- [ ] The C/C++ code location information format is correct (function/class level: `file.c:start-end` or `file.cpp:start-end`, file level: `file.c`/`file.cpp`/`file.hpp`, directory level: `dir/`)
- [ ] The expected output is structured (using a bulleted list format)
- [ ] The expected output contains the C code location information
- [ ] The task dependencies are set correctly
- [ ] The creation of the task list has been verified as successful

### Planning Phase Checklist

- [ ] C/C++ code location information has been recorded (file path and line number range)
- [ ] The C/C++ code location information is included in the task description or background information
- [ ] For C++ templates, the locations of all instantiations have been recorded
- [ ] An appropriate module location has been selected
- [ ] A function signature that follows Rust best practices has been designed
- [ ] The function/struct/trait comment contains the corresponding C/C++ code location information
- [ ] For C++ classes, conversion to Rust structs and traits has been considered
- [ ] For C++ templates, conversion to Rust generics has been considered
- [ ] Whether implementation is needed has been evaluated (if skipped, the reason has been explained in detail)
- [ ] If it is a root symbol, the signature contains the `pub` keyword
- [ ] **The planning phase documentation has been generated**
- [ ] The planning document contains all required content (location information, decisions, assessment results, etc.)
- [ ] The planning document has been saved to the specified location
- [ ] The task's expected output contains the document path

### Implementation Phase Checklist

- [ ] Test cases were written first
- [ ] The test cases cover the main functionality, boundary cases, and error cases
- [ ] The function has been implemented to make the tests pass
- [ ] `todo!` or `unimplemented!` placeholders are not used
- [ ] Rust native types and idioms are used
- [ ] Comments are in Chinese
- [ ] The function/struct/trait comment contains the C/C++ code location information
- [ ] For C++ classes, correct conversion to Rust structs and traits has been performed
- [ ] For C++ inheritance, correct conversion to Rust traits and impls has been performed
- [ ] For C++ templates, correct conversion to Rust generics has been performed
- [ ] `use ...::*` wildcard imports are not used
- [ ] **The implementation phase documentation has been generated**
- [ ] The implementation document contains all required content (test design, implementation strategy, refactoring description, etc.)
- [ ] The implementation document has been saved to the specified location
- [ ] The task's expected output contains the document path

### Build Phase Checklist

- [ ] All test cases pass
- [ ] No compilation errors
- [ ] The fixing process did not break other tests
- [ ] Changes are minimized, with no unrelated refactoring
- [ ] **The build phase documentation has been generated**
- [ ] The build document contains all required content (build process, problems and solutions, verification results, etc.)
- [ ] The build document has been saved to the specified location
- [ ] The task's expected output contains the document path

- [ ] Test cases have not been broken (#[test] markers intact)

### Review Phase Checklist

- [ ] Test cases have not been broken (#[test] markers intact)
- [ ] No serious problems (null pointers, out-of-bounds, etc.)
- [ ] Test cases are complete (covering main functionality, boundary, and error cases)
- [ ] The core functionality is consistent with the C/C++ implementation
- [ ] For C++ classes, the public interface is consistent with the original implementation
- [ ] For C++ inheritance, the inheritance relationships are correctly converted
- [ ] The file structure is reasonable
- [ ] The problem report contains a detailed description, fix suggestions, and fix code examples
- [ ] **The review phase documentation has been generated**
- [ ] The review document contains all required content (review results, problem list, fix suggestions, etc.)
- [ ] The review document has been saved to the specified location
- [ ] The task's expected output contains the document path

### Optimization Phase Checklist

- [ ] All problems have been fixed by priority
- [ ] All tests pass after the fixes
- [ ] No regression problems were introduced
- [ ] Changes are minimized
- [ ] **The optimization phase documentation has been generated**
- [ ] The optimization document contains all required content (optimized problems, fix plans, verification results, etc.)
- [ ] The optimization document has been saved to the specified location
- [ ] The task's expected output contains the document path

### Evaluation Phase Checklist

- [ ] An independent evaluation has been performed using a sub-agent
- [ ] The evaluation report has been generated, containing functional alignment check results
- [ ] The evaluation report contains the C/C++ code location information
- [ ] The functional alignment check has been completed, comparing C/C++ and Rust implementations item by item
- [ ] For C++ classes, the class's encapsulation and interface consistency have been checked
- [ ] For C++ inheritance, the inheritance and polymorphism behavior has been checked
- [ ] For C++ templates, the template instantiation behavior has been checked
- [ ] The test coverage check has been completed
- [ ] The boundary case check has been completed
- [ ] If functional misalignment problems were found, an optimization subtask has been created
- [ ] The optimization subtask contains the C code location information
- [ ] The optimization subtask has been executed and the problems fixed
- [ ] After fixing, the evaluation has been re-performed and the functionality is fully aligned
- [ ] The evaluation report confirms that the functionality is fully aligned
- [ ] All test cases pass
- [ ] **The evaluation phase documentation has been generated**
- [ ] The evaluation document contains all required content (evaluation report, functional alignment check, problems and suggestions, etc.)
- [ ] The evaluation document has been saved to the specified location
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
