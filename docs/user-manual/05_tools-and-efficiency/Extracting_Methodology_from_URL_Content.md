# Extract Methodology from URL Content

## Use Cases

When you want to distill the experience content from a web page, an online article, or external instructions into a local methodology, you can directly use the URL as input for extraction.

## Steps

1. Prepare the URL of the methodology source you want to extract.
2. In the terminal, run the command to extract methodology from a URL, for example: `hm extract-url "https://example.com/article" --scope global`.
3. Choose the save scope:

   - global
   - project

4. If you choose the project scope, make sure the current directory is inside a Git repository.
5. After submitting the command, the system extracts the methodology content based on that URL and tries to organize it into a structured result.
6. After a successful extraction, the result is saved to the specified scope and merged with the existing methodologies.

## Prompts and Feedback You Will See

- When the extraction starts, the system prompts that the extraction is being performed.
- After a successful extraction, it displays the number of methodologies successfully extracted and saved.
- If the returned content format does not meet the requirements, the system prompts "invalid response format".
- If the parsing stage fails, it prompts "YAML parsing failed" or other clear error information.
- If the scope argument is invalid, or the project scope lacks a Git repository context, the system also reports an error directly.

## Notes

- This is "extract methodology from URL content", not simply saving a link.
- If the final returned content format is incorrect, the system does not silently ignore it but directly prompts failure.
- The project scope still requires being inside a Git repository.
- Since this is an extraction-type operation, it is recommended to check the result afterward with "list all methodologies" or an export command.
