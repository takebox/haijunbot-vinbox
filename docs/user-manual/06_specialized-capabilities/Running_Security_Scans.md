# Run a Security Scan

## Use Cases

When you have completed the security scan configuration and want to directly run a security scan on the current project, a certain directory, or specified files and generate a report, you can use the security scan command.

## Steps

1. First confirm that the scan arguments have been saved through the configuration command.
2. In the terminal, enter the following command, then press Enter: `hsec scan`
3. This command itself does not accept extra business arguments; after submitting it, it automatically reads the local `.haijunbot/sec/config.json` configuration file.
4. If the target in the configuration is a directory, the system runs the scan on that directory.
5. If the target in the configuration is a file, the system first scans the directory it is in, then filters out the issue results related to that file.
6. After the scan is complete, view the terminal output, or check the report in the output file specified in the configuration.

## Prompts and Feedback You Will See

- If the configuration file does not exist, the system prompts you to run the configuration command first.
- After a successful scan, the system outputs Markdown or CSV report content.
- If you configured an output file, the system writes the report to that file, and usually also displays the content in the terminal.
- When the main scan flow cannot produce a result, the system falls back to direct scan mode to continue generating the report.
- If the target file does not exist, the system may fall back to continuing the scan by the current directory.

## Notes

- This command itself does not accept complete scan arguments; it relies on the saved configuration.
- `hsec scan --help` only has help information and no extra business options; before first use, you should run "configure security scans".
- The output file suffix is adjusted automatically according to the output format.
- If you only want to analyze an external JSON file, you should not use this command but instead use the external security issue analysis entry point.
