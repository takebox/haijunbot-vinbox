---
name: cpp_test
description: Triggered when tests need to be written for a C/C++ project or a test framework needs to be configured. Triggered whenever the user mentions "C++ testing", "C testing", "Google Test", "GTest", "Catch2". Not triggered: testing non-C/C++ projects; code review; performance optimization.
---

# C/C++ Testing Standards

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

### Google Test (gtest) (recommended)

**Installation methods:**

- Install with a package manager (e.g. `apt-get install libgtest-dev`)
- Or build and install from source

**CMake build and run:**

```bash
mkdir build && cd build
cmake ..
make
./test_runner              # run all tests
./test_runner --gtest_filter=TestClass.* # run specific tests
```

**Direct compile and run:**

```bash
g++ -std=c++17 test.cpp -lgtest -lgtest_main -pthread
./a.out
```

### Catch2

**Installation methods:**

- Download the single-header version
- Or install with a package manager

**Compile and run:**

```bash
g++ -std=c++17 test.cpp -o test
./test
```

## Test Cases You Must Write

### Google Test test case

```cpp
// test/calculator_test.cpp
#include <gtest/gtest.h>
#include "../src/calculator.h"

TEST(CalculatorTest, Add) {
    Calculator calc;
    EXPECT_EQ(5, calc.add(2, 3));
}


TEST(CalculatorTest, DivideByZero) {
    Calculator calc;
    EXPECT_THROW(calc.divide(10, 0), std::invalid_argument);
}
```

### Catch2 test case

```cpp
// test/calculator_test.cpp
#include <catch2/catch.hpp>
#include "../src/calculator.h"

TEST_CASE("Calculator add", "[calculator]") {
    Calculator calc;
    REQUIRE(calc.add(2, 3) == 5);
}
```

## Assertion Macro Usage Conventions

### Google Test assertions

- **Must**: Use `EXPECT_*` for non-fatal assertions (the test continues running)
- **Must**: Use `ASSERT_*` for fatal assertions (the test stops immediately)
- **Common**: `EXPECT_EQ`, `ASSERT_EQ`, `EXPECT_THROW`, `ASSERT_THROW`

### Catch2 assertions

- **Must**: Use `REQUIRE` for fatal assertions
- **Must**: Use `CHECK` for non-fatal assertions

## Test Execution Checklist

Before committing code, be sure to confirm:

- [ ] **Run tests immediately after writing them**
- [ ] **All tests pass**
- [ ] **If it fails, fix it until it passes**
- [ ] Tests cover the normal case
- [ ] Tests cover the boundary case
- [ ] Tests cover the exception case
- [ ] Use appropriate assertion macros (EXPECT_EQ, ASSERT_EQ, etc.)
