---
name: opensource_research
description: Triggered when an open-source project needs to be systematically researched. Triggered whenever the user mentions "research an open-source project", "open-source project analysis", "technical research", "competitor comparison", or "project selection research". Not triggered by: only using an open-source project without researching it; only viewing a project's README; only installing/deploying an open-source project.
---

# Open-Source Software Research

## Rule Overview

This rule provides a systematic method and process for researching open-source software, used to deeply understand an open-source project's technical principles, architecture design, and implementation details.

## Research Goals

Through systematic research, comprehensively master the following aspects of an open-source project:

- **Development background**: project origin, development history, community ecosystem
- **Problem solving**: core problems, solutions, technical innovations
- **Technical architecture**: system architecture, component design, core tech stack
- **Strengths and weaknesses**: technical highlights, limitations, applicable scenarios
- **Competitor comparison**: similar products, difference analysis, selection recommendations
- **Future development**: evolution direction, trend prediction, follow-up strategy

## Research Process

### Stage 1: Project Background Research

**Rule to use**: `{{ rule_file_dir }}/opensource_research/01_background_research.md`

**Research content**:

- Project origin and development history
- Core maintainers and community status
- Project positioning and application scenarios

**Output**: `01_project_background.md`

### Stage 2: Problem and Solution Research

**Rule to use**: `{{ rule_file_dir }}/opensource_research/02_problem_solution.md`

**Research content**:

- The core problem the project aims to solve
- The technical challenges and difficulties of the problem
- The project's solution and technical path

**Output**: `02_problem_solution.md`

### Stage 3: Key Technology Research

**Rule to use**: `{{ rule_file_dir }}/opensource_research/03_key_technologies.md`

**Research content**:

- Core technologies and algorithms
- Technical innovations and distinctive features
- Considerations behind technology selection

**Output**: `03_key_technologies.md`

### Stage 4: Architecture and Design Research

**Rule to use**: `{{ rule_file_dir }}/opensource_research/04_architecture_design.md`

**Research content**:

- Overall system architecture
- Core components and their responsibilities
- Interaction and collaboration between components
- Design patterns and design principles

**Output**: `04_architecture_design.md`

### Stage 5: Strengths and Weaknesses Analysis

**Rule to use**: `{{ rule_file_dir }}/opensource_research/05_pros_cons.md`

**Research content**:

- The project's technical highlights and strengths
- Existing limitations and shortcomings
- Applicable scenarios and constraints

**Output**: `05_pros_cons.md`

### Stage 6: Competitor Comparison Analysis

**Rule to use**: `{{ rule_file_dir }}/opensource_research/06_competitor_analysis.md`

**Research content**:

- Identify similar tools and competitors
- Compare and analyze the pros and cons of each option
- Provide selection recommendations

**Output**: `06_competitor_analysis.md`

### Stage 7: Evolution Direction Research

**Rule to use**: `{{ rule_file_dir }}/opensource_research/07_evolution_direction.md`

**Research content**:

- The project's latest developments and trends
- Technology evolution direction
- Community roadmap and plans

**Output**: `07_evolution_direction.md`

### Stage 8: Follow-Up Strategy Formulation

**Rule to use**: `{{ rule_file_dir }}/opensource_research/08_followup_strategy.md`

**Research content**:

- How to continuously follow the project's development
- Ways to participate in the community
- Application and integration strategy

**Output**: `08_followup_strategy.md`

### Stage 9: Summary Report Generation

**Rule to use**: `{{ rule_file_dir }}/opensource_research/09_summary_report.md`

**Research content**:

- Integrate the research results of each stage
- Generate a comprehensive analysis report
- Provide decision recommendations

**Output**: `summary_report.md`

## Research Quality Requirements

### Reliability of Information Sources

- **Must**: prioritize consulting official documentation, authoritative technical blogs, and academic papers
- **Must**: information must cite its source (link, document title, author)
- **Forbidden**: relying on a single information source; cross-validate
- **Forbidden**: using unverified information and guesses

### Research Depth Requirements

- **Must**: deeply research the technical principles and implementation details
- **Must**: analyze the essence of the problem, not surface phenomena
- **Must**: provide concrete data, cases, and evidence
- **Forbidden**: speaking in generalities and lacking in-depth analysis

### Research Output Requirements

- **Must**: each stage produces an independent markdown document
- **Must**: the document contains a detailed analysis process and conclusions
- **Must**: all conclusions are well-founded, with cited sources
- **Must**: finally generate an integrated summary report

## Research Tools and Methods

### Information Collection Tools

- **search_web**: search web information, technical documentation, and blog posts
- **read_webpage**: read web page content and official documentation
- **load_rule**: load relevant technical rules and best practices

### Research Methods

- **Literature review**: systematically read official documentation, technical papers, and design documents
- **Code analysis**: analyze source code, design documents, and architecture diagrams
- **Comparative study**: compare different options and analyze competitors
- **Case study**: analyze specific application scenarios and usage cases

## Execution Checklist

Before starting research, be sure to confirm:

- [ ] Clarify the research goals and scope
- [ ] Create a research working directory
- [ ] Prepare the research document templates

After completing the research, be sure to confirm:

- [ ] The research documents for all 9 stages are complete
- [ ] Each document has a clear structure and conclusions
- [ ] All information has credible sources cited
- [ ] The final summary report has been generated
- [ ] The research conclusions have sufficient basis and evidence
