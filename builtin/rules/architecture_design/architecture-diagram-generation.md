---
name: architecture-diagram-generation
description: Triggered when a system architecture diagram or component relationship diagram needs to be generated. Triggered whenever the user mentions "architecture diagram", "component diagram", "architecture design diagram", "system architecture", "dependency graph", or "deployment diagram". Not triggered: describing the architecture in text only without generating a diagram; UI/interface design diagrams; flowcharts (use the fireworks_tech_graph rule).
---

# Architecture Diagram Generation Rule

## Workflow You Must Follow

### Complete Architecture Diagram Generation Process (strictly follow)

1. **Requirements clarification phase**:
   - You must clarify which architecture view the user needs to generate
   - Forbidden to start code analysis when the requirements are unclear

2. **Code reading phase**:
   - You must use the `read_code` tool to read all the source code provided by the user completely and carefully
   - Forbidden to read only part of the code or guess out of thin air

3. **Component identification and relationship analysis phase**:
   - You must identify the core classes, modules, interfaces, and functions
   - You must analyze the dependencies, inheritance, calls, and data flow relationships among them
   - You must perform appropriate abstraction and grouping of the components according to the view type

4. **View drawing phase (DOT language)**:
   - **Logical view**: must focus on functionality and system structure, mainly presenting layering relationships, avoiding overly dense connections between components
   - **Implementation view**: must focus on the physical organization of the code, showing files, modules, packages, and their dependency relationships
   - **Process view**: must focus on the system's runtime behavior, showing the main processes, threads, tasks, and their communication
   - **Deployment view**: must focus on the system's physical deployment, showing hardware nodes, network connections, and the software components deployed on the nodes
   - **Use case view**: must focus on the interaction between users and the system, showing actors and use cases

5. **Diagram generation and rendering phase**:
   - You must output the generated Graphviz DOT code to a file with a `.dot` suffix
   - You must use the `execute_script` tool to invoke the `dot` command to render the `.dot` file into a `.png` image
   - You must report the rendered image path to the user

## Principles You Must Follow

### Code Completeness Principle

- **Forbidden**: reading only part of the code or guessing the system architecture out of thin air
- **Must**: read and analyze all the source code provided by the user completely and carefully
- **Must**: accurately identify the core classes, modules, interfaces, and functions and their interrelationships

### View Accuracy Principle

- **Must**: the diagram must accurately reflect the actual structure of the code
- **Must**: in diagrams of the same series, the representation of the same component should be consistent
- **Forbidden**: reflecting specific implementation names or paths in the diagram, you must use abstract responsibility or role naming

### Diagram Clarity and Visual Aesthetics Principle

- **Must**: the diagram must be simple and clear, easy to understand, and have a professional appearance
- **Must**: avoid overly dense connections between components, keep the diagram clear, and leave sufficient whitespace
- **Must**: use a coordinated and unified color scheme, using different color families for different levels to ensure a clear visual hierarchy
- **Must**: keep node styles unified (rounded rectangles, fill color, border color) to improve overall aesthetics
- **Must**: use a moderate font size, keep label text clear and readable, and avoid text overlap or being too small
- **Must**: keep connection styles unified, use appropriate arrow styles and line weights, and highlight important relationships in bold
- **Must**: use a soft background color and a clear border for subgraphs (clusters) to enhance the grouping visual effect
- **Must**: keep the overall layout balanced, with nodes evenly distributed, avoiding overly crowded or sparse local areas

### Professionalism Principle

- **Must**: strictly follow the best practices of architecture design and Graphviz
- **Must**: all output DOT code must be complete and directly renderable
- **Must**: be contained in `digraph G { ... }`, following unified style conventions

## Specific Requirements and Conventions

- All output DOT code must be complete and directly renderable.
- It should be contained in `digraph G { ... }`.
- **Layout direction**: for diagrams with an obvious hierarchical structure (such as organizational structure and call chains),
  prefer using `rankdir="TB"` to achieve a top-to-bottom layout. For flow or sequence
  relationships, `rankdir="LR"` (left to right) may be more appropriate.
