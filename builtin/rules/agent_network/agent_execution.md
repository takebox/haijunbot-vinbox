---
name: agent_execution
description: Triggered when there is a need to guide an Agent on how to specifically execute a task. Triggered whenever the user mentions "Agent execution", "task execution", "execution workflow", or "collaborative execution". Not triggered: only creating an Agent without involving execution; only scheduling and assigning tasks (use the intelligent_scheduling rule); single-Agent work that does not involve collaboration.
license: MIT
---

# Agent Execution Rule

## Clarifying the Core Concepts

**Agent (intelligent entity)**:

- An independent intelligent entity, each with its own working directory, model, and task
- Created with the `create_agent` operation of the `gateway_manager` tool
- agent_type must be `'agent'` or `'codeagent'`
- Examples: knowledge base Agent, monitoring Agent, scheduling Agent

**Tool (tool)**:

- A functional module called by Agents
- Created with the `meta_agent` tool (not in this rule's scope)
- Examples: memory tool, execute_script tool, read_code tool

**Common error warnings**:

- ❌ Confusing the concepts of an Agent and a tool
- ❌ Using the wrong agent_type (such as 'knowledge', 'monitor', etc.)
- ❌ Creating an Agent using the method for creating tools

## Task Reception

### 1. Task understanding

**Understanding mechanism:**

- **Must**: analyze the task description and requirements in detail
- **Must**: clarify the task goals, constraints, and acceptance criteria
- **Must**: identify the key points and difficulties of the task
- **Must**: confirm the understanding of the task is correct
- **Forbidden**: acting hastily without fully understanding the task

### 2. Capability matching

**Matching mechanism:**

- **Must**: assess whether one's own capabilities fit the task's needs
- **Must**: identify capability gaps and formulate compensating strategies
- **Must**: request help from other Agents when necessary
- **Must**: ensure having the capability to complete the task
- **Forbidden**: accepting tasks beyond one's own capabilities

### 3. Resource preparation

**Preparation content:**

- **Must**: prepare the necessary tools and environment
- **Must**: obtain the required knowledge and information
- **Must**: plan the execution time and resources
- **Must**: ensure the resources are available and sufficient
- **Forbidden**: acting hastily with insufficient resources

## Execution Workflow

### 1. Execution plan

**Plan formulation:**

- **Must**: formulate a detailed execution plan
- **Must**: clarify the execution steps and their order
- **Must**: set milestones and checkpoints
- **Must**: plan risk response strategies
- **Forbidden**: acting blindly without a plan

### 2. Step implementation

**Implementation conventions:**

- **Must**: implement step by step according to the plan
- **Must**: verify the result after each step completes
- **Must**: record the execution process and results
- **Must**: adjust the plan in time to respond to changes
- **Forbidden**: skipping the verification step

### 3. Quality check

**Check mechanism:**

- **Must**: perform a quality check during execution
- **Must**: ensure the output meets the requirements
- **Must**: verify the correctness of the functionality
- **Must**: check the performance metrics
- **Forbidden**: ignoring quality issues

## Collaborative Execution

### 1. Task decomposition

**Decomposition principles:**

- **Must**: decompose complex tasks into subtasks
- **Must**: clarify the dependency relationships between subtasks
- **Must**: reasonably assign subtasks to other Agents
- **Must**: ensure the decomposed tasks can be executed independently
- **Forbidden**: decomposing with too fine or too coarse granularity

### 2. Parallel execution

**Execution strategy:**

- **Must**: identify the subtasks that can be executed in parallel
- **Must**: coordinate multiple Agents working in parallel
- **Must**: manage resource conflicts during parallel execution
- **Must**: monitor the progress of parallel execution
- **Forbidden**: ignoring the coordination of parallel execution

### 3. Result integration

**Integration method:**

- **Must**: collect the results of all subtasks
- **Must**: verify the consistency of the results
- **Must**: integrate the results into a final output
- **Must**: handle result conflicts and exceptions
- **Forbidden**: ignoring the quality of result integration

## Result Reporting

### 1. Report format

**Format conventions:**

- **Must**: use a standardized report format
- **Must**: include the execution result, process records, and problem feedback
- **Must**: provide a clear summary and conclusions
- **Must**: attach necessary evidence and data
- **Forbidden**: the report content being incomplete or unclear

### 2. Progress updates

**Update mechanism:**

- **Must**: update the execution progress regularly
- **Must**: report the problems and difficulties encountered
- **Must**: clarify the circumstances of plan adjustments
- **Must**: provide a plan for the next actions
- **Forbidden**: updating progress untimely

### 3. Problem feedback

**Feedback mechanism:**

- **Must**: feed back the problems encountered during execution in time
- **Must**: analyze the causes and impact of the problems
- **Must**: propose solution suggestions
- **Must**: request necessary support and help
- **Forbidden**: hiding problems or delaying feedback

## Learning During Execution

### 1. Experience recording

**Recording content:**

- **Must**: record the lessons learned during the execution process
- **Must**: record successful experiences and failure lessons
- **Must**: record effective solutions
- **Must**: record areas that can be improved
- **Forbidden**: ignoring experience recording

### 2. Pattern recognition

**Recognition method:**

- **Must**: analyze the patterns in the execution process
- **Must**: identify effective execution strategies
- **Must**: identify common problem patterns
- **Must**: form reusable knowledge
- **Forbidden**: ignoring pattern recognition

### 3. Capability improvement

**Improvement mechanism:**

- **Must**: improve execution capability based on experience
- **Must**: learn new tracks and methods
- **Must**: optimize the execution workflow and strategies
- **Must**: share learning achievements with other Agents
- **Forbidden**: ceasing learning and progress

## Checklist

After executing the task, be sure to confirm:

- [ ] The task understanding is accurate without errors
- [ ] Capabilities match and resources are sufficient
- [ ] The execution plan is detailed and feasible
- [ ] The execution process is standardized and orderly
- [ ] Collaborative execution is efficient and coordinated
- [ ] The result report is complete and clear
- [ ] Experience learning is ongoing
