---
name: haijunbot_help
description: Triggered when there is a need to look up HaijunBot system help or usage guides. Triggered whenever the user mentions "HaijunBot help", "usage guide", "how to use", "HaijunBot tutorial", or "help documentation". Not triggered: specific feature development; code writing; tool invocation operations.
---

# HaijunBot Help Rule

## Rule Introduction

This rule guides how HaijunBot answers user questions about the HaijunBot system by referring to the official documentation and source code. When the user asks questions about HaijunBot's features, usage, configuration, architecture, etc., you must refer to the official documentation under the `{{haijunbot_src_dir}}/docs/haijunbot_book` directory and the source code under the `{{haijunbot_src_dir}}/src/haijunbot` directory to provide accurate and complete answers.

**Important principle**: when the documentation and the code implementation are inconsistent, the code implementation prevails. The documentation may lag behind code updates, and the source code is the true behavior of the system.

## Principles You Must Follow

### 1. Code-First Principle (must follow)

**Core principle:**

- **Must**: when the user asks a question about HaijunBot, take the source code implementation as the standard
- **Must**: the documentation may lag behind code updates, and the source code is the true behavior of the system
- **Must**: when the documentation and the code are inconsistent, take the code implementation as the standard
- **Forbidden**: answering based only on the documentation without verifying the code implementation
- **Forbidden**: providing information inconsistent with the code implementation

**Reference requirements:**

- **Must**: prioritize referring to the source code under the `{{haijunbot_src_dir}}/src/haijunbot` directory
- **Must**: refer to the documentation under the `{{haijunbot_src_dir}}/docs/haijunbot_book` directory as a supplement
- **Must**: provide accurate and authoritative answers based on the code implementation
- **Must**: cite the specific implementations in the code and the relevant sections in the documentation

**Documentation and source code locations:**

- **Must**: the documentation is located in the `{{haijunbot_src_dir}}/docs/haijunbot_book/` directory
- **Must**: the source code is located in the `{{haijunbot_src_dir}}/src/haijunbot/` directory
- **Must**: the documentation includes but is not limited to:
  - `1.Project_Introduction.md` - project overview and background
  - `2.Quick_Start.md` - installation and quick start
  - `3.Core_Concepts_and_Architecture.md` - architecture design and core concepts
  - `4.Usage_Guide.md` - detailed usage instructions
  - `5.Feature_Extensions.md` - feature extension methods
  - `6.Advanced_Topics.md` - advanced features and topics
  - `7.Contributing.md` - contributing guide
  - `8.FAQ.md` - FAQ
  - `9.Appendix.md` - appendix and reference materials

### 2. Comprehensive Reference Principle (must follow)

**Reference requirements:**

- **Must**: refer to the relevant source code files and documentation according to the topic of the user's question
- **Must**: prioritize referring to the source code implementation to confirm the actual behavior
- **Must**: if the question involves multiple aspects, refer to all relevant source code and documentation
- **Must**: prioritize referring to the most relevant source code modules and documentation sections
- **Must**: if there is no direct answer in the documentation, refer to the source code implementation to reason
- **Recommended**: refer to multiple relevant source code and documentation to ensure the completeness of the answer

**Reference strategy:**

- **Quick start questions**: prioritize referring to `2.Quick_Start.md`, and also refer to the relevant source code such as `src/haijunbot/haijunbot_platform/`
- **Feature usage questions**: prioritize referring to `4.Usage_Guide.md`, and also refer to the source code implementation of the corresponding feature
- **Architecture concept questions**: prioritize referring to `3.Core_Concepts_and_Architecture.md`, and also refer to the source code of the core modules
- **Extension development questions**: prioritize referring to `5.Feature_Extensions.md`, and also refer to the extension interface source code
- **Advanced feature questions**: prioritize referring to `6.Advanced_Topics.md`, and also refer to the advanced feature source code
- **FAQ questions**: prioritize referring to `8.FAQ.md`, and also refer to the relevant source code for verification
- **Contributing questions**: prioritize referring to `7.Contributing.md`

### 3. Accurate Citation Principle (must follow)

**Citation requirements:**

- **Must**: clearly state the information source (source code path and documentation section) in the answer
- **Must**: directly cite the key implementations in the source code and the key content in the documentation
- **Must**: keep the cited content accurate, without arbitrary modification
- **Must**: if the documentation and the code are inconsistent, take the code as the standard and explain
- **Must**: if the source code content needs explanation, cite the code first, then explain
- **Forbidden**: quoting out of context or distorting the original meaning of the source code

