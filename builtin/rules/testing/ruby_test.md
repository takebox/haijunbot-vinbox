---
name: ruby_test
description: Triggered when tests need to be written for a Ruby project or a test framework needs to be configured. Triggered whenever the user mentions "Ruby testing", "RSpec", "Minitest". Not triggered: testing non-Ruby projects; code review; performance optimization.
---

# Ruby Testing Standards

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

### RSpec (recommended)

**Installation command:**

```bash
gem install rspec
# or add to your Gemfile
gem 'rspec'
```

**Run commands:**

```bash
rspec                 # run all tests
rspec spec/file_spec.rb  # run a specific file
rspec -fd                # verbose output
rspec --format documentation # documentation-format output
```

### Minitest (standard library, no installation required)

**Run commands:**

```bash
ruby -I test test/test_file.rb  # run a specific file
rake test                        # run all tests (Rake)
```

## Test Cases You Must Write

### RSpec test case

```ruby
# spec/calculator_spec.rb
require_relative '../lib/calculator'

RSpec.describe Calculator do
  describe '#add' do
    it 'adds two numbers' do
      calc = Calculator.new
      expect(calc.add(2, 3)).to eq(5)
    end
  end

  describe '#divide' do
    it 'raises error on divide by zero' do
      calc = Calculator.new
      expect { calc.divide(10, 0) }.to raise_error(ZeroDivisionError)
    end
  end
end
```

### Minitest test case

```ruby
# test/test_calculator.rb
require 'minitest/autorun'
require_relative '../lib/calculator'

class TestCalculator < Minitest::Test
  def test_add
    calc = Calculator.new
    assert_equal 5, calc.add(2, 3)
  end
end
```

## Test Execution Checklist

Before committing code, be sure to confirm:

- [ ] **Run tests immediately after writing them**
- [ ] **All tests pass**
- [ ] **If it fails, fix it until it passes**
- [ ] Use descriptive test names
- [ ] Tests cover the normal case
- [ ] Tests cover the boundary case
- [ ] Tests cover the exception case
