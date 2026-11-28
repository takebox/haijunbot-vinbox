# Analyze External Security Issue JSON

## Use Cases

When you already have an externally generated security issue JSON file and want HaijunBot to further categorize, aggregate, and analyze these issues, you can directly use the external JSON analysis entry point without having to rescan the code.

## Steps

1. Prepare a security issue JSON file.
2. In the terminal, enter the basic command: `hsec analyze your-issues.json`
3. If you need to save a Markdown report and limit the number processed per batch, you can run: `hsec analyze your-issues.json --output-format markdown --output-file report.md --cluster-limit 30 --enable-verification`
4. If you want to turn off secondary verification or turn off forced memory, you can also specify explicitly: `hsec analyze your-issues.json --no-verification --no-force-save-memory`
5. After submitting the command, wait for the system to read and analyze the issue list in the input file.
6. If you need to save the result, you can specify an output file; if you do not, the result is displayed directly in the terminal.

## Prompts and Feedback You Will See

- When the analysis succeeds, the system outputs the analysis result, or writes the report to the specified file.
- If the input JSON does not conform to the standard format, the system tries to perform a compatible conversion and continue the analysis.
- If the input file does not exist, the system clearly prompts an error and exits.
- If the analysis fails or an unknown error occurs, the system gives a clear failure prompt.
- By default, secondary verification is enabled; if you do not need it, you can explicitly turn it off with `--no-verification`.

## Notes

- This is an analysis of an "existing issue list", not a rescan of the source code.
- If no output file is specified, the result is printed directly in the terminal.
- The input file must be a readable JSON file, otherwise the flow cannot start.
- `--enable-verification/--no-verification` and `--force-save-memory/--no-force-save-memory` are paired boolean switches, which you can explicitly choose as needed.
- If you want to scan code directly according to the current project configuration, you should use the "run a security scan" entry point, not this command.
