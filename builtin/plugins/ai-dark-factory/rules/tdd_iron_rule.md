---
name: tdd_iron_rule
description: The TDD iron rule of the AI Agent dark factory. Triggered when the generator agent needs to write code. Requires no code without a failing test, writing tests before implementation, and following test-driven development discipline.
---

# TDD Iron Rule

## Core Principles

**No production code without a failing test**. This is the iron rule of the dark factory generator—write the test first, then the implementation, until the test passes.

TDD ensures the output is verifiable and is the precondition for the isolated evaluator to objectively assess the output. Code without tests cannot be evaluated and therefore cannot pass the gate.

## Discipline Requirements

1. **Write the test first**: before implementing any feature, first write a test that verifies it.
2. **Red-green-refactor**: first see the test fail (red), then write the implementation to make it pass (green), and finally refactor (keeping the tests green).
3. **Tests as contract**: tests define the expected behavior of the interface and are the executable form of the interface contract.
4. **Do not skip**: writing code without a failing test is considered a violation.

## Position in the Pipeline

```text
planner decomposes the task
  → generator writes the test first (red)
  → generator writes the implementation (green)
  → validator independently evaluates with holdout scenarios
  → orchestrator aggregates the report → human approval checkpoint
```

## Relationship to Holdout Scenarios

- **TDD tests**: the unit/integration tests written by the generator itself and visible—used to drive the implementation.
- **Holdout scenarios**: the hidden acceptance scenarios held by the evaluator and invisible to the coding agent—used for independent evaluation.

The two are complementary: TDD drives the correct implementation, and holdout verifies that the standard is truly met.

## Common Pitfalls

- **Skipping tests**: writing the implementation directly, producing unverifiable output.
- **Tests too weak**: only testing the happy path, not boundaries and exceptions.
- **Tests isomorphic to the implementation**: the tests merely restate the implementation logic and have no independent value.
- **Testing just to pass**: making the tests accommodate the implementation instead of the implementation satisfying the tests.

## Working with Tools

When the generator writes spec-driven tests, refer to the `spec_writing` rule to ensure the four spec elements are clear; in the evaluation stage, use the `gate_calculator` tool to compute the gate pass rate.
