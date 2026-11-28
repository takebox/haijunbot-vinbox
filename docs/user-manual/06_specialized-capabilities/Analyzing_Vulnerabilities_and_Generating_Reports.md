# Analyze Code Vulnerabilities and Generate Reports

## Use Cases

When you want HaijunBot to deeply read code from a security perspective and output a structured vulnerability analysis report, you can use the built-in security vulnerability analyst to complete this task.

## Steps

1. In the task, clearly tell the system: use the security vulnerability analyst.
2. Specify the code scope, project module, or key risk area to be analyzed.
3. If needed, additionally state the security directions you particularly care about, for example:

   - input handling
   - authentication and authorization
   - session management
   - unsafe API usage
   - logic flaws

4. If you do not know how to organize the description, you can directly use a task like: `Please use the security vulnerability analyst to review src/auth and src/api, focusing on input validation, authentication and authorization, and sensitive information leakage risks, and output a Markdown report containing issue locations, trigger scenarios, impacts, and remediation suggestions.`
5. After submitting the task, wait for the system to first read the code and understand the overall architecture, modules, and data flow.
6. Ask the system to output a complete vulnerability analysis report including remediation suggestions.

## Prompts and Feedback You Will See

- The report usually contains:

  - issue location
  - issue description
  - severity
  - trigger scenario
  - impact
  - remediation suggestions

- The output result is more suitable for archiving and sharing in Markdown.
- If the task is more complex, the system may first split the analysis scope and then aggregate the results separately.
- The analysis emphasizes being evidence-based rather than making unfounded guesses.
- If you request structured output, the system usually organizes "issue + evidence + suggestion" into a report format convenient for later remediation.

## Notes

- This is an expert-type task entry point, not a fixed CLI subcommand.
- If the analysis scope is too large, it is recommended to focus on high-risk modules first to avoid an overly general report.
- The value of the report lies in the complete chain of "issue + evidence + remediation suggestion", not merely in listing risk names.
- For complex projects, analyzing in stages and then aggregating is usually more reliable than a one-time rough scan.
