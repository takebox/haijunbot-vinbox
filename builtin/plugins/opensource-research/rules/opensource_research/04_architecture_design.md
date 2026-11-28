# Architecture and Design Research

## Research Goals

Deeply understand an open-source project's system architecture, core component design, component interaction methods, and design patterns, and grasp the project's architectural thinking and design philosophy.

## Research Steps You Must Perform

### Step 1: Draw the Overall System Architecture

**Content that must be researched and analyzed:**

- The high-level architecture diagram of the system
- Architecture patterns (layered, microservices, event-driven, etc.)
- Architecture layers and module division
- The design principles of the architecture

**Keywords to search:**

- "[project name] architecture diagram"
- "[project name] system architecture"
- "[project name] architecture overview"
- "[project name] high level design"

**Information sources:**

- The Architecture section of the official documentation
- Architecture design documents
- The architecture diagram in the README
- Architecture analysis on technical blogs

### Step 2: Identify the Core Components

**Core components that must be analyzed:**

- What main components the system is composed of
- The core responsibility of each component
- The boundaries and interfaces of the components
- The dependencies between components

**Key analysis questions:**

- Why this component is needed
- What problem this component solves
- What the component's inputs and outputs are
- The testability and maintainability of the component

**Information sources:**

- The code directory structure
- Documentation of the core modules
- Component README files
- Design documents and RFCs

### Step 3: Analyze Component Interaction Methods

**Interaction mechanisms that must be researched:**

- How components communicate with each other
- What communication protocols and patterns are used
- Data flow and control flow
- The startup and shutdown process of components

**Keywords to search:**

- "[project name] component communication"
- "[project name] data flow"
- "[project name] message passing"
- "[project name] event handling"

**Information sources:**

- The interaction diagram in the architecture documents
- Sequence diagrams and flowcharts
- Call relationships in the source code
- read_webpage to read technical documentation

### Step 4: Research the Application of Design Patterns

**Design patterns that must be identified:**

- What design patterns are used
- Why these patterns are used
- How the patterns work
- Variants and customizations of the patterns

**Common design patterns:**

- Creational patterns: factory, singleton, builder
- Structural patterns: adapter, decorator, proxy
- Behavioral patterns: observer, strategy, chain of responsibility

**Information sources:**

- Pattern applications in the source code
- Pattern explanations in the design documents
- Pattern analysis on technical blogs
- Design explanations in code comments

### Step 5: Analyze Data Structures and Data Flow

**Content that must be researched:**

- The main data structures used by the system
- The flow paths of data through the system
- How data is stored and retrieved
- Data consistency and persistence

**Keywords to search:**

- "[project name] data model"
- "[project name] data structures"
- "[project name] storage"
- "[project name] database schema"

**Information sources:**

- Data model documents
- Database schema definitions
- Data structures in the source code
- Data definitions in the API documentation

### Step 6: Research Interface and Abstraction Design

**Interface designs that must be analyzed:**

- Design principles of public interfaces
- The abstraction levels of interfaces
- Backward compatibility considerations
- The design of extension points

**Key research content:**

- Interface stability
- Interface usability
- Interface flexibility
- Interface documentation completeness

**Information sources:**

- API documentation
- Interface design documents
- RFC discussions
- The implementation of client libraries

### Step 7: Analyze Error Handling and Fault Tolerance Mechanisms

**Content that must be researched:**

- The system's error handling strategy
- Fault tolerance and recovery mechanisms
- Logging and monitoring
- Degradation and rate limiting

**Keywords to search:**

- "[project name] error handling"
- "[project name] fault tolerance"
- "[project name] resilience"
- "[project name] retry policy"

**Information sources:**

- Operations and deployment documentation
- Error handling code
- Monitoring documentation
- Troubleshooting guides

## Research Output Requirements

### Document Structure

**Document that must be produced:** `04_architecture_design.md`

**The document must contain the following sections:**

1. Overall system architecture
2. Core component analysis
3. Component interaction mechanisms
4. Design pattern application
5. Data structures and data flow
6. Interface and abstraction design
7. Error handling and fault tolerance
8. Reference list

### Content Quality Requirements

- **Must**: provide architecture diagrams and component diagrams
- **Must**: deeply analyze the responsibility and interaction of each component
- **Must**: identify and explain the use of design patterns
- **Must**: analyze the complete path of the data flow
- **Must**: all analysis has source citations
- **Forbidden**: only listing component names without analyzing responsibilities
- **Forbidden**: lacking analysis of interaction mechanisms

## Research Depth Check

After completing this stage of research, you must confirm:

- [ ] You can draw the system's architecture diagram
- [ ] You understand the responsibility of each core component
- [ ] You grasp the interaction methods between components
- [ ] You identify the design patterns used
- [ ] You understand data flow and control flow
- [ ] All analysis has sufficient basis

## Architecture Analysis Framework

### Component Analysis Framework

**Must answer:**

- **What**: what the component does
- **Why**: why this component is needed
- **How**: how the component works
- **Input/Output**: what the inputs and outputs are
- **Dependencies**: which components it depends on

### Interaction Analysis Framework

**Must include:**

- Communication protocols and methods
- Call sequence and flow
- Data transfer format
- Error handling mechanisms

### Design Pattern Analysis Framework

**Must include:**

- The name and type of the pattern
- The applicable scenarios of the pattern
- The problem the pattern solves
- Implementation variants and customizations

## Common Mistakes

**❌ Wrong approaches:**

- Only listing components without analyzing responsibilities
- Lacking analysis of component interaction
- Not identifying the application of design patterns
- Ignoring data flow and error handling

**✅ Correct approaches:**

- Deeply analyze the responsibility and boundaries of each component
- Research the communication and interaction between components
- Identify design patterns and analyze their role
- Pay attention to data flow and fault tolerance mechanisms

## Practical Tips

**In-depth research strategy:**

1. Start from the entry code (the main function) and trace the execution flow
2. Use code analysis tools to generate call graphs
3. Look at unit tests to understand the expected behavior of components
4. Analyze log output to understand runtime behavior
5. Look at configuration files to understand the components' configuration items
6. Research failure and error handling logic