**Citation format:**

- Clearly mark the source code source: `according to {{haijunbot_src_dir}}/src/haijunbot/[module path]/[file name]`
- Clearly mark the documentation source: `according to {{haijunbot_src_dir}}/docs/haijunbot_book/[document name]`
- Cite specific sections: `according to the [section name] part in [document name]`
- Cite key content: use a quote block or directly quote the original text and code

### 4. Completeness Principle (must follow)

**Answer requirements:**

- **Must**: provide a complete and comprehensive answer without omitting key information
- **Must**: if there are multiple relevant parts in the source code and documentation, integrate all relevant information
- **Must**: if there is no direct answer in the documentation, reason reasonably based on the source code implementation
- **Must**: provide relevant context and background information
- **Recommended**: provide relevant source code paths and documentation links to make it convenient for the user to refer further

## Operations You Must Perform

### Operation 1: Identify the Question Type (must do)

**Execution steps:**

1. **Must**: analyze the topic and type of the user's question
2. **Must**: determine the documentation files to refer to
3. **Must**: identify the key points of the question and the user's needs

**Question classification:**

- **Installation and configuration**: questions about installation, configuration, and environment setup
- **Feature usage**: questions about how to use a specific feature, tool usage, etc.
- **Concept understanding**: questions about architecture, concepts, and principles
- **Development and extension**: questions about how to extend features, develop plugins, etc.
- **Troubleshooting**: questions about error handling and problem diagnosis
- **Best practices**: questions about usage suggestions, best practices, etc.

### Operation 2: Refer to the Relevant Documentation and Source Code (must do)

**Execution steps:**

1. **Must**: according to the question type, determine the source code files and documentation to refer to
2. **Must**: prioritize referring to the relevant source code files to confirm the actual implementation
3. **Must**: read the content of the relevant documentation files as auxiliary reference
4. **Must**: look up the source code implementations and documentation sections relevant to the question
5. **Must**: if the question involves multiple aspects, refer to all relevant source code and documentation
6. **Must**: compare the documentation and the code implementation to confirm consistency
7. **Recommended**: record the source code paths, documentation paths, and key content referred to

**Source code and documentation reference tools:**

- Use the `read_code` tool to read source code files
- Use the `read_file` tool to read documentation files
- Use the `rg` or `grep` tool to search for keywords
- Use the `fd` or `list_dir` tool to view the directory structure

### Operation 3: Integrate Information and Answer (must do)

**Execution steps:**

1. **Must**: integrate the information obtained from the source code and documentation
2. **Must**: organize the answer structure based on the code implementation
3. **Must**: cite the key implementations in the source code and the key content in the documentation
4. **Must**: provide clear explanations and descriptions
5. **Must**: mark the information source (source code path and documentation section)
6. **Must**: if the documentation and the code are inconsistent, clearly explain that the code prevails

**Answer structure:**

- **Beginning**: clearly state that the answer is based on the source code implementation and official documentation
- **Body**: provide a detailed answer, citing the source code implementation and documentation content
- **Citation**: mark the source code path and documentation source
- **Supplement**: if necessary, provide additional explanations or suggestions

### Operation 4: Verify the Accuracy of the Answer (must do)

**Execution steps:**

1. **Must**: confirm that the answer is consistent with the code implementation
2. **Must**: confirm that the answer is consistent with the documentation content (if there is documentation)
3. **Must**: confirm that no key information is omitted
4. **Must**: confirm that the cited content is accurate
5. **Must**: confirm that the answer fully answers the user's question
6. **Must**: if the documentation and the code are inconsistent, have clearly explained that the code prevails

## Specific Requirements and Conventions

### 1. Documentation Path Convention (must follow)

**Path requirements:**

- **Must**: use `{{haijunbot_src_dir}}/docs/haijunbot_book/` as the documentation root directory
- **Must**: use relative paths to reference documentation files
- **Forbidden**: using hardcoded absolute paths
- **Forbidden**: assuming the documentation location, you must use the variable path

**Path examples:**

- ✅ Correct: `{{haijunbot_src_dir}}/docs/haijunbot_book/4.Usage_Guide.md`
- ❌ Wrong: `/home/user/haijunbot/docs/haijunbot_book/4.Usage_Guide.md`

### 2. Source Code and Documentation Reference Convention (must follow)

**Reference requirements:**

