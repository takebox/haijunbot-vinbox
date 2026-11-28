# AI Agent Dark Factory (AI Dark Factory) Research Report

> Research date: 2026-10-06
> Background: The administrator corrected the direction — what is wanted is an "Agent dark factory", not an industrial dark factory. This report studies the concept, architecture, and implementation approach of the AI Agent dark factory, providing a basis for designing the HaijunBot version of the dark factory plugin.

## 1. What Is an AI Agent Dark Factory

**AI Dark Factory** is a **software delivery model**: AI Agents autonomously write, test, and ship code ("running with the lights off"). Human engineers define the spec, review the output, and control the trust boundary. **Specs in, working software out** — no human writes code, and no human reviews code line by line.

The name is borrowed from the manufacturing "lights-out factory" (an unattended, fully automated factory). The AI dark factory pursues the same ideal: given a well-defined spec, the system can autonomously produce, test, review, and deliver a complete software module, with humans intervening only at approval gates, not coding line by line.

**Source**: Proposed by Dan Shapiro (Glowforge) in January 2026; it is the **Level 5 endpoint** of AI-driven development maturity.

## 2. The Six-Level Framework of AI-Driven Development

| Level | Name         | What You Are Doing    | Key Unlock                |
| ---- | ------------ | ------------------ | ------------------------- |
| L0   | Manual       | Hand-writing every character | —                         |
| L1   | Task delegation | Handing off independent tasks | Learn to write good prompts |
| L2   | Collaboration | Pair programming with AI | AGENTS.md + structured context |
| L3   | Human review loop | Review diffs instead of writing code | Specs + holdout scenarios |
| L4   | Spec-driven  | Write specs, verify results | Automated evaluation + auto-merge |
| L5   | **Dark factory** | Design systems rather than features | Digital twins + full pipeline |

Most developers stop at L2 (pair programming). Research shows (METR 2025 randomized trial) that L2 developers are actually 19% slower, because they review every diff. Crossing past L2 requires writing structured specs and giving up line-by-line code review.

## 3. The Three Core Elements (all required)

A true dark factory must have all three of the following at once; otherwise it degenerates into "agentic coding with automation enhancements":

1. **Spec-driven input**: NLSpec (natural language spec) as input. An NLSpec is structured English with formalized constraints — precise enough that the agent cannot fill gaps with judgment. Typical structure: Goal / Constraints / Interfaces / Non-goals.

2. **Isolated evaluator + holdout scenarios**: the coding agent **never sees** the acceptance scenarios (holdout scenarios). An independent evaluator agent tests the produced code with these hidden scenarios. This is train/test separation — preventing a reasoning model from "overfitting" to the specs it has seen (research confirms that reasoning models will cheat for the specs they can see, even with explicit counter-instructions).

3. **Zero human diff review**: humans do not review code line by line, they only review the evaluator's **pass/fail report**. The quality gate changes from "human code review" to "automated scenario evaluation".

## 4. The Four-Layer Core Architecture

```text
┌─────────────────────────────────────────────┐
│  Orchestrator — the pipeline's nervous system│
│  Read spec → dispatch generators → dispatch validators → gate │
├─────────────────────────────────────────────┤
│  Planner — break down tasks, generate a plan │
├─────────────────────────────────────────────┤
│  Generators — write code from the spec       │
├─────────────────────────────────────────────┤
│  Validators — run tests, evaluate scenarios  │
└─────────────────────────────────────────────┘
```

Key insight: **design the orchestration logic first, then focus on individual agents**. A strong generator agent with a weak orchestrator performs poorly; a simple generator agent with a well-designed orchestrator wins instead. The orchestrator is the pipeline's "nervous system", not an afterthought.

## 5. Key Concepts

- **NLSpec (natural language spec)**: structured English containing Goal / Constraints / Interfaces / Non-goals. Constraints must be explicit; the agent cannot fill gaps with judgment.
- **Holdout scenarios**: acceptance tests written in plain English that the coding agent never sees. The evaluator agent uses them to test the produced code. Each scenario is run 3 times, passing 2-of-3 to smooth out LLM variance.
- **Auto-merge gate**: auto-merge is only allowed when ≥90% of scenarios pass; if <90%, retry. Do not enable it prematurely — first collect 20-30 PRs comparing the evaluator's judgment with human judgment, and only enable it when (scenario pass rate ≥90%, false positive rate <5%, human override rate <10%) are met.
- **AGENTS.md**: structured project context for agents (build steps, conventions, architecture rules). An open standard used by 60,000+ projects. It is the foundation of every level.
- **Digital twins**: high-fidelity behavioral clones of external services (Stripe/Okta/databases). They let agents test in complete isolation — millisecond-level runs, no API key, injectable faults, deterministic. AI makes building digital twins economically viable.
- **Ephemeral environment**: the PR is deployed as a container revision, and the evaluator tests within it.

## 6. Full Pipeline (Level 5)

