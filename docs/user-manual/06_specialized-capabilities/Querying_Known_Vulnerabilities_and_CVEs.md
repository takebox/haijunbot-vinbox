# Query Known Vulnerabilities and CVEs

## Use Cases

When you not only want to analyze the local code itself but also want to combine third-party dependencies, known vulnerability databases, and CVE information for a more complete security assessment, you can add Web search and known-vulnerability query requirements to the security vulnerability analysis task.

## Steps

1. In the security analysis task, clearly state: in addition to reading the code, also query related known vulnerabilities and CVE information.
2. Specify the dependencies, components, frameworks, or libraries to focus on.
3. First have the system finish reading the code and clarify the dependency relationships and potential risk points.
4. Then have the system supplement known security intelligence with Web search.
5. If you want to directly give an executable task, you can use a description like: `When analyzing this project's authentication module, please also query the known vulnerabilities and CVEs related to the OpenSSL and nginx used, and finally merge the local code risks and external vulnerability intelligence into one report.`
6. Finally, ask for the local code issues and external known vulnerability risks to be organized together into the report.

## Prompts and Feedback You Will See

- The final report covers not only the security issues in the local code but also known vulnerability-related risks.
- The system incorporates third-party dependency risks into the overall security assessment rather than only focusing on the business code.
- The query results usually serve as supplementary verification material to help you judge whether the dependencies have publicly known security intelligence risks.

## Notes

- Web search is a supplementary verification means; the premise is still to first understand the code and dependency relationships.
- This is not a pure keyword search detached from context; it should be used in combination with the actual dependencies of the current project.
- Known vulnerability information is suitable for supplementing the risk perspective but should not replace the local code review itself.
- If the dependency information is unclear, identifying dependencies first and then querying vulnerabilities is more reliable.
- Just saying "look up CVEs" is usually too broad; it is best to specify the dependency name, version range, or key module.