- **Layout alignment**: to obtain a neat and aligned layout, actively use
  `subgraph cluster_...` to group nodes, and use
  `{ rank=same; ... }` statements to place nodes that need horizontal alignment on the same level.
- **Layout spacing**: to avoid node or text overlap, you can set the `nodesep` and `ranksep` properties in `graph [...]`
  to increase the spacing between nodes and levels,
  such as `nodesep=0.6, ranksep=1.0`. At the same time, you can set `overlap=false` to disable
  overlap.
- Use graph, node, and edge properties to beautify the diagram. The following professional and aesthetically pleasing style conventions are recommended:

```dot
digraph G {
    // --- Global Settings ---
    // Use professional global style settings to ensure the diagram is aesthetically pleasing and consistent
    graph [rankdir="TB",
           splines=ortho,                    // Use orthogonal connections, more professional
           fontname="Sans-serif",
           fontsize=11,                      // Appropriate font size
           label="Diagram title: [enter the view name here]",
           labelloc="t",
           fontcolor="#333333",              // Title text color
           newrank=true,
           nodesep=0.8,                      // Node spacing, avoid crowding
           ranksep=1.2,                      // Level spacing, clear hierarchy
           overlap=false,                    // Disable overlap
           bgcolor="#FFFFFF",                // White background
           pad=0.5];                         // Margin, sufficient whitespace

    // --- Default Node Style ---
    // Default node style: rounded rectangle, soft fill, clear border
    node [shape=box,
          style="rounded,filled",
          fillcolor="#F5F5F5",               // Light gray fill, soft and comfortable
          color="#666666",                    // Dark gray border, clear but not obtrusive
          fontname="Sans-serif",
          fontsize=10,
          fontcolor="#333333",                // Text color, ensure readability
          penwidth=1.5];                      // Moderate border weight

    // --- Default Edge Style ---
    // Default connection style: clear and concise
    edge [fontname="Sans-serif",
          fontsize=9,
          fontcolor="#555555",                // Label text color
          color="#888888",                    // Connection color, does not steal attention
          penwidth=1.2,                       // Connection weight
          arrowsize=0.8];                     // Moderate arrow size

    // --- Interface/Entry Point Nodes ---
    // Interface layer/entry nodes: use eye-catching warm tones
    node [group=interface,
          shape=cds,                         // Rounded rectangle, representing an interface
          fillcolor="#FFE6CC",               // Warm orange fill
          color="#D79B00",                    // Dark orange border
          penwidth=2.0];                      // Slightly thicker border, highlighting importance
    api_gateway [label="API Gateway"];

    // --- Service Layer Subgraph ---
    // Service layer subgraph: use a professional blue family with clear grouping
    subgraph cluster_services {
        label = "Business Service Layer";
        style = "filled,rounded";            // Fill + rounded corners, more attractive
        fillcolor="#F0F4F8",                 // Light blue-gray background, soft and professional
        color="#6C8EBF",                      // Blue border, echoing the nodes
        fontname="Sans-serif";
        fontsize=11;
        fontcolor="#4A5568";                  // Dark gray text, clearly readable
        penwidth=2.0;                         // Slightly thicker border, highlighting the group

        node [group=service,
              fillcolor="#DAE8FC",            // Light blue fill
              color="#6C8EBF",                // Blue border
              penwidth=1.8];                  // Border weight
        service_A [label="Service A"];
        service_B [label="Service B"];
    }

    // --- Data Layer ---
    // Data layer: use a green family, representing storage and persistence
    node [group=database,
          shape=cylinder,                      // Cylinder shape, representing a database
          fillcolor="#D5E8D4",                // Light green fill
          color="#82B366",                    // Dark green border
          penwidth=2.0];                      // Slightly thicker border, highlighting importance
    database_A [label="Database"];

    // --- Relationships ---
    // Relationship connections: use clear labels and styles
    api_gateway -> service_A [label="route",
                               color="#6C8EBF",    // Use the service layer color
                               penwidth=1.5];
    api_gateway -> service_B [label="route",
                               color="#6C8EBF",
                               penwidth=1.5];
    service_A -> database_A [label="read/write",
                             color="#82B366",     // Use the data layer color
                             penwidth=1.5];
    service_B -> database_A [label="read",
                             color="#82B366",
                             penwidth=1.5,
                             style="dashed"];      // Use a dashed line for read-only relationships

    // --- Horizontal Alignment ---
    // Horizontal alignment: ensure nodes at the same level are on the same horizontal line
    { rank=same; service_A; service_B; }
}
```

