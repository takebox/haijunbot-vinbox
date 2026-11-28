# Pre-Deployment Environment and Dependency Checks

## Use Cases

When you are about to deploy an open-source project and want to check whether the environment meets the requirements before actually executing, so as to avoid discovering halfway through deployment that the version, dependencies, disk, or network conditions are unsuitable, you can have the deployment flow perform environment and dependency checks first.

## Steps

1. In the deployment task, explicitly require: perform the environment check first, then enter the formal deployment.
2. Provide the target project, version, and runtime environment information.
3. Have the system check the runtime environment and dependencies relevant to your deployment goal, for example:

   - Python
   - Node.js
   - Go
   - Rust
   - a virtual environment or tool environment
   - operating system information
   - system dependencies
   - disk space
   - network connectivity

4. If you want to state the task directly, you can use an expression like: `Before deploying the xx project, please first check whether Python, uv, system dependencies, disk space, and network connectivity in the Ubuntu 22.04 environment meet the requirements, and list the items that need to be completed.`
5. Based on the check result the system gives, first complete the installation, upgrade, or alternative handling of the missing items.
6. Once the environment is satisfied, continue with the formal deployment steps.

## Prompts and Feedback You Will See

- The system first gives a judgment of whether the current environment meets the deployment requirements.
- If it finds a version mismatch, missing dependencies, or an unsuitable environment, it gives clear remediation suggestions.
- For Python projects, it usually pays special attention to `uv` and the virtual environment state.
- After completing the check, you get an environment checklist or remediation suggestions more suitable for continuing the deployment.

## Notes

- This is usually a prerequisite stage in the deployment expert flow, not a completely independent general-purpose command.
- The environment check is not an optional extra but an important step before the formal deployment.
- If you skip this step, the probability of subsequent deployment failure rises noticeably.
- The check conclusion should be understood in the context of your target environment, for example a local machine, a container, CI, or a remote server.
- The more specific the environment information, the more accurate the check items; if you do not state the system version, deployment method, and runtime user, the result tends to be too general.
