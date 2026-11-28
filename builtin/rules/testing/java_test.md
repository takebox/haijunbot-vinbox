---
name: java_test
description: Triggered when tests need to be written for a Java project or a test framework needs to be configured. Triggered whenever the user mentions "Java testing", "JUnit", "TestNG", "Mockito". Not triggered: testing non-Java projects; code review; performance optimization.
---

# Java Testing Standards

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

### JUnit 5 (recommended)

**Maven run commands:**

```bash
mvn test                  # run all tests
mvn test -Dtest=TestClass # run a specific test class
```

**Gradle run commands:**

```bash
gradle test               # run all tests
gradle test --tests TestClass # run a specific test class
```

### JUnit 4

**Run commands:**

```bash
mvn test                  # run all tests
```

## Test Cases You Must Write

### JUnit 5 test case

```java
// src/test/java/CalculatorTest.java
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CalculatorTest {
    @Test
    void testAdd() {
        Calculator calc = new Calculator();
        assertEquals(5, calc.add(2, 3));
    }

    @Test
    void testDivideByZero() {
        Calculator calc = new Calculator();
        assertThrows(ArithmeticException.class, () -> {
            calc.divide(10, 0);
        });
    }
}
```

### JUnit 4 test case

```java
import org.junit.Test;
import static org.junit.Assert.*;

public class CalculatorTest {
    @Test
    public void testAdd() {
        Calculator calc = new Calculator();
        assertEquals(5, calc.add(2, 3));
    }
}
```

## Test Execution Checklist

Before committing code, be sure to confirm:

- [ ] **Run tests immediately after writing them**
- [ ] **All tests pass**
- [ ] **If it fails, fix it until it passes**
- [ ] Tests cover the normal case
- [ ] Tests cover the boundary case
- [ ] Tests cover the exception case
- [ ] Use @BeforeEach/@AfterEach for setup and teardown (if needed)
