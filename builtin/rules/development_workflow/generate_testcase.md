---
name: generate_testcase
description: Triggered when test cases need to be generated based on requirements. Triggered whenever the user mentions "test case", "TestCase", "case generation", or "integration test case". Not triggered: only writing unit test code; only running tests without generating cases; debugging test failure issues.
---

# Textual Test Case Generation Rule

## Rule Overview

This rule guides how to generate structured textual test cases based on project requirement documents and code interfaces, to guide later integration test development. The generated test case file will be written to `.haijunbot/rules/spec/test_cases.md`.

## The Principles You Must Follow

### 1. The Requirement-Driven Principle

**Requirements:**

- **Must**: prioritize reading the Spec files in the `.haijunbot/rules/spec/` directory as the requirement source
- **Must**: design test cases based on the functional behavior and acceptance criteria defined in the Spec
- **Must**: each acceptance criterion corresponds to at least one test case
- **Forbidden**: conjecturing test scenarios detached from the requirement documents
- **Forbidden**: omitting the boundary conditions and exception handling defined in the Spec

### 2. The Case Completeness Principle

**Requirements:**

- **Must**: cover functional testing (normal flows)
- **Must**: cover boundary condition testing (empty values, extreme values, critical values)
- **Must**: cover exception handling testing (incorrect inputs, abnormal states)
- **Must**: cover interface compatibility testing (parameter types, return value formats)
- **Forbidden**: covering only normal flows while ignoring exceptional scenarios

### 3. The Case Structuring Principle

**Requirements:**

- **Must**: each case contains: case ID, case name, precondition, test steps, expected result, priority
- **Must**: organize test cases in groups by functional module
- **Must**: use the three-tier classification for priorities: P0 (core functionality), P1 (important functionality), P2 (auxiliary functionality)
- **Must**: the case ID format is `TC-{module abbreviation}-{sequence number}` (e.g. TC-AUTH-001)
- **Forbidden**: using vague expected results (such as "returns normally", "no errors")

## The Operations You Must Execute

### Operation 1: Collect requirement information

**Execution steps:**

1. Read all Spec files in the `.haijunbot/rules/spec/` directory
2. Extract the functional overview, interface definitions, functional behavior, and acceptance criteria of each Spec
3. If there are no Spec files, analyze the interface definitions and docstrings in the source code

### Operation 2: Analyze the code interfaces

**Execution steps:**

1. Browse the source directory and identify the public interfaces (functions, classes, API endpoints)
2. Read the parameter definitions, return value types, and docstrings of the interfaces
3. Identify the call relationships and dependencies between interfaces

### Operation 3: Design the test cases

**Execution steps:**

1. Based on the Spec's acceptance criteria, design normal-flow cases for each functional point
2. Based on the boundary conditions, design boundary value test cases
3. Based on the exception handling descriptions, design exceptional scenario cases
4. Based on the interface definitions, design interface compatibility cases
5. Assign a priority (P0/P1/P2) to each case

### Operation 4: Generate the test case file

**Execution steps:**

1. Organize the test cases in groups by functional module
2. Use the `write_file` tool to write the test cases to `.haijunbot/rules/spec/test_cases.md`
3. Ensure each case has a complete structure and explicit expected results

### Test Case File Template

```markdown
# Test Case Document

## Module: [module name]

### [module name] functional testing

| Case ID       | Case name   | Precondition   | Test steps               | Expected result | Priority |
| ------------- | ----------- | -------------- | ------------------------ | --------------- | -------- |
| TC-{MOD}-001  | [case name] | [precondition] | 1. [step 1]<br>2. [step 2] | [specific expected result] | P0       |

### [module name] boundary condition testing

| Case ID        | Case name   | Precondition   | Test steps   | Expected result | Priority |
| -------------- | ----------- | -------------- | ------------ | --------------- | -------- |
| TC-{MOD}-B001  | [case name] | [precondition] | 1. [step 1]  | [specific expected result] | P1       |

### [module name] exception handling testing

| Case ID   | Case name | Precondition | Test steps | Expected result | Priority |
| --------- | --------- | ------------ | ---------- | --------------- | -------- |
```

## Checklist

After completing the task, be sure to confirm:

- [ ] All Spec files have been read and the requirements extracted
- [ ] The code interface definitions have been analyzed
- [ ] Each acceptance criterion corresponds to at least one test case
- [ ] Functional testing, boundary conditions, exception handling, and interface compatibility are covered
- [ ] Each case has a complete structure (ID, name, precondition, steps, expected result, priority)
- [ ] The cases are organized in groups by functional module
- [ ] The test case file has been written to `.haijunbot/rules/spec/test_cases.md`
- [ ] The expected results are specific and clear, and verifiable
