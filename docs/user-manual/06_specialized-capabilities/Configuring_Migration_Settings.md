# Configure Migration Settings

## Use Cases

When you are about to perform a C→Rust migration and want to first set the root symbols, disabled libraries, additional notes, and FFI export validation options, you can configure the migration settings first so the subsequent migration pipeline can use them directly.

## Steps

1. In the terminal, enter `hc2r config` and add arguments as needed.
2. You can prepare the root symbols in the following ways:

   - automatically extract function names from a header or source file, for example: `hc2r config --files bzlib.h`
   - import function names line by line from a text file, for example: `hc2r config --files roots.txt`
   - directly enter a comma-separated list of root symbols on the command line, for example: `hc2r config --root-list-syms "func1,func2,func3"`

3. If needed, then set the disabled library list, for example: `hc2r config --disabled-libs "libc,libm"`
4. If there are special migration requirements, you can fill in additional notes, for example: `hc2r config --additional-notes "all functions must handle error cases and avoid panic"`
5. Enable or disable FFI export validation as needed, for example: `hc2r config --enable-ffi-export-validation` or `hc2r config --disable-ffi-export-validation`
6. If you only want to check the current configuration, you can run: `hc2r config --show`
7. If you want to restore the default values, you can run: `hc2r config --clear`
8. After the modifications are complete, the configuration is saved to the local `.haijunbot/c2rust/config.json`, for the subsequent `hc2r run` to read directly.

## Prompts and Feedback You Will See

- In view mode, the system displays the current configuration file path and the complete configuration content.
- After clearing the configuration, the system prompts that the configuration has been cleared.
- When extracting function names from a header or source file, the system prompts the extraction process and the extraction count.
- If the same root symbol is imported repeatedly, it is automatically deduplicated in the end.
- When the input file cannot be found, the system gives a clear prompt.

## Notes

- This is a command-line entry point; the configuration result is saved to a local configuration file for the subsequent pipeline to read.
- For non-source/header inputs, only `.txt` text files are accepted as the source of the symbol list.
- Additional notes support being cleared, suitable for reorganizing when the migration strategy changes.
- The main migration flow does not re-enter this content in the `run` command, so it is recommended to prepare the configuration first.