```text
Issue Tracker → Coding Agent → Ephemeral Env → Evaluator Agent → Auto-Merge Gate → Production deploy
(Jira/Linear/GitHub Issues)  (read AGENTS.md+spec    (PR deployed as container    (run holdout     (≥90% pass→merge   (standard CI/CD
                              →implement→test)        revision)            scenarios 3x)   <90%→retry)         unchanged)
                                                                                           ↑
                                                     Monitoring (alerts become the next round's bug spec) — feedback loop
```

## 7. Reference Implementations

### 7.1 GitHub wenxueliu/darkfactory (most direct reference)

**A human-machine collaborative software generation system**: coordinates multiple specialized AI Agents into a pipeline, automating end-to-end from requirements to delivery. It follows **acceptance-driven development** and the **TDD iron rule** (do not write code without a failing test). 32 tracks cover the complete E2E pipeline.

Agent architecture (v2):

```text
sw-controller (master control: Intent Gate + Phase Transition + delegation discipline — coordinates only, does not execute)
  ├── [Requirements layer] sw-requirements-clarifier / sw-value-judgment
  ├── [Planning layer] sw-strategic-planner (+ pre-planning-consultant / plan-reviewer / codebase-explorer / external-researcher)
  ├── [Design layer] sw-brainstorming / sw-feature-designer → sw-service-designer × N → sw-e2e-designer
  ├── [Decomposition layer] sw-task-decomposer
  ├── [Execution layer] sw-plan-executor → sw-worktree-controller × N → sw-tdd-agent (+ reviewer-logic/security/performance/context)
  ├── [Testing layer] sw-integration-tester
  ├── [Delivery layer] sw-delivery-manager
  └── [Infrastructure] sw-setup / sw-knowledge-agent / sw-systematic-debugging / sw-verification-before-completion / ...
```

Configuration items: `architecture` (monolith/microservices), `business_domain` (general/fintech/ecommerce/internal-tools), `min_iteration_before_human` (how many autonomous AI iterations before escalating to a human), `enabled_reviewers` (security,logic,performance), `merge_strategy`.

### 7.2 bborbe/agent's Dark Factory CI/CD pipeline

An automated implementation pipeline used to evolve an agent codebase. Architecture changes are defined as specs, and after human approval Haijun Code implements them in ephemeral containers. Described in README lines 62-71.

## 8. Real-World Case Study

**StrongDM's Attractor system**: three engineers used this model to produce **16,000 lines of Rust + 9,500 lines of Go + 6,700 lines of TypeScript** from 3 markdown spec files. No human wrote code, and no human reviewed code.

| Metric       | Traditional Development | Dark Factory                |
| ------------ | ---------------- | --------------------------- |
| 8-person team output | 8 engineers      | 25-30 engineer equivalents  |
| Main bottleneck | Developer time   | Spec quality                |
| Dominant cost | Salaries         | ~$1k/day/engineer-equivalent (token) |
| Quality gate | Human code review | Automated scenario evaluation |
| Feedback loop | Hours to days    | Minute-level                |

## 9. Common Pitfalls

- **Vague spec (L3+)**: the agent cannot infer intent. "Add auth" will fail; "Add an OAuth2 PKCE flow with these 5 constraints" will succeed.
- **Leaked scenarios (L4+)**: if the coding agent sees the holdout scenarios, it optimizes for them rather than solving the problem. Strict isolation is non-negotiable.
- **Skipping AGENTS.md (all levels)**: without structured context, the agent produces generic code.
- **Premature auto-merge (L4)**: enable it only after 20-30 PRs prove the evaluator agrees with human judgment.
- **J-curve (L2→3)**: it gets slower before you learn to write specs; this is normal, so persist.
- **Giant spec (L3+)**: large specs overwhelm the context window. One spec per feature.

## 10. Implications and Implementation Suggestions for HaijunBot

HaijunBot already has the underlying capabilities to build a dark factory plugin:

- **Orchestration mechanism**: `@OrganizeAgents` + YAML orchestration files, enabling one-click batch creation of multi-Agent collaboration topologies (corresponding to the Orchestrator/Planner layer)
- **Multi-Agent collaboration**: inter-Agent communication, point-to-point, group chat, sub-agents (corresponding to the Generators/Validators layer)
- **Unattended operation**: `no_interaction_mode=True` process-level unattended operation + scheduled tasks (corresponding to the fully automatic pipeline)
- **SDK**: `pipeline` / `run_agents_parallel` / `run_structured` (corresponding to orchestration and structured output)
- **CI integration**: `hca -n --task-file` non-interactive + status_file mechanism (corresponding to the automatic gate)
- **Rule system**: three-layer rule system (builtin/project/global) + AGENTS.md compatibility (corresponding to agent context)

**Suggested plugin form**: a plugin package installable via `haijunbot --install-plugin`, providing:

1. **Rule files**: defining the dark factory methodology (spec writing specification, holdout scenario isolation discipline, TDD iron rule, orchestration discipline)
2. **Tools**: spec generation/validation, holdout scenario generation, evaluation gate calculation, orchestration file generation
3. **Orchestration template**: a preset sw-controller-style multi-Agent pipeline orchestration YAML

> Note: This report is a research result. The specific plugin design must be confirmed with the administrator before implementation.