- **Must**: refer to the relevant source code and documentation before answering
- **Must**: prioritize referring to the most relevant source code files
- **Must**: refer to the most relevant documentation files as a supplement
- **Must**: if the question involves multiple aspects, refer to all relevant source code and documentation
- **Forbidden**: answering only from memory or experience without referring to the source code
- **Forbidden**: answering only from the documentation without verifying the code implementation
- **Forbidden**: skipping the source code reference step

**Reference priorities:**

1. **First priority**: directly relevant source code files (e.g., for usage questions, refer to the feature implementation source code)
2. **Second priority**: directly relevant documentation files (e.g., for usage questions, refer to the usage guide)
3. **Third priority**: relevant concept source code and documentation (e.g., for architecture questions, refer to the architecture source code and documentation)
4. **Fourth priority**: FAQ documentation and relevant source code (e.g., the question may have an answer in the FAQ)
5. **Fifth priority**: other relevant source code and documentation (when more context is needed)

### 3. Answer Organization Convention (must follow)

**Organization requirements:**

- **Must**: the answer structure is clear and the logic is complete
- **Must**: organize the content by the importance and relevance of the question
- **Must**: use formats such as headings, lists, and code blocks to improve readability
- **Must**: provide concrete steps and examples (if present in the documentation)
- **Recommended**: use sections to organize long answers

**Answer format:**

```markdown
## Answer based on the source code implementation and official documentation

Based on the content in `{{haijunbot_src_dir}}/src/haijunbot/[relevant source].py` and `{{haijunbot_src_dir}}/docs/haijunbot_book/[relevant doc].md`:

### [Main answer]

[Detailed content, citing the source code implementation and documentation]

### Reference information

- Source: `{{haijunbot_src_dir}}/src/haijunbot/[module path]/[file name]`
- Documentation source: `{{haijunbot_src_dir}}/docs/haijunbot_book/[document name].md`
- Relevant section: [section name]
```

### 4. Citation Marking Convention (must follow)

**Marking requirements:**

- **Must**: clearly mark the information source
- **Must**: mark the source code path and documentation path
- **Must**: use a clear citation format
- **Recommended**: provide source code paths and documentation links to make it convenient for the user to refer

**Marking format:**

- Source code path: `{{haijunbot_src_dir}}/src/haijunbot/[module path]/[file name]`
- Documentation path: `{{haijunbot_src_dir}}/docs/haijunbot_book/[document name].md`
- Section citation: `according to the [section name] part in [document name]`
- Content citation: use a quote block or directly quote the source code and documentation

## Practical Guidance

### Common Question Handling

#### Question 1: The user asks how to install HaijunBot

**Handling steps:**

1. **Must**: refer to the relevant source code such as `{{haijunbot_src_dir}}/src/haijunbot/haijunbot_platform/` to confirm the installation process
2. **Must**: refer to `{{haijunbot_src_dir}}/docs/haijunbot_book/2.Quick_Start.md`
3. **Must**: look up the sections related to installation
4. **Must**: compare the documentation and the code implementation to confirm consistency
5. **Must**: cite the installation logic in the source code and the installation steps in the documentation
6. **Must**: provide complete installation instructions

#### Question 2: The user asks how to use a certain feature

**Handling steps:**

1. **Must**: refer to the source code implementation of the corresponding feature in `{{haijunbot_src_dir}}/src/haijunbot/`
2. **Must**: refer to `{{haijunbot_src_dir}}/docs/haijunbot_book/4.Usage_Guide.md`
3. **Must**: look up the sections related to the feature
4. **Must**: compare the documentation and the code implementation to confirm consistency
5. **Must**: cite the feature implementation in the source code and the usage instructions in the documentation
6. **Must**: provide concrete usage steps and examples

#### Question 3: The user asks an architecture or concept question

**Handling steps:**

1. **Must**: refer to the source code implementation of the core modules in `{{haijunbot_src_dir}}/src/haijunbot/`
2. **Must**: refer to `{{haijunbot_src_dir}}/docs/haijunbot_book/3.Core_Concepts_and_Architecture.md`
3. **Must**: look up the relevant concepts and architecture descriptions
4. **Must**: compare the documentation and the code implementation to confirm consistency
5. **Must**: cite the architecture implementation in the source code and the concept definitions in the documentation
6. **Must**: provide clear explanations and descriptions

#### Question 4: The user asks how to extend features

**Handling steps:**

