---
name: javascript_test
description: Triggered when tests need to be written for a JavaScript/TypeScript project or a test framework needs to be configured. Triggered whenever the user mentions "JavaScript testing", "TypeScript testing", "frontend testing", "Jest", "Mocha", "Vitest". Not triggered: testing non-JS/TS projects; code review; performance optimization.
---

# JavaScript/TypeScript Testing Standards

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

### Jest (recommended)

**Installation command:**

```bash
npm install --save-dev jest
```

**Run commands:**

```bash
npm test                  # run all tests
npm test -- --watch       # watch mode
npm test -- file.test.js  # run a specific file
npm test -- --coverage    # show coverage
```

### Mocha + Chai

**Installation command:**

```bash
npm install --save-dev mocha chai
```

**Run commands:**

```bash
npm test                  # run all tests
npx mocha test/**/*.js    # run a specific directory
```

### Vitest (recommended for Vite projects)

**Installation command:**

```bash
npm install --save-dev vitest
```

**Run commands:**

```bash
npm test                  # run all tests
npm test -- --watch       # watch mode
```

## Test Cases You Must Write

### Jest test case

```javascript
// test/calculator.test.js
const { add, divide } = require("../src/calculator");

describe("Calculator", () => {
  test("adds two numbers", () => {
    expect(add(2, 3)).toBe(5);
  });

  test("throws error on divide by zero", () => {
    expect(() => divide(10, 0)).toThrow("Division by zero");
  });
});
```

### TypeScript + Jest test case

```typescript
// test/calculator.test.ts
import { add, divide } from "../src/calculator";

describe("Calculator", () => {
  it("adds two numbers", () => {
    expect(add(2, 3)).toBe(5);
  });
});
```

## Test Execution Checklist

Before committing code, be sure to confirm:

- [ ] **Run tests immediately after writing them**
- [ ] **All tests pass**
- [ ] **If it fails, fix it until it passes**
- [ ] Tests cover the normal case
- [ ] Tests cover the boundary case
- [ ] Tests cover the exception case
- [ ] Use descriptive test names
