# Research Official Docs and Generate Deployment Steps

## Use Cases

When you are going to deploy an open-source project but do not want to just try things out by experience, instead wanting to organize clear and executable deployment steps based on official documentation, official repositories, and community material, you can use the built-in open-source deployment expert.

## Steps

1. In the task, clearly tell the system: use the open-source deployment expert.
2. Provide the name of the project to be deployed, the version, the target environment, and special requirements.
3. Ask the system to research, in priority order:

   - the official repository
   - README
   - the official deployment documentation
   - community best practices

4. If you want to directly start a complete task, you can use a description like: `Please use the open-source deployment expert to research the official repository and official documentation of the xx project, and organize a set of executable deployment steps for an Ubuntu 22.04 server, along with verification methods, key configuration explanations, and common issue troubleshooting suggestions.`
5. After submitting the task, wait for the system to first understand the project and environment requirements, then organize the deployment steps.
6. After obtaining the output result, execute the deployment step by step and check progressively according to the verification methods in the document.

## Prompts and Feedback You Will See

- The system usually first supplements items to confirm, such as the version, operating system, runtime environment, or deployment method.
- The output result contains structured deployment steps rather than scattered suggestions.
- The document usually also includes:

  - key configuration explanations
  - verification methods
  - notes
  - common issues or troubleshooting suggestions

- If a problem is encountered during deployment, the system continues to troubleshoot by combining the materials.

## Notes

- This is an expert-type task entry point, not a fixed CLI command.
- The focus is to prioritize official materials rather than skipping research and directly giving empirical commands.
- The clearer the target environment, the more executable the output, for example local development, a server, a container, or a specific system version.
- If the project's own documentation is scattered, the deployment expert usually first helps you aggregate the entry materials.
- At a minimum, the three basic pieces of information — project name, version, and target environment — should be provided; otherwise the deployment steps can usually only remain at a rather general reference level.
