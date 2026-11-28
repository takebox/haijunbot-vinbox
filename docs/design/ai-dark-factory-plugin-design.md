# AI Agent Dark Factory Plugin Implementation Design Plan

> Design date: 2026-10-06
> Basis: `docs/design/ai-dark-factory-research.md` (research report)
> Administrator decision: implement for the best effect, **may be not fully unattended** (pure unattended operation easily goes wrong; keep a human approval gateway at the gate).

## 1. Plugin Positioning

**AI Dark Factory** is a software delivery model: AI Agents autonomously write, test, and evaluate code ("running with the lights off"), while human engineers define the spec, review pass/fail reports, and control the trust boundary. **Specs in, working software out**.

This plugin turns HaijunBot into an AI dark factory: given an NLSpec (natural language spec), the system orchestrates multiple Agents through "planning → generation → verification → gate → delivery", with humans intervening only at approval gateways, not writing code line by line or reviewing code line by line.

**Key design orientation (administrator decision)**: do not pursue fully unattended, fully automatic auto-merge; instead **keep a human approval gateway at the evaluation gate** — the orchestrator aggregates the pass/fail reports from each validator and only enters delivery/merge after a human approves. This both fits the dark factory principle that "humans only review pass/fail reports" and avoids the runaway risk of purely unattended operation.

## 2. Plugin Directory Structure

```text
builtin/plugins/ai-dark-factory/
├── config.yaml                     # plugin metadata + load directories ({{plugin_dir}} template variable)
├── rules/                          # methodology rules (.md, with YAML front matter)
│   ├── spec_writing.md             # NLSpec writing specification
│   ├── holdout_discipline.md       # acceptance scenario isolation discipline
│   ├── tdd_iron_rule.md            # TDD iron rule
│   └── orchestration.md            # orchestration discipline + human approval gateway
├── tools/                          # tools (.py, class XxxTool)
│   ├── spec_validator.py           # validate NLSpec completeness
│   ├── holdout_generator.py        # generate holdout scenarios
│   └── gate_calculator.py          # evaluation gate calculation
└── orchestration/
    └── dark_factory_pipeline.yaml  # orchestration template (agents + flow, reference for dynamically generated orchestration files)
```

## 3. config.yaml Design

```yaml
name: ai-dark-factory
description: AI Agent dark factory — specs in, working software out. Orchestrates multiple Agents to autonomously write code/test/evaluate, with humans reviewing pass/fail reports to control the trust boundary.
version: 0.1.0
license: MIT
rules_load_dirs:
  - "{{plugin_dir}}/rules"
tool_load_dirs:
  - "{{plugin_dir}}/tools"
```

- `name`: `ai-dark-factory` (distinguished from the deleted industrial version `dark-factory`)
- `rules_load_dirs` / `tool_load_dirs`: use the `{{plugin_dir}}` template variable to point to directories inside the plugin, which are automatically rendered to the plugin's actual path after installation.
- After the plugin is installed to `~/.haijunbot/plugins/ai-dark-factory/`, it is automatically discovered at startup and merged into the global configuration.

## 4. Rule File List (rules/)

| File                    | Purpose          | Key Content                                                                                                                       |
| ----------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `spec_writing.md`       | NLSpec writing specification | The four elements Goal / Constraints / Interfaces / Non-goals; constraints must be explicit; one spec per feature; giant specs overwhelm the context |
| `holdout_discipline.md` | Acceptance scenario isolation discipline | The coding agent **never sees** the holdout scenarios; train/test separation prevents cheating; an independent evaluator tests with hidden scenarios |
| `tdd_iron_rule.md`      | TDD iron rule    | Do not write code without a failing test; write the test first, then implement                                                     |
| `orchestration.md`      | Orchestration discipline | sw-controller only coordinates and does not execute; four-layer architecture (Orchestrator/Planner/Generators/Validators); **human approval gateway** — humans review pass/fail reports at the gate |

Each rule file has YAML front matter (`name` / `description` / `license`).

## 5. Tool List (tools/)

| Tool Class              | Function               | Input → Output                                                              |
| ----------------------- | ---------------------- | --------------------------------------------------------------------------- |
| `SpecValidatorTool`     | Validate NLSpec completeness | Spec text → whether it contains the four elements Goal/Constraints/Interfaces/Non-goals + hints for missing items |
| `HoldoutGeneratorTool`  | Generate holdout scenarios | Feature description + count → hidden acceptance scenario list (marked as invisible to the coding side) |
| `GateCalculatorTool`    | Evaluation gate calculation | Each scenario pass/fail → scenario pass rate, false positive rate, human override rate + whether it meets the bar (≥90%) |
| `PipelineGeneratorTool` | Generate orchestration YAML | Feature description → sw-controller-style multi-Agent pipeline orchestration YAML |

