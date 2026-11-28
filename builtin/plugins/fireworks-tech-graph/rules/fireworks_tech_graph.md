---
name: fireworks_tech_graph
description: Triggered when a technical diagram or a system/process visualization needs to be created. Triggered whenever the user mentions "draw a diagram", "draw one for me", "generate a diagram", "make a diagram", "architecture diagram", "flowchart", "visualization", "produce a diagram", or "diagram". Not triggered by: only viewing an existing image; only describing a diagram without generating one; plain text output that does not involve a diagram.
license: MIT
---

# Fireworks Tech Graph

Generate high-quality SVG technical diagrams and export them to PNG with `rsvg-convert`.

## Helper Scripts (Recommended)

This rule includes helper scripts and style reference files, located in the same directory as the rule file:

- `fireworks-tech-graph/scripts/` - helper scripts
- `fireworks-tech-graph/references/` - style reference files

### 1. generate-diagram.sh - Validate SVG and export PNG

```bash
# Assume the current directory is at the same level as fireworks-tech-graph
./fireworks-tech-graph/scripts/generate-diagram.sh -t architecture -s 1 -o ./output/arch.svg
```

### 2. generate-from-template.py - Create SVG from a template

```bash
python3 ./fireworks-tech-graph/scripts/generate-from-template.py architecture ./output/arch.svg '{"title":"My Diagram","nodes":[],"arrows":[]}'
```

### 3. validate-svg.sh - Validate SVG syntax

```bash
./fireworks-tech-graph/scripts/validate-svg.sh <svg-file>
```

### 4. Style Reference Files

The `references/` directory contains seven visual style references:

- style-1-flat-icon.md - Flat Icon (default)
- style-2-dark-terminal.md - Dark Terminal
- style-3-blueprint.md - Blueprint
- style-4-notion-clean.md - Notion Clean
- style-5-glassmorphism.md - Glassmorphism
- style-6-haijun-official.md - Haijun Official
- style-7-openai.md - OpenAI Official
- icons.md - Icon reference
- style-diagram-matrix.md - Style–diagram type adaptation matrix
- svg-layout-best-practices.md - SVG layout best practices

## Workflow (Always Follow This Order)

1. **Classify** the diagram type
2. **Extract the structure** — identify layers, nodes, edges, flows, and semantic groups from the user's description
3. **Plan the layout** — apply the layout rules for the diagram type
4. **Load the style reference** — load style-1-flat-icon by default
5. **Map nodes to shapes** — use the shape vocabulary
6. **Check icon requirements**
7. **Write the SVG** — use the Python List method (mandatory)
8. **Validate**: run `rsvg-convert file.svg -o /dev/null 2>&1`
9. **Export PNG**: `rsvg-convert -w 1920 file.svg -o file.png`
10. **Report** the generated file path
11. **(Optional) Visual self-check**

## Diagram Types and Layout Rules

### Architecture Diagram

Nodes = services/components. Group into horizontal layers (top-to-bottom or left-to-right).

- Typical layers: client → gateway/load balancer → service → data/storage
- Group related services in the same layer with a dashed `<rect>` container
- Arrow direction follows the data/request flow
- ViewBox: `0 0 960 600` standard, `0 0 960 800` for tall stacks

### Data Flow Diagram

Emphasize where data moves. Focus on data transformations.

- Label each arrow with the data type (e.g. embeddings, query, context)
- Use wider arrows (stroke-width: 2.5) for primary data paths
- Dashed arrows for control/trigger flows
- Color arrows by data category

### Flowchart / Process Flow

Sequential decision/process steps.

- Prefer top-to-bottom; left-to-right for wide flows
- Diamond for decisions, rounded rectangle for processes, parallelogram for I/O
- Keep node labels short (≤3 words)
- Align nodes on a grid: x positions to 120px intervals, y to 80px

### Agent Architecture Diagram

Show how an AI agent reasons, uses tools, and manages memory.

Key conceptual layers:

- **Input layer**: user, query, trigger
- **Agent core**: LLM, reasoning loop, planner
- **Memory layer**: short-term (context window), long-term (vector/graph database), episodic
- **Tool layer**: tool calls, API, search, code execution
- **Output layer**: response, action, side effect

Show iterative reasoning with circular arrows (loop arcs). Visually separate different types of memory.

### Memory Architecture Diagram (Mem0, MemGPT style)

An Agent diagram focused on memory operations.

- Show the memory write path and read path separately (different arrow colors)
- Memory hierarchy: working memory → short-term → long-term → external storage
- Label memory operations: store(), retrieve(), forget(), consolidate()
- Show storage tiers with stacked rectangles or layered cylinders

### Sequence Diagram

Time-ordered message exchanges between participants.

- Participants are vertical lifelines (top label + vertical dashed line)
- Messages are horizontal arrows between lifelines, ordered top-to-bottom by time
- Activation boxes (thin filled rectangles on the lifeline) show active processing
- Group with `<rect>` loop/alt frames, with labels in the top-left corner
- ViewBox height = 80 + (number of messages × 50)

### Comparison / Feature Matrix