**Style beautification points**:

- **Color scheme**: use a coordinated color family, warm colors for the interface layer (orange/yellow), cool colors for the service layer (blue), green for the data layer, and purple for external systems
- **Font conventions**: uniformly use the Sans-serif font, 11pt for titles, 10pt for node labels, 9pt for edge labels
- **Border styles**: use slightly thicker borders for important nodes (penwidth=2.0), and 1.5-1.8 for ordinary nodes
- **Fill effects**: use soft light-color fills, avoid being too vivid, and ensure a professional feel
- **Connection styles**: use solid bold lines for important relationships and dashed lines for secondary relationships, with corresponding colors for different levels
- **Subgraph beautification**: use a rounded filled background (style="filled,rounded"), a soft background color, and a clear border
- **Whitespace design**: control spacing through nodesep and ranksep, and control margins through pad, to ensure the diagram is not crowded

- Use appropriate shapes and styles according to different views.
- Use rectangles (shape=box) for module nodes as much as possible; except for special components such as databases, external systems, and message queues, avoid using other shapes to represent "modules".
- Abstract naming convention: do not reflect specific implementation names or paths in the diagram (such as utils.output, xxx.py, specific function names); use abstract responsibility or role naming (such as output module, storage module, network layer, authentication service).
- Comments are clear, explaining the key elements and relationships in the diagram.
- **Accuracy**: the diagram must accurately reflect the actual structure of the code.
- **Clarity**: the diagram must be simple and clear, easy to understand.
- **Consistency**: in diagrams of the same series, the representation of the same component should be consistent.
- **Professionalism**: strictly follow the best practices of architecture design and Graphviz.

## Practical Guidance

### Code Analysis Best Practices

- **Start from the entry point**: first identify the system's main entry points (such as API gateway, main function, core controller)
- **Layered analysis**: analyze according to the hierarchy of presentation layer, business logic layer, and data access layer
- **Dependency tracing**: use tools or manually trace the dependencies between code, and draw a dependency graph
- **Module identification**: identify module units with high cohesion and low coupling

### Component Abstraction Techniques

- **Use abstract naming**: abstract concrete class names and function names into responsibility descriptions (e.g., abstract `UserService` into "user management service")
- **Reasonable grouping**: group related functional components into the same subgraph, using the `subgraph cluster_xxx` syntax
- **Layer division**: clearly distinguish different layers such as the interface layer, service layer, and data layer
- **External system identification**: clearly identify external components such as external systems, databases, and message queues

### View Selection Guidance

- **Logical view**: suitable for showing the division of system functional modules and their interaction relationships
- **Implementation view**: suitable for showing the code organization structure and package dependency relationships
- **Process view**: suitable for showing the concurrency and communication between processes and threads during system runtime
- **Deployment view**: suitable for showing the deployment topology of the system in the physical environment
- **Use case view**: suitable for showing the interaction scenarios between users and the system

### Graphviz Usage Tips and Beautification Guide

#### Layout and Alignment Techniques

