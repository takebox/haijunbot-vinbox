# Configure Security Scans

## Use Cases

When you are about to use HaijunBot's security scanning capability but want to first clarify the scan target, language scope, excluded directories, output format, and analysis parameters, you can configure the security scan settings first instead of manually re-entering them every time.

## Steps

1. In the terminal, enter `hsec config` and add arguments as needed.
2. For example, to scan C/C++/Rust files in the current directory, exclude `build` and `third_party`, and output a Markdown report to a file, you can run: `hsec config --target . --languages c,cpp,rust --exclude-dirs build,third_party --output-format markdown --output-file report.md`
3. If you also want to limit the number of clusters, turn off secondary verification, or specify a model group, you can continue appending arguments, for example: `hsec config --cluster-limit 30 --no-verification --llm-group security`
4. Set the following as needed according to your goal:
   - the scan target, which can be a file path or a directory path
   - language filtering
   - excluded directories
   - output format
   - output file
   - cluster limit
   - whether to enable secondary verification
   - whether to force-save memory
   - the runtime model group

5. If you only want to confirm the current configuration, you can run directly: `hsec config --show`
6. If you want to restore the default configuration, you can run: `hsec config --clear`
7. After the modifications are complete, the system saves the configuration to the local `.haijunbot/sec/config.json`, and subsequent scan commands automatically read these settings.

## Prompts and Feedback You Will See

- After setting a certain option, the system echoes that the item has been updated.
- In view mode, the system displays the current configuration file path and the complete configuration content.
- After clearing the configuration, the system prompts that the configuration has been cleared and echoes the default configuration.
- If the output format is not a supported type, the system reports an error directly.
- If you do not provide any valid modification arguments, the system prompts you to add configuration arguments.

## Notes

- This is a command-line entry point, not an expert-type task entry point.
- The output format only supports `csv` or `markdown`.
- The configuration is written to the local `.haijunbot/sec/config.json`, and the subsequent `hsec scan` uses it directly.
- If you have not configured it yet, it is recommended to complete this step before the first scan.