Side-by-side comparison of methods, systems, or components.

- Column headers = systems, row headers = attributes
- Row height: 40px; column width: minimum 120px; header row height: 50px
- Supported cells: colored background (e.g. #dcfce7) + ✓ check mark
- Alternate row fills (#f9fafb / #ffffff) to improve readability
- Maximum readable columns: 5; split into two diagrams if exceeded

### Timeline / Gantt Chart

A horizontal time axis showing durations, phases, and milestones.

- X-axis = time (week/month/quarter); Y-axis = project/task/phase
- Bars: rounded rectangles, colored by category, labeled inside or beside
- Milestone markers: diamonds or filled circles at specific x positions, with labels above
- ViewBox: 0 0 960 400 typical; wider for more periods: 0 0 1200 400

### Mind Map / Concept Map

Radial layout from a central concept.

- Central node at cx=480, cy=280
- First-level branches: evenly distributed around the center (360/N degrees)
- Second-level branches: branch off from first-level branches at 30-45° offsets
- Show branches with cubic Bézier `<path>`, not straight lines

### Class Diagram (UML)

A static structure showing classes, attributes, methods, and relationships.

- **Class boxes**: 3-compartment rectangles (name/attributes/methods), minimum width 160px
- **Relationships**: inheritance (solid line + hollow triangle), realization (dashed line + hollow triangle), association (solid line + open arrow), aggregation (hollow diamond), composition (filled diamond), dependency (dashed line + open arrow)
- ViewBox: 0 0 960 600 standard; 0 0 960 800 for deep structures

### Use Case Diagram (UML)

System functionality from the user's perspective.

- **Actors**: stick figures, placed outside the system boundary
- **Use cases**: ellipses with centered labels, minimum 140×60px
- **System boundary**: a large rectangle with a dashed border
- **Relationships**: include, extend, generalization
- ViewBox: 0 0 960 600 standard

### State Machine Diagram (UML)

The lifecycle states and transitions of an entity.

- **States**: rounded rectangles with state names, minimum 120×50px
- **Initial state**: filled black circle (r=8)
- **Final state**: a filled circle inside a hollow circle
- **Transitions**: arrows, with optional label event [guard] / action
- ViewBox: 0 0 960 600 standard

### ER Diagram (Entity-Relationship)

Database schemas and data relationships.

- **Entities**: rectangles, with the entity name in bold in the title area and attributes below
- **Relationships**: diamonds on the connecting lines
- **Cardinality labels**: 1, N, 0..1, 0.._, 1.._
- ViewBox: 0 0 960 600 standard; wider for more entities: 0 0 1200 600

### Network Topology

Physical or logical network infrastructure.

- **Devices**: routers, switches, servers, firewalls, load balancers, cloud
- **Connections**: wired (solid line), wireless (dashed line + WiFi), VPN (dashed line + lock)
- **Subnets/zones**: dashed rectangular containers (DMZ, internal, external)
- Layout: layered top-to-bottom (internet → edge → core → access → endpoint)
- ViewBox: 0 0 960 600 standard

## Shape Vocabulary

Map semantic concepts to consistent shapes:

| Concept            | Shape                              | Notes                          |
| ------------------ | ---------------------------------- | ------------------------------ |
| User/Human         | Circle + body path                 | Stick figure or avatar         |
| LLM/Model          | Rounded rectangle + brain/spark icon | Use accent color             |
| Agent/Orchestrator | Hexagon or double-bordered rounded rectangle | Indicates an active controller |
| Short-term memory  | Dashed-border rounded rectangle    | Brief = dashed                 |
| Long-term memory   | Cylinder (database shape)          | Persistent = solid cylinder    |
| Vector store       | Cylinder with grid lines           | Add 3 horizontal lines         |
| Graph database     | Cluster of circles (3 overlapping circles) |                        |
| Tool/Function      | Gear-shaped rectangle or wrench icon |                              |
| API/Gateway        | Single-border hexagon              |                                |
| Queue/Stream       | Horizontal tube (pipe shape)       |                                |
| File/Document      | Rectangle with folded corner       |                                |
| Browser/UI         | Rectangle with a 3-dot title bar   |                                |
| Decision           | Diamond                            | Flowcharts only                |
| Process/Step       | Rounded rectangle                  | Standard box                   |
| External service   | Rectangle with a cloud icon or dashed border |                      |
| Data/Artifact      | Parallelogram                      | I/O in flowcharts              |

## Arrow Semantics

Always give arrows meaning, not just color:

| Flow Type          | Color        | Stroke      | Dashed | Meaning                     |
| ------------------ | ------------ | ----------- | ------ | --------------------------- |
| Primary data flow  | Blue #2563eb | 2px solid   | No     | Primary request/response path |
| Control/trigger    | Orange #ea580c | 1.5px solid | No   | One system triggers another |
| Memory read        | Green #059669 | 1.5px solid | No    | Retrieve from storage       |
| Memory write       | Green #059669 | 1.5px       | 5,3    | Write/store operation       |
| Async/event        | Gray #6b7280 | 1.5px       | 4,2    | Non-blocking, event-driven  |
| Embedding/transform | Purple #7c3aed | 1px solid | No    | Data transformation         |
| Feedback/loop      | Purple #7c3aed | 1.5px curve | No   | Iterative reasoning loop    |

When using more than 2 arrow types, always include a legend.

## Layout Rules and Validation

**Spacing**:

- Nodes in the same layer: 80px horizontal, 120px vertical between layers
- Canvas margin: minimum 40px, 60px between node edges
- Align to an 8px grid: 120px horizontal intervals, 120px vertical intervals

**Arrow labels** (critical):

- A background rect is required: `<rect fill="canvas_bg" opacity="0.95"/>`, with 4px horizontal and 2px vertical padding
- Place at the arrow midpoint, ≤3 words; offset by 15-20px when multiple arrows converge
- Keep a 10px safety distance from nodes

**Arrow routing**:

- Prefer orthogonal (L-shaped) paths to minimize crossings
- Anchor arrows at component edges, not geometric centers
- Route around dense node clusters; use different y offsets for parallel arrows
- Use hop arcs (5px radius) for unavoidable crossings

**Line overlap prevention** (critical - the most common bug):

- When two arrows must cross, always use a hop arc to prevent visual overlap
- Crossing horizontal arrows: add a small semicircle arc (5px radius) to hop over the other line
- Multiple crossings: stagger the arc radii (5px, 7px, 9px)

**Validation checklist** (run before completion):

1. **Arrow-component collision**: arrows must not pass through the interior of components
2. **Text overflow**: all text should be within an 8px padding
3. **Arrow-text alignment**: arrow endpoints must connect to shape edges
4. **Container rule**: prefer entering/exiting through the open gaps between components

## SVG Technical Rules

- ViewBox: `0 0 960 600` default; `0 0 960 800` tall; `0 0 1200 600` wide
- Fonts: embed via `<style>font-family: ...</style>` — do not use external `@import`
- `<defs>`: arrow markers, gradients, filters, clip paths
- Text: minimum 12px, recommended 13-14px labels, 11px sublabels, 16-18px titles
- All arrows: `<marker>` with `markerEnd`, size `markerWidth="10" markerHeight="7"`
- Drop shadow: `<feDropShadow>` in a `<filter>`, use sparingly (key nodes only)
- Curved paths: use `M x1,y1 C cx1,cy1 cx2,cy2 x2,y2` cubic Bézier
- Clipping content: use `<clipPath>` when text may overflow the node box

## SVG Generation and Error Prevention

**Mandatory: Python List method** (always use):

```python
python3 << 'EOF'
lines = []
lines.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 700">')
lines.append('  <defs>')
# ... one line at a time
lines.append('</svg>')
with open('/path/to/output.svg', 'w') as f:
    f.write('\n'.join(lines))
print("SVG generated successfully")
EOF
```

**Pre-invocation checklist** (critical - use every time):

1. ✅ Can I write the complete command/content immediately?
2. ✅ Do I have all the required parameters ready?
3. ✅ Have I checked the prepared content for syntax errors?

**Error recovery protocol**:

- First error: analyze the root cause and apply a targeted fix
- Second error: switch the approach entirely (Python list → chunked generation)
- Third error: stop and report to the user — do not loop indefinitely

**Validation** (run after generation):

```bash
rsvg-convert file.svg -o /tmp/test.png 2>&1 && echo "✓ Valid" && rm /tmp/test.png
```

## Styles

| #   | Name                     | Background        | Best For                          |
| --- | ------------------------ | ----------------- | --------------------------------- |
| 1   | **Flat Icon** (default)  | White             | Blogs, documentation, presentations |
| 2   | **Dark Terminal**        | #0f0f1a           | GitHub, dev articles              |
| 3   | **Blueprint**            | #0a1628           | Architecture docs                 |
| 4   | **Notion Clean**         | White, minimal    | Notion                            |
| 5   | **Glassmorphism**        | Dark gradient     | Product sites, keynote talks      |
| 6   | **Haijun Official**      | Warm cream #f8f6f3 | Juglow-style diagrams         |
| 7   | **OpenAI Official**      | Pure white #ffffff | OpenAI-style diagrams            |

## Common Patterns

These patterns recur often — internalize them:

- **RAG pipeline**: Query → Embed → VectorSearch → Retrieve → Augment → LLM → Response
- **Agentic RAG**: add an Agent loop and tool use between Query and LLM
- **Agentic Search**: Query → Planner → [Search Tool / Calculator / Code] → Synthesizer → Response
- **Mem0 / memory layer**: Input → Memory Manager → [Write: VectorDB + GraphDB] / [Read: Retrieve+Rank] → Context
- **Agent memory types**: Sensory (raw input) → Working (context window) → Episodic (past interactions) → Semantic (facts) → Procedural (tracks)
- **Multi-Agent**: Orchestrator → [SubAgent A / SubAgent B / SubAgent C] → Aggregator → Output
- **Tool call flow**: LLM → Tool Selector → Tool Execution → Result Parser → LLM (loop)
