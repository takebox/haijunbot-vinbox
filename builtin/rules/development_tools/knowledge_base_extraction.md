---
name: knowledge_base_extraction
description: Triggered when external technical documentation/manuals need to be added to the HaijunBot knowledge base. Triggered whenever the user mentions "import into knowledge base", "extract into knowledge base", "add this document to the knowledge base", "learn this document/manual", "save the documentation of a third-party framework/library/tool". Not triggered: only reading documents; only writing documents; searching existing knowledge base content.
license: MIT
---

# Knowledge Base Extraction Rules

## Rule Introduction

HaijunBot's knowledge base reuses the rules system mechanism: external technical documentation/manuals (such as usage manuals and API documentation of third-party frameworks, libraries, and tools) are read, summarized, and organized by the Agent itself, then written into the global rules directory `~/.haijunbot/rules/kb/` as rule files with front-matter. From then on, these knowledge base entries behave like ordinary rules: they are automatically pre-filtered, injected, and fetched on demand (`load_rule`) whenever the Agent needs them.

## Principles You Must Follow

### 1. Trigger Timing

**Requirements:**

- **Must**: Trigger when the user explicitly requests that an external technical document/manual be added to the long-term knowledge base
- **Must**: The document source is "external" (third-party frameworks/libraries/tools/protocols, etc.), not project-internal code or memory
- **Forbidden**: Import project-internal code, temporary notes, or content that does not need long-term retention into the knowledge base

### 2. Summarization and Organization

**Requirements:**

- **Must**: The Agent summarizes and organizes the document's key points itself, rather than copying the entire original document into the knowledge base
- **Must**: The extracted content should focus on technical substance (concepts, usage, parameters, examples, caveats) and remove redundancy
- **Must**: The knowledge base file written includes YAML front-matter (name/description) so it can be pre-filtered and injected
- **Forbidden**: Write un-extracted original documents without front-matter

### 3. Content Acquisition

**Requirements:**

- **Must**: Read local files with `read_code`; fetch public web pages with `read_webpage`
- **Must**: For websites that require login or dynamic rendering, log in and fetch with the browser extension (`browser_ext_*`), rather than relying only on URL fetching
- **Forbidden**: Fetch login-required websites only via URL (correct content cannot be obtained this way)

## Operations You Must Perform

### Operation 1: Acquire the document content

**Execution steps:**

1. Determine the document source: local file / public web page / website requiring login
2. Read local files with `read_code`
3. Fetch the body of public web pages with `read_webpage`
4. For websites requiring login, log in with the browser extension and then fetch the content
5. If the document is too long, read and summarize it in sections

### Operation 2: Summarize and organize the key points

**Execution steps:**

1. Read through the document and identify the topics and section structure
2. Summarize the technical key points by topic/section (concepts, usage, parameters, examples, caveats)
3. Output in Chinese, keeping necessary English terms, with a clear structure (headings, lists, code blocks)
4. Do not fabricate content that does not exist in the document

### Operation 3: Write the knowledge base file

**Execution steps:**

1. Determine the `category` (such as framework / tool / protocol / api) and the `title`
2. Write with `write_file` to `~/.haijunbot/rules/kb/<category>/<title>.md`
3. The file includes YAML front-matter (name/description); the body consists of the summarized key points
4. Confirm the write succeeded; the rule can be referenced as `global:kb/<category>/<title>`

**Example front-matter:**

```yaml
---
name: <title>
description: External document knowledge base entry, source <source>. Triggered when technical details about <title> need to be looked up.
---
```

## Checklist

After completing the task using knowledge base import, be sure to confirm:

- [ ] The document source is indeed external technical documentation/manual
- [ ] The correct content was acquired (login-required websites were accessed via the browser extension)
- [ ] Key points were summarized and organized (rather than copying the original text)
- [ ] Written to `~/.haijunbot/rules/kb/<category>/<title>.md` with front-matter
- [ ] The knowledge base entry can be read by `load_rule` (`global:kb/<category>/<title>`)

## Related Resources

- Knowledge base storage directory: `~/.haijunbot/rules/kb/<category>/<title>.md`
- Retrieval method: the `load_rule` tool (`global:kb/<category>/<title>`)
- Content acquisition: `read_code` (local), `read_webpage` (public web pages), `browser_ext_*` (websites requiring login)
