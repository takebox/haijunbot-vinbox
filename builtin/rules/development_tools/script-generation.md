---
name: script-generation
description: Triggered when there is a need to generate script code or write automation scripts. Triggered whenever the user mentions "generate a script", "write a script", "automation script", "batch processing", "Shell script", "Python script", or "PowerShell script". Not triggered: only executing an existing script; only debugging script errors; non-script class code development.
---

# Script Generation Rule

This rule defines the standardized process and requirements for script generation, ensuring the generated scripts have high quality, maintainability, and executability.

## Principles You Must Follow

### 1. Requirements Understanding Principle

- **Must** fully understand the user's script requirements and usage scenarios
- **Must** clarify the script's functional boundaries and expected output
- **Forbidden** starting script generation when the requirements are unclear

### 2. Technology Selection Principle

- **Must** choose the most suitable scripting language according to the target environment
- **Must** consider performance, security, and maintainability requirements
- **Forbidden** using outdated or incompatible technical solutions

### 3. Code Quality Principle

- **Must** generate clear, readable, and maintainable script code
- **Must** follow the best practices and coding conventions of the chosen language
- **Forbidden** generating code containing security vulnerabilities or performance issues

### 4. Documentation Completeness Principle

- **Must** provide complete script usage instructions and parameter documentation
- **Must** explain the function and implementation logic of key code sections
- **Forbidden** providing scripts that lack documentation or have unclear explanations

## Workflow You Must Follow

### Stage 1: Requirements Analysis

- **Must** clarify the script's functional requirements and business goals
- **Must** confirm the target runtime environment and system requirements
- **Must** understand the performance and security requirements
- **Must** determine the input/output format and data flow
- **Must** confirm the script save path and file permissions

### Stage 2: Script Design

- **Must** choose the scripting language best suited to the target environment
- **Must** design a clear script structure and module division
- **Must** plan a comprehensive error handling mechanism
- **Must** consider the script's extensibility and long-term maintainability
- **Forbidden** designing an overly complex or hard-to-maintain script structure

### Stage 3: Script Generation and Saving

- **Must** generate complete, directly executable script code
- **Must** write the script to the file path specified by the user
- **Must** add the necessary comments and documentation
- **Must** include usage examples and invocation methods
- **Must** provide testing methods and verification steps
- **Forbidden** generating scripts containing syntax errors or logic flaws

### Stage 4: Optimization and Improvement

- **Must** optimize the script functionality promptly according to user feedback
- **Must** add parameterization support to increase script flexibility
- **Must** improve the script's robustness and fault tolerance
- **Must** optimize performance-critical parts and execution efficiency
- **Forbidden** ignoring user feedback or rejecting reasonable improvement suggestions

## Specific Requirements and Conventions

### Script Output Convention

- **Must** provide complete, directly runnable script code
- **Must** save the script to the file path specified by the user
- **Must** display the script in a code block for easy copying and use
- **Must** explain the function and implementation logic of key code sections
- **Must** provide detailed script usage instructions and parameter descriptions
- **Must** list possible error situations and their corresponding solutions

### Script Quality Requirements

- **Must** ensure the script syntax is correct with no execution errors
- **Must** add appropriate comments to explain complex logic
- **Must** handle common exception situations and boundary conditions
- **Must** provide clear command-line argument parsing (where applicable)
- **Forbidden** generating scripts containing hardcoded paths or sensitive information
- **Forbidden** ignoring error handling or exception handling

### Technical Conventions

- **Must** choose the appropriate scripting language (Python, Bash, PowerShell, etc.) according to the target environment
- **Must** follow the encoding conventions and best practices of the chosen language
- **Must** consider cross-platform compatibility (if needed)
- **Must** optimize script execution efficiency and resource usage
- **Forbidden** using deprecated or not recommended language features

## Practical Guidance

### Communication Best Practices

- **Must** maintain a professional, clear technical communication style
- **Must** provide detailed technical explanations for the script implementation approach
- **Must** remain attentive to the user's questions and needs and respond promptly
- **Must** proactively clarify and confirm when encountering ambiguous requirements
- **Forbidden** using vague or uncertain technical expressions

### Script Optimization Strategy

- **Recommended** record common script patterns and solutions to build a knowledge base
- **Recommended** summarize reusable code snippets and function libraries
- **Recommended** continuously update and optimize script best practices
- **Recommended** establish standardized script templates for different scenarios
- **Recommended** periodically review and improve script generation quality

### Common Scenario Handling

- **Complex requirements**: must decompose into multiple simple steps and handle them progressively
- **Performance requirements**: must perform performance analysis and optimize critical paths
- **Security-sensitive**: must follow secure programming conventions and avoid common vulnerabilities
- **Cross-platform requirements**: must consider compatibility and provide platform-specific solutions
- **Maintainability requirements**: must design a modular structure for subsequent maintenance

### Quality Improvement Methods

- **Code review**: periodically perform script quality checks and optimization
- **User feedback**: actively collect and apply the user's improvement suggestions
- **Technology updates**: promptly adopt new scripting technologies and best practices
- **Performance monitoring**: continuously monitor script execution efficiency and resource usage
- **Documentation maintenance**: keep documentation accurate and complete

## Execution Checklist

### Requirements Confirmation Stage

- [ ] **Requirements understanding**: the user's script requirements and usage scenarios have been fully understood
- [ ] **Environment confirmation**: the target runtime environment and system requirements have been clarified
- [ ] **Functional boundaries**: the script's functional scope and expected output have been determined
- [ ] **Performance requirements**: performance and security related requirements have been understood

### Design Stage

- [ ] **Language selection**: the most suitable scripting language has been chosen
- [ ] **Architecture design**: a clear script structure and module division have been designed
- [ ] **Error handling**: a comprehensive error handling mechanism has been planned
- [ ] **Maintainability**: the script's extensibility and maintainability have been considered

### Implementation Stage

- [ ] **Code completeness**: complete, executable script code has been generated
- [ ] **File saving**: the script has been saved to the specified file path
- [ ] **Comments documentation**: the necessary comments and documentation have been added
- [ ] **Usage examples**: usage examples and invocation methods have been included
- [ ] **Testing verification**: testing methods and verification steps have been provided

### Quality Check Stage

- [ ] **Syntax check**: the script syntax correctness has been verified
- [ ] **Functional testing**: the script's core functionality has been tested
- [ ] **Error handling**: exception situations and boundary condition handling have been verified
- [ ] **Documentation completeness**: the documentation accuracy and completeness have been checked
- [ ] **User feedback**: user feedback has been collected and processed

### Delivery Stage

- [ ] **Code delivery**: the script file delivery has been completed
- [ ] **Documentation delivery**: the usage documentation delivery has been completed
- [ ] **Training support**: the necessary usage guidance has been provided
- [ ] **Follow-up support**: a follow-up optimization and maintenance mechanism has been established
