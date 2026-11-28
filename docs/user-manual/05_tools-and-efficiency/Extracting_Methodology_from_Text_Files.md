# Extract Methodology from Text Files

## Use Cases

When you already have a set of experience notes, a retrospective record, operation instructions, or other text material, and want to organize it into a reusable methodology and save it, you can use the "extract methodology from text files" command.

## Steps

1. Prepare a text file whose content can be experience notes, a process document, or a problem-solving record.
2. In the terminal, run the extract methodology command, for example: `hm extract your-text-file.txt --scope global`.
3. Choose the save scope:

   - global
   - project

4. If you choose the project scope, make sure the current directory is inside a Git repository.
5. After submitting the command, the system reads the text content and tries to extract a structured methodology.
6. After a successful extraction, the system saves the result to the specified scope and merges it with the existing methodologies.

## Prompts and Feedback You Will See

- At the start, the system prompts that it is extracting the methodology.
- If the extraction succeeds, it displays "extracted valid methodology", along with the number successfully saved and the target location.
- If the returned result format is incorrect, the system prompts "invalid response format".
- If YAML parsing fails, it clearly prompts "YAML parsing failed" along with the specific error information.
- If the overall extraction flow is abnormal, it also displays the reason for the extraction failure.

## Notes

- The input must be a text file, not a JSON methodology import file.
- The project scope depends on a Git repository; if you are not currently in a repository, this scope is unavailable.
- The extraction result is merged with the existing methodologies, and content with the same name is overwritten by the new result.
- The clearer and more focused the text material, the more likely it is to yield a reusable methodology result.
