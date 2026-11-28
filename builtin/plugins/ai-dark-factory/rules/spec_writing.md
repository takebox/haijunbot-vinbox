---
name: spec_writing
description: Authoring standards for NLSpec (natural language spec) in the AI Agent dark factory. Triggered when defining the input spec of a dark factory pipeline or writing requirements as a structured spec. Ensures the spec contains the four elements Goal/Constraints/Interfaces/Non-goals, makes constraints explicit, and keeps one feature per spec.
---

# NLSpec Authoring Standards

## What Is NLSpec

NLSpec (Natural Language Spec) is the **input** to the AI dark factory pipeline. It is a structured English description with formal constraints, precise enough that the coding agent cannot fill in gaps with its own judgment.

The dark factory's principle is: **specs in, working software out**. The quality of the spec directly determines the quality of the output—vague specs fail, clear specs succeed.

## Four Elements (All Required)

A qualified NLSpec must contain the following four parts:

1. **Goal**: what to build. State the feature and its value in one sentence.
2. **Constraints**: hard limits. Tech stack, performance metrics, security requirements, compatibility, unusable approaches. **Constraints must be explicit**—the agent cannot fill in gaps with its own judgment.
3. **Interfaces**: external contracts. Function signatures, API endpoints, data structures, input/output formats, error semantics.
4. **Non-goals**: clearly state **what not to do**. Prevents the agent from over-designing or overstepping.

## Authoring Principles

- **Make constraints explicit**: write out all implicit assumptions. For example, "add auth" is too vague; write "add an OAuth2 PKCE flow, with these 5 constraints".
- **One feature per spec**: giant specs overwhelm the context window. Each spec focuses on a single feature and remains independently evaluable.
- **Verifiable**: each Goal should be verifiable through some acceptance scenario. A goal that cannot be verified is equivalent to no goal.
- **Precise interfaces**: define interfaces down to parameter types, return structures, and error code levels, so the generator does not need to guess.
- **Clear Non-goals**: clarify the boundaries to prevent the agent from deviating from the main line to implement extra features.

## Common Failure Modes

- **Vague spec**: the agent cannot infer the intent and produces generic code.
- **Giant spec**: overwhelms the context window, causing omissions and inconsistencies.
- **Missing constraints**: the agent fills in gaps with its own judgment and makes wrong technology choices.
- **No acceptance criteria**: cannot assess whether the output meets the standard.

## Working with Tools

After writing the spec, use the `spec_validator` tool to verify that it contains the four elements; use the `holdout_generator` tool to generate hidden acceptance scenarios (invisible to the coding agent).