Each tool class implements the `name` / `description` / `parameters` / `check` / `execute` interface (see `src/haijunbot/haijunbot_tools/read_symbols.py`).

## 6. Orchestration Template Design (orchestration/dark_factory_pipeline.yaml)

Reusing HaijunBot's `@OrganizeAgents` + YAML orchestration file mechanism (format referenced from `builtin/agent_orchestration/self_evolving_network.yaml`), a pipeline orchestration template is preloaded, embodying the four-layer architecture:

```text
planner — reads the spec, breaks down tasks, generates an implementation plan
  → generators — write code from the spec (TDD: write tests first)
  → validators — run tests and evaluate with holdout scenarios
  → orchestrator — aggregates pass/fail reports → human approval gateway
```

In the orchestration template, each agent's responsibility description is injected via the `task` field. **`no_interaction_mode` is deliberately not set**: this plugin insists on "not fully unattended", keeping a human-in-the-loop gateway at every stage (planning/generation/verification/gate); the gate decision agent outputs a pass/fail report and then stops, waiting for human approval and not merging automatically. This is an intentional design by the administrator, not an implementation gap.

## 7. "Not Fully Unattended" Human Approval Gateway Design

This is the core design orientation of this plan and the key difference from a pure dark factory (fully automatic auto-merge); **it is also a deliberate, intentional design by the administrator**: this plugin does not enable `no_interaction_mode` on orchestration agents by default, insisting that "humans review pass/fail reports and control the trust boundary", and is never purely unattended.

1. **Fully automatic segment**: from the spec to generators writing code and validators running holdout scenarios, everything is AI-driven. HaijunBot's underlying capabilities support unattended operation (`no_interaction_mode` + `hca -n --task-file` + `status_file`), but **this plugin does not enable it by default**, keeping a human-in-the-loop gateway at every stage.
2. **Human approval gateway**: after validators produce pass/fail reports, **the orchestrator does not merge automatically**; instead it outputs a structured approval report (per-scenario pass rate, failing scenario details, change diff summary) for a human to approve.
3. **After approval**: once a human confirms, it enters the delivery/merge stage (which can be automated again).
4. **Gate criteria**: per the research report — only recommend approval when the scenario pass rate is ≥90%; only consider relaxing to automatic when the false positive rate is <5% and the human override rate is <10%.

This preserves the efficiency of a dark factory where "humans only review pass/fail reports, not code line by line", while controlling the trust boundary through human approval gateways and avoiding the runaway risk of purely unattended operation.

## 8. Reused HaijunBot Mechanisms (all verified to exist)

| Mechanism                         | Corresponding Dark Factory Layer | Location                                  |
| --------------------------------- | ----------------------- | ----------------------------------------- |
| `@OrganizeAgents` + YAML orchestration file | Orchestrator / Planner  | `builtin/agent_orchestration/` has format examples |
| Multi-Agent collaboration / communication / sub-agents | Generators / Validators | Built-in                                  |
| `no_interaction_mode` orchestration field | Unattended execution    | Orchestration file field                  |
| `hca -n --task-file`              | Non-interactive pipeline entry point | `haijunbot.py:819`                           |
| `status_file` mechanism           | Automatic gate status reporting | `haijunbot.py:1053`                          |
| Three-layer rule system + AGENTS.md compatibility | Agent context           | Built-in                                  |

> Note: The SDKs mentioned in the research report (`pipeline` / `run_agents_parallel` / `run_structured`) were verified to **not exist in the current code**; this plan does not depend on them and uses only the verified mechanisms above.

## 9. Implementation Steps

1. Create the `builtin/plugins/ai-dark-factory/` directory structure and `config.yaml` (validated with yamllint)
2. Write the 4 rule files (validated with markdownlint)
3. Write the 4 tool files (verified to pass)
4. Write the orchestration template `dark_factory_pipeline.yaml` (validated with yamllint)
5. Verify: `haijunbot --install-plugin builtin/plugins/ai-dark-factory` installs successfully + `haijunbot --list-plugins` recognizes it
6. git commit the plugin source

## 10. Verification Method

- **config.yaml / orchestration YAML**: passes yamllint
- **Rule .md files**: pass markdownlint
- **Tool .py files**: valid input returns correct results, invalid input returns errors
- **Plugin installation**: `haijunbot --install-plugin` succeeds, `haijunbot --list-plugins` can list `ai-dark-factory`
