# Referencing Files in Input and Automatically Attaching File Symbol Information

## When to Use

When you want the agent to understand the rough structure of a file, rather than just seeing a file name, you can reference the file path directly in the input and let the system automatically supplement the structured symbol information in the file.

## Steps

1. In the current task input, wrap the file path in single quotes, for example writing the target file in the form `'path/file-name'`.
2. Submit the task in the usual way.
3. The system checks whether these paths point to text files that actually exist.
4. If recognized successfully, the system automatically attaches the file's structured symbol information after your input, then hands it to the agent for processing.

## Prompts and Feedback You Will See

- Only paths written inside single quotes are recognized as files to be analyzed.
- If the file exists and is readable, the system automatically supplements the file's structure information, without you needing to organize it manually.
- If the path does not exist, is not a text file, or structure information cannot be extracted, the system usually does not report an extra error; it simply does not attach this part of the context.

## Notes

- This method is more suitable for readable files such as source code, configuration, and script text.
- If you do not wrap the path in single quotes, the system will not treat it as a file reference.
- This capability is meant to help the agent understand the file structure faster; it is not the same as automatically completing a full-text analysis for you.
