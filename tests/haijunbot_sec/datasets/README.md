# Heuristic Rule Test Datasets

This directory contains test datasets provided for each heuristic rule, used to validate rule accuracy and reduce false positives.

## Directory Structure

```
datasets/
├── possible_null_deref/          # Null pointer dereference detection
│   ├── positive_no_check.c       # Positive: should be detected
│   ├── negative_if_check.c       # Negative: should not be detected
│   └── ...
├── data_race_suspect/            # Data race detection
│   ├── positive_write_no_lock.c  # Positive: should be detected
│   ├── negative_with_mutex.c     # Negative: should not be detected
│   └── ...
└── ...                           # Other rules
```

## File Naming Conventions

- **Positive case files**: `positive_*.c` or `positive_*.cpp`
  - Contain real issues that should be detected
  - File header comment describes the rule name expected to be detected

- **Negative case files**: `negative_*.c` or `negative_*.cpp`
  - Contain safe code that should not be detected
  - Used to verify rules do not produce false positives

## Test Dataset Purpose

1. **Validate rule accuracy**: Ensure rules correctly detect real issues
2. **Reduce false positives**: Ensure rules do not flag safe code
3. **Continuous optimization baseline**: Provide validation benchmarks for future rule improvements

## Usage

### Manual Verification

```python
from haijunbot.haijunbot_sec.checkers.c_checker import analyze_c_cpp_text

# Read test file
with open('datasets/possible_null_deref/positive_no_check.c', 'r') as f:
    src = f.read()

# Analyze code
issues = analyze_c_cpp_text('test.c', src)

# Verify expected issue was detected
assert any(i.pattern == 'possible_null_deref' for i in issues)
```

### Batch Verification

You can use the test framework to batch-verify all test datasets:

```bash
pytest tests/haijunbot_sec/test_checkers.py -v
```

## Rule List

| Rule Name                     | Directory                     | Description                |
| ----------------------------- | ----------------------------- | -------------------------- |
| possible_null_deref          | possible_null_deref/          | Null pointer dereference detection |
| data_race_suspect            | data_race_suspect/            | Data race detection        |
| unsafe_api                   | unsafe_api/                   | Unsafe API detection       |
| malloc_no_null_check         | malloc_no_null_check/         | malloc return value check   |
| format_string                | format_string/                | Format string detection    |
| uaf_suspect                  | uaf_suspect/                  | Use-After-Free detection   |
| double_free                  | double_free/                  | Double Free detection      |
| command_execution            | command_execution/            | Command execution detection |
| alloc_size_overflow          | alloc_size_overflow/          | Allocation size overflow detection |
| scanf_no_width               | scanf_no_width/               | scanf width detection      |
| insecure_tmpfile             | insecure_tmpfile/             | Insecure temp file detection |
| atoi_family                  | atoi_family/                  | atoi family detection      |
| rand_insecure                | rand_insecure/                | rand insecure detection    |
| strtok_nonreentrant          | strtok_nonreentrant/          | strtok non-reentrant detection |
| pthread_returns_unchecked    | pthread_returns_unchecked/    | pthread return value check  |
| thread_leak_no_join          | thread_leak_no_join/          | Thread leak detection      |
| deadlock_patterns            | deadlock_patterns/            | Deadlock pattern detection |
| uninitialized_ptr_use        | uninitialized_ptr_use/        | Uninitialized pointer use detection |
| smart_ptr_cycle              | smart_ptr_cycle/              | Smart pointer cycle detection |
| smart_ptr_get_unsafe         | smart_ptr_get_unsafe/         | Smart pointer get() unsafe detection |
| new_delete_mismatch          | new_delete_mismatch/          | new/delete mismatch detection |
| reinterpret_cast_unsafe      | reinterpret_cast_unsafe/      | reinterpret_cast unsafe detection |
| const_cast_unsafe            | const_cast_unsafe/            | const_cast unsafe detection |
| missing_virtual_dtor         | missing_virtual_dtor/         | Missing virtual destructor detection |
| move_after_use               | move_after_use/               | Move after use detection   |
| uncaught_exception           | uncaught_exception/           | Uncaught exception detection |
| vector_string_bounds_check   | vector_string_bounds_check/   | vector string bounds check  |
| strncpy_no_nullterm          | strncpy_no_nullterm/          | strncpy not null-terminated detection |
| realloc_assign_back          | realloc_assign_back/          | realloc not assigned back detection |
| function_return_ptr_no_check | function_return_ptr_no_check/ | Function return pointer unchecked |
| unchecked_io                 | unchecked_io/                 | I/O return value unchecked |
| alloca_unbounded             | alloca_unbounded/             | alloca unbounded detection  |
| vla_usage                    | vla_usage/                    | VLA usage detection        |
| cond_wait_no_loop            | cond_wait_no_loop/            | cond_wait without loop detection |
| inet_legacy                  | inet_legacy/                  | inet legacy API detection  |
| time_apis_not_threadsafe     | time_apis_not_threadsafe/     | Time APIs not thread-safe detection |
| getenv_unchecked             | getenv_unchecked/             | getenv unchecked detection |
| open_permissive_perms        | open_permissive_perms/        | Overly permissive permissions detection |

## Contribution Guidelines

When adding new test datasets, please follow these conventions:

1. Create a separate directory for each rule
2. Provide at least one positive case and one negative case
3. Add a header comment in files describing expected detection results
4. Use `.c` extension for C code and `.cpp` for C++ code
5. Follow `positive_*.c` and `negative_*.c` naming conventions
