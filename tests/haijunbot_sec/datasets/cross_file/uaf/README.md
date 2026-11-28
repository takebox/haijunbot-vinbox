# Cross-File UAF Test Suite

This directory contains cross-file Use-After-Free vulnerability test cases.

## Test Case List

### 1. basic_cross_file_uaf

**Description**: Memory allocation, use, and free across different files

**Difficulty**: Easy

**Detection Points**:

- Cross-function call chain tracing
- Pointer state propagation across files
- UAF pattern recognition

### 2. callback_uaf

**Description**: UAF triggered through callback functions

**Difficulty**: Medium

**Detection Points**:

- Callback function lifecycle analysis
- Indirect call tracing

### 3. struct_member_uaf

**Description**: UAF of structure member pointers

**Difficulty**: Medium

**Detection Points**:

- Structure field access tracing
- Member pointer state management

## Testing Methods

```bash
# Run a single test case
pytest tests/haijunbot_sec/test_cross_file_analysis.py::TestCrossFileUAF::test_uaf_alloc_use_free_different_files -v

# Run all UAF tests
pytest tests/haijunbot_sec/test_cross_file_analysis.py::TestCrossFileUAF -v
```

## Adding New Test Cases

1. Create a subdirectory in this directory (e.g., `my_uaf_case/`)

2. Add source code files (.c/.h)

3. Create `metadata.json` describing test information

4. Add corresponding test methods in the test framework