- **Layout selection**:
  - Use `rankdir="TB"` (top to bottom) for hierarchical structures, suitable for showing layered architecture
  - Use `rankdir="LR"` (left to right) for flow relationships, suitable for showing data flow or call chains
  - For complex relationships, you can try `rankdir="BT"` or `rankdir="RL"`, choosing the best direction according to the content

- **Node alignment**:
  - Use `{ rank=same; node1; node2; }` to achieve horizontal alignment of nodes at the same level
  - Important nodes can use `rank=source` or `rank=sink` to place them at the top or bottom
  - Use the `group` property to group related nodes, automatically aligning them

- **Spacing adjustment**:
  - `nodesep=0.8-1.2`: control the spacing between nodes at the same level, avoid crowding
  - `ranksep=1.0-1.5`: control the spacing between different levels, clear hierarchy
  - `pad=0.5-1.0`: control the diagram margins, sufficient whitespace
  - `overlap=false`: disable node overlap, ensure clarity

#### Color and Visual Beautification

- **Color scheme** (recommended professional colors):
  - **Interface layer/entry**: warm tones `#FFE6CC` (light orange) fill, `#D79B00` (dark orange) border
  - **Service layer/business logic**: cool tones `#DAE8FC` (light blue) fill, `#6C8EBF` (dark blue) border
  - **Data layer/storage**: green family `#D5E8D4` (light green) fill, `#82B366` (dark green) border
  - **External systems**: purple family `#E1D5E7` (light purple) fill, `#9673A6` (dark purple) border
  - **Tools/tool layer**: red family `#F8CECC` (light red) fill, `#B85450` (dark red) border
  - **Events/messages**: yellow family `#FFF2CC` (light yellow) fill, `#B57800` (dark yellow) border

