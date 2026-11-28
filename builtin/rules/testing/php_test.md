---
name: php_test
description: Triggered when tests need to be written for a PHP project or a test framework needs to be configured. Triggered whenever the user mentions "PHP testing", "PHPUnit", "Codeception". Not triggered: testing non-PHP projects; code review; performance optimization.
---

# PHP Testing Standards

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

### PHPUnit (recommended)

**Installation command:**

```bash
composer require --dev phpunit/phpunit
```

**Run commands:**

```bash
phpunit                 # run all tests
phpunit tests/TestClass.php # run a specific file
phpunit --filter testMethod # run a specific test method
phpunit --coverage-html coverage/ # generate a coverage report
```

### Pest

**Installation command:**

```bash
composer require --dev pestphp/pest
```

**Run commands:**

```bash
./vendor/bin/pest       # run all tests
./vendor/bin/pest --filter test_name # run a specific test
```

## Test Cases You Must Write

### PHPUnit test case

```php
// tests/CalculatorTest.php
use PHPUnit\Framework\TestCase;

class CalculatorTest extends TestCase
{
    public function testAdd()
    {
        $calc = new Calculator();
        $this->assertEquals(5, $calc->add(2, 3));
    }

    public function testDivideByZero()
    {
        $calc = new Calculator();
        $this->expectException(DivisionByZeroError::class);
        $calc->divide(10, 0);
    }
}
```

### Pest test case

```php
// tests/CalculatorTest.php
use Tests\TestCase;

test('adds two numbers', function () {
    $calc = new Calculator();
    expect($calc->add(2, 3))->toBe(5);
});
```

## Test Class and Method Conventions

### PHPUnit conventions

- **Must**: Test classes extend `TestCase`
- **Must**: Test methods start with `test` or use the `@test` annotation
- **Must**: Test methods must be `public`

### Pest conventions

- **Must**: Define tests with the `test()` function
- **Must**: Use descriptive test names

## Test Execution Checklist

Before committing code, be sure to confirm:

- [ ] **Run tests immediately after writing them**
- [ ] **All tests pass**
- [ ] **If it fails, fix it until it passes**
- [ ] Test classes extend TestCase (PHPUnit)
- [ ] Test methods start with `test` or use the `@test` annotation
- [ ] Tests cover the normal case
- [ ] Tests cover the boundary case
- [ ] Tests cover the exception case
