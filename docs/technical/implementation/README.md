# Technical Implementation Documentation

This directory contains the core technical implementation documentation for the HaijunBot Agent system, detailing the implementation details, design considerations, and technical approaches of various features.

## Document List

### Context Compression

- **[Context Compression Strategies Document](./context_compression_strategies.md)**
  - Details all implemented and planned context compression strategies
  - Includes strategy descriptions, implementation locations, trigger conditions, configuration methods, etc.
  - Suitable for understanding the overall architecture and available strategies of context compression

- **[Context Compression Flow Document](./context_compression_flow.md)**
  - Details the complete execution flow of context compression
  - Includes trigger conditions, strategy selection, execution order, fallback mechanisms, etc.
  - Suitable for understanding the actual workflow and best practices of context compression

### LSP Language Support

- **[Extending LSP Language Support for the Editor](./lsp_language_extension.md)**
  - Explains the "extend by changing configuration" LSP language support mechanism (the `lsp.languages` in `~/.haijunbot/config.yaml` is the sole configuration source)
  - Includes field descriptions, a complete example of adding a language (Rust), degradation behavior, and debugging methods
  - Suitable for developers who need to add language support to the editor or troubleshoot LSP issues

## Directory Description

This directory is used to store documents related to technical implementation, including:

- Implementation details of core features
- Design considerations of algorithms and strategies
- Detailed descriptions of technical approaches
- Implementation flows and best practices

## Related Documents

- [Best Practices Document](../../best_practices/HaijunBot_Rule_System_Introduction.md) - Usage guide and best practices
- [Configuration Document](../../haijunbot_config.md) - System configuration description
- [HaijunBot Book](../../haijunbot_book/1.Project_Introduction.md) - Complete user-manual