- **Color usage principles**:
  - Use the same color family for the same level to maintain visual consistency
  - Use light colors for fills (in the #F0-F8 range) and dark colors for borders (in the #4-9 range), forming a hierarchy
  - Avoid overly vivid colors (such as pure red, pure blue), and use soft intermediate tones
  - Use white as the unified background color (`bgcolor="#FFFFFF"`) to ensure a professional feel

#### Node Style Beautification

- **Shape conventions**:
  - Interface/API: `shape=cds` (rounded rectangle), highlighting the entry characteristic
  - Service/module: `shape=box, style="rounded,filled"` (rounded filled rectangle), the standard style
  - Database: `shape=cylinder` (cylinder shape), the traditional representation
  - External systems: `shape=box, style="rounded,filled,dashed"` (dashed border), distinguishing external
  - Queue/message: `shape=box, style="rounded,filled"`, which can be distinguished with special colors

- **Node beautification techniques**:
  - Use `penwidth=1.5-2.0` to control the border weight, slightly thicker for important nodes
  - Use `fillcolor` to set a soft fill color, avoid pure white or pure black
  - Use `fontsize=10-11` to ensure text is clear and readable
  - Use `fontcolor="#333333"` to set dark text, ensuring contrast

#### Connection Style Beautification

- **Connection styles**:
  - Important relationships: `penwidth=1.5-2.0`, solid lines, with the corresponding level color
  - Secondary relationships: `penwidth=1.0-1.2`, dashed lines (`style="dashed"`)
  - Data flow: you can use the arrow styles `arrowhead=normal` or `arrowhead=vee`
  - Bidirectional relationships: use `dir=both`, with arrows on both ends

- **Connection labels**:
  - Use concise label text, avoid being too long
  - `fontsize=9`, ensuring it does not steal attention from the nodes
  - `fontcolor="#555555"`, use a medium gray, clear but not obtrusive

#### Subgraph (Cluster) Beautification

- **Subgraph styles**:
  - Use `style="filled,rounded"`, fill + rounded corners, more attractive
  - Use the light-color version of the corresponding level for the background color (e.g., `#F0F4F8` for the service layer)
  - Use the dark color of the corresponding level for the border (e.g., `#6C8EBF` for the service layer)
  - `penwidth=2.0`, a slightly thicker border, highlighting the group
  - Use `fontsize=11` for the label, clearly identifying the group

#### Font and Text Beautification

- **Font selection**:
  - Uniformly use `fontname="Sans-serif"`, modern and concise
  - Title: `fontsize=11-12`, displayed in bold
  - Node labels: `fontsize=10`, clearly readable
  - Edge labels: `fontsize=9`, does not steal attention

- **Text colors**:
  - Title: `fontcolor="#333333"` (dark gray)
  - Node labels: `fontcolor="#333333"` (dark gray)
  - Edge labels: `fontcolor="#555555"` (medium gray)

#### Overall Visual Effect

- **Enhancing professionalism**:
  - Use unified style conventions to ensure overall coordination
  - Avoid excessive decoration, keep it simple and professional
  - Use whitespace reasonably, avoid crowding
  - Ensure sufficient color contrast, with clear and readable text

- **Creating a sense of hierarchy**:
  - Distinguish levels through the depth of colors
  - Highlight importance through the weight of borders
  - Reflect the closeness of relationships through the size of spacing
  - Clarify module boundaries through subgraph grouping

## Rendering Steps

1. First, use the REWRITE operation or PATCH operation to write the generated DOT code into a `.dot` file.
2. Next, use `execute_script` to invoke the `dot` command for rendering.
3. Finally, report the generated `.png` file path to the user.

## Execution Checklist

Before starting architecture diagram generation, please be sure to confirm:

- [ ] The type of architecture view the user needs to generate has been clarified (logical/implementation/process/deployment/use case view)
- [ ] All relevant source code file paths have been obtained
- [ ] The code analysis tools and environment are ready

When performing code analysis, please be sure to confirm:

- [ ] All relevant source code has been read completely, with no key files missed
- [ ] The system's core components and modules have been accurately identified
- [ ] The dependencies, inheritance, calls, and data flow relationships between components have been analyzed
- [ ] Appropriate abstraction and grouping of components have been performed according to the view type

When drawing the architecture diagram, please be sure to confirm:

- [ ] An appropriate view type has been selected to show the system architecture
- [ ] The correct Graphviz syntax and DOT language format have been used
- [ ] Unified style conventions and color combinations have been followed, and a professional color scheme has been used
- [ ] The diagram layout is clear and easy to understand, with sufficient whitespace and evenly distributed nodes
- [ ] Component naming is abstract, without exposing specific implementation details
- [ ] Node styles are unified (rounded corners, fill, border), with a professional and aesthetically pleasing visual effect
- [ ] Connection styles are reasonable (weight, color, solid/dashed), with important relationships highlighted
- [ ] Subgraph grouping is clear, with coordinated background colors and borders, and clear, readable labels
- [ ] The font size is moderate, and the text color contrast is sufficient, ensuring readability
- [ ] The overall color scheme is coordinated, with a clear hierarchy and a professional appearance

When generating and rendering the diagram, please be sure to confirm:

- [ ] The DOT code is complete and syntactically correct
- [ ] It has been successfully rendered into a PNG image using the `dot` command
- [ ] The generated image file path is correct and accessible
- [ ] A clear image access path has been provided to the user

Before delivering the result, please be sure to confirm:

- [ ] The architecture diagram accurately reflects the actual structure of the code
- [ ] The diagram conforms to the best practices of architecture design
- [ ] All components and relationships are correctly represented
- [ ] The image quality is clear, suitable for demonstration and sharing
- [ ] The diagram has a professional and aesthetically pleasing appearance, with coordinated colors and unified styles
- [ ] The visual hierarchy is clear, with important components highlighted and the overall layout balanced
- [ ] The text is clear and readable, with sufficient color contrast, without overlap or crowding
- [ ] It conforms to the visual standards of enterprise-level architecture diagrams, suitable for formal documents and presentations
