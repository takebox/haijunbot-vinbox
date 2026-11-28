# Configuring Default Auto-Loaded Rules

## Use Cases

If you want certain rules to be automatically included every time CodeAgent or a related Agent starts, rather than manually entering the rule names each time, you can set `default_rule_names` in the config file.

## Steps

1. First confirm that the rule names you want to load actually exist and are available.
2. Open the HaijunBot global config file: `~/.haijunbot/config.yaml`.
3. Add or modify `default_rule_names`, which is an array of strings. For example:

   ```yaml
   default_rule_names:
     - project:code_quality/haijunbot_user_manual_writing
     - global:security/basic_safe_editing
   ```

4. Save the config file.
5. Restart the session that reads the config.
6. If the startup entry point later also passes in rule names, the system merges `default_rule_names` with the rules passed from the command line and deduplicates them.

## Prompts and Feedback You Will See

- This config option usually does not pop up a separate "default rules loaded" prompt box.
- A more practical feedback is: in subsequent tasks, the system stably follows these default rule constraints.
- If a rule name is written incorrectly, a common symptom is that this rule does not take effect, rather than the system correcting it for you automatically.
- If you also pass `--rule-names` on the command line, what finally takes effect is the deduplicated merge of "config rules + command-line rules".

## Notes

- The config option name is `default_rule_names`.
- This is an array, not a single string.
- It is suitable for rules used stably long-term; temporary rules are better specified per single task.
- If you are not sure whether a rule name exists, confirm the rule source first before writing it into the config, to avoid a document that looks correct but is invalid at runtime.