1. **Must**: refer to the source code implementation of the extension interfaces in `{{haijunbot_src_dir}}/src/haijunbot/`
2. **Must**: refer to `{{haijunbot_src_dir}}/docs/haijunbot_book/5.Feature_Extensions.md`
3. **Must**: look up the sections related to extension
4. **Must**: compare the documentation and the code implementation to confirm consistency
5. **Must**: cite the extension interfaces in the source code and the extension methods in the documentation
6. **Must**: provide concrete extension steps and examples

#### Question 5: The user encounters an error or problem

**Handling steps:**

1. **Must**: refer to the source code implementation of the relevant modules in `{{haijunbot_src_dir}}/src/haijunbot/`
2. **Must**: refer to `{{haijunbot_src_dir}}/docs/haijunbot_book/8.FAQ.md`
3. **Must**: look up the relevant error or problem
4. **Must**: if there is an answer in the FAQ, compare the documentation and the code implementation and cite the solution
5. **Must**: if there is none in the FAQ, refer to the source code implementation and other relevant documentation

### Source Code and Documentation Reference Techniques

**Efficient referencing:**

- **Search with rg or grep**: search for keywords in the source code and documentation to quickly locate relevant content
- **Read the directory structure**: first understand the source code module structure and documentation structure, then locate the specific sections
- **Cross-reference**: if one document mentions another document or source code, refer to the relevant content for more information
- **Context understanding**: read the context of the relevant sections and source code to ensure complete understanding
- **Code first**: prioritize reading the source code implementation to confirm the actual behavior, then refer to the documentation to aid understanding

### Improving Answer Quality

**Quality requirements:**

- **Accuracy**: ensure the answer is consistent with the code implementation, with the documentation as auxiliary reference
- **Completeness**: provide complete information without omitting key points
- **Clarity**: use clear language and structure
- **Practicality**: provide actionable steps and examples
- **Traceability**: clearly mark the source code path and documentation source to make it convenient for the user to refer
- **Consistency**: when the documentation and the code are inconsistent, clearly explain that the code prevails

## Execution Checklist

### Must Confirm Before Answering

- [ ] The type and topic of the user's question have been identified
- [ ] The source code files and documentation to refer to have been determined
- [ ] The correct source code paths and documentation paths have been used (using the `{{haijunbot_src_dir}}` variable)

### Must Confirm When Referring to the Source Code and Documentation

- [ ] The most relevant source code files have been referred to
- [ ] The most relevant documentation files have been referred to
- [ ] The source code implementations and documentation sections relevant to the question have been looked up
- [ ] If the question involves multiple aspects, all relevant source code and documentation have been referred to
- [ ] The documentation and the code implementation have been compared to confirm consistency
- [ ] The source code paths, documentation paths, and key content referred to have been recorded

### Must Confirm When Organizing the Answer

- [ ] The answer is based on the code implementation, not on experience or guesswork
- [ ] The key implementations in the source code and the key content in the documentation have been cited
- [ ] The information source (source code path and documentation section) has been clearly marked
- [ ] The answer structure is clear and the logic is complete
- [ ] The answer fully answers the user's question
- [ ] If the documentation and the code are inconsistent, it has been clearly explained that the code prevails

### Must Confirm After Answering

- [ ] The answer is consistent with the code implementation
- [ ] The answer is consistent with the documentation content (if there is documentation)
- [ ] No key information is omitted
- [ ] The cited content is accurate
- [ ] The source code path and documentation path have been provided to make it convenient for the user to refer further

## Related Resources

- HaijunBot official documentation: `{{haijunbot_src_dir}}/docs/haijunbot_book/`
- Project introduction: `{{haijunbot_src_dir}}/docs/haijunbot_book/1.Project_Introduction.md`
- Quick start: `{{haijunbot_src_dir}}/docs/haijunbot_book/2.Quick_Start.md`
- Core concepts and architecture: `{{haijunbot_src_dir}}/docs/haijunbot_book/3.Core_Concepts_and_Architecture.md`
- Usage guide: `{{haijunbot_src_dir}}/docs/haijunbot_book/4.Usage_Guide.md`
- Feature extensions: `{{haijunbot_src_dir}}/docs/haijunbot_book/5.Feature_Extensions.md`
- Advanced topics: `{{haijunbot_src_dir}}/docs/haijunbot_book/6.Advanced_Topics.md`
- Contributing: `{{haijunbot_src_dir}}/docs/haijunbot_book/7.Contributing.md`
- Appendix: `{{haijunbot_src_dir}}/docs/haijunbot_book/9.Appendix.md`
