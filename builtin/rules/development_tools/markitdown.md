---
name: markitdown
description: Triggered when a file needs to be converted to Markdown format. Triggered whenever the user mentions "file to markdown", "document conversion", "markitdown". Not triggered: only writing Markdown content; only reading Markdown files; Markdown formatting that does not involve file conversion.
license: MIT
---

# markitdown Tool Usage Rules

## Rule Introduction

markitdown is a lightweight Python tool developed by Microsoft, dedicated to converting various file formats into Markdown. It is well suited for LLM and text analysis pipelines. It supports conversion of many formats including PDF, PowerPoint, Word, Excel, images, audio, and HTML, and preserves important document structure (headings, lists, tables, links, etc.).

## Principles You Must Follow

### 1. Installation and Configuration

**Requirements:**

- **Must**: Install the full-featured version directly for the best experience
- **Recommended**: Use the uv tool for installation management

**Examples:**

```bash
# install the full-featured markitdown with uv
uv tool install 'markitdown[all]'
```

### 2. Usage Safety

**Requirements:**

- **Must**: Ensure a secure environment when handling sensitive documents
- **Must**: Configure the correct endpoint when using Azure Document Intelligence
- **Forbidden**: Hardcode sensitive information such as API keys into code
- **Forbidden**: Process malicious files from unknown sources

## Operations You Must Perform

### Operation 1: Command-line usage

**Execution steps:**

1. Basic file conversion
2. Specify the output file
3. Pipe operations

**Examples:**

```bash
# basic conversion
markitdown document.pdf > output.md

# specify the output file
markitdown document.pdf -o output.md

# pipe operation
cat document.pdf | markitdown
```

### Operation 2: Python API usage

**Execution steps:**

1. Import the MarkItDown class
2. Create a converter instance
3. Perform the conversion

**Examples:**

```python
from markitdown import MarkItDown

# basic usage
md = MarkItDown(enable_plugins=False)
result = md.convert("document.docx")
print(result.text_content)

# use an LLM for image description
from openai import OpenAI

client = OpenAI()
md = MarkItDown(
    llm_client=client,
    llm_model="gpt-4o",
    llm_prompt="describe the image content"
)
result = md.convert("image.jpg")
```

### Operation 3: Plugin usage

**Execution steps:**

1. Install plugins
2. Enable plugin functionality
3. Use plugins to extend functionality

**Examples:**

```bash
# install the OCR plugin
pip install markitdown-ocr

# list available plugins
markitdown --list-plugins

# enable plugins
markitdown --use-plugins document.pdf
```

### Operation 4: Azure Document Intelligence integration

**Execution steps:**

1. Configure the Azure Document Intelligence endpoint
2. Use the Document Intelligence functionality
3. Process the conversion result

**Examples:**

```bash
# command-line usage
markitdown document.pdf -o output.md -d -e "<your-endpoint>"
```

```python
# Python API usage
from markitdown import MarkItDown

md = MarkItDown(docintel_endpoint="<your-endpoint>")
result = md.convert("document.pdf")
```

## Optional Dependencies

markitdown supports feature modules that can be installed on demand:

- `[all]` - install all optional dependencies
- `[pptx]` - PowerPoint file support
- `[docx]` - Word file support
- `[xlsx]` - Excel file support
- `[pdf]` - PDF file support
- `[az-doc-intel]` - Azure Document Intelligence
- `[audio-transcription]` - audio transcription
- `[youtube-transcription]` - YouTube transcription

## Checklist

After completing the task with markitdown, be sure to confirm:

- [ ] markitdown and the required dependencies are installed correctly
- [ ] The virtual environment is activated (if used)
- [ ] The input file format is supported
- [ ] The output Markdown structure is correct
- [ ] Sensitive information has been handled properly
- [ ] The necessary error handling has been implemented

## Related Resources

- Official GitHub repository: [https://github.com/microsoft/markitdown](https://github.com/microsoft/markitdown)
- PyPI package page: [https://pypi.org/project/markitdown/](https://pypi.org/project/markitdown/)
- Azure Document Intelligence: [https://learn.microsoft.com/azure/ai-services/document-intelligence](https://learn.microsoft.com/azure/ai-services/document-intelligence)
