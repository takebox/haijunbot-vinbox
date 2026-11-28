# Configuring Custom Input Tags and Text Replacement Rules

## Use Cases

If you frequently type repeated long passages of text, such as fixed instructions like "analyze first, then execute" or "output according to team conventions", you can define them as short tags and have HaijunBot automatically expand them on input. The config option used by this capability is `replace_map`.

## Steps

1. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
2. Add or modify `replace_map` in the config file.
3. Each tag corresponds to an object, and the commonly used fields are:
   - `template`: the text content to replace with
   - `append`: whether to append on top of the existing template
4. For example:

   ```yaml
   replace_map:
     /spec:
       template: |
         Please first provide the task understanding, risk assessment, execution steps, and acceptance criteria.
       append: false

     /safe:
       template: |
         All modifications must be minimal; read before writing, and do not speculate.
       append: false
   ```

5. After saving the config file, restart the session.
6. In subsequent input, use the tags you defined, for example typing `/spec` or `/safe`, and observe whether they are expanded into the corresponding text.

## Prompts and Feedback You Will See

- This feature usually does not pop up a separate "replacement succeeded" prompt.
- The most direct way to verify is to see whether the content finally sent to the system has already been expanded according to `replace_map`.
- If you define a tag with the same name as a built-in rule, the custom content overrides the built-in item with the same name.
- If there is no effect after the modification, usually first check:
  - Whether the config file is written at `~/.haijunbot/config.yaml`
  - Whether the YAML indentation of `replace_map` is correct
  - Whether the current session was restarted after the modification

## Notes

- The config option name is `replace_map`, and its value is an object, not an array.
- Tags are recommended to carry a clear prefix, such as `/spec`, `/safe`, `/jira`, to avoid conflicts with ordinary natural language.
- `template` can contain multiline text; using the YAML `|` style to preserve formatting is recommended.
- If the replacement content is very long, it is recommended to test once with a simple input first to confirm the expansion result matches expectations.
