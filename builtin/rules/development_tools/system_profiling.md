---
name: system_profiling
description: Triggered when the system environment needs to be analyzed or a host profile needs to be generated. Triggered whenever the user mentions "system profile", "host analysis", "environment detection", "hardware information", "system assessment". Not triggered: only viewing a single hardware parameter; only checking disk space; only viewing CPU usage.
---

# System Environment Profiling Rules

## Rule Introduction

This rule is used to analyze the hardware, software, and resources of the current system environment and generate a local environment profile report. The report helps the user identify what types of work the current system is suitable for (such as AI training, web development, compilation/build, etc.).

## Principles You Must Follow

### 1. Report Path Conventions

**Requirements:**

- **Must**: Save the report file in the `{{ haijunbot_data_dir }}/reports/` directory
- **Must**: The report file name is fixed as `system_profile.md`
- **Must**: Overwrite the old report on each run to ensure the report content is up to date
- **Forbidden**: Save the report in any other directory
- **Forbidden**: Use dynamic file names (such as those with timestamps)

### 2. Information Collection

**Requirements:**

- **Must**: Collect real, accurate system information
- **Must**: Get information using standard system commands (such as `uname`, `free`, `df`, `lscpu`, etc.)
- **Must**: Organize the collected information into a structured form
- **Forbidden**: Fabricate or guess system information
- **Forbidden**: Collect sensitive information (such as passwords, keys, etc.)

### 3. Report Format Conventions

**Requirements:**

- **Must**: Generate the report in Markdown format
- **Must**: Include the report generation time
- **Must**: Use clear headings and sections
- **Must**: Summarize and evaluate the key metrics

## Mandatory Operations

### Operation 1: Collect system information

**Execution steps:**

1. Get operating system info: `uname -a`, `cat /etc/os-release`
2. Get CPU info: `lscpu` or `cat /proc/cpuinfo`
3. Get memory info: `free -h`
4. Get disk info: `df -h`
5. Get GPU info (if any): `nvidia-smi` or `lspci | grep -i vga`
6. Get network info: `ip addr` or `ifconfig`
7. Get installed development tools: `python3 --version`, `node --version`, `docker --version`, etc.

### Operation 2: Generate the profile report

**Execution steps:**

1. Ensure the `{{ haijunbot_data_dir }}/reports/` directory exists and create it if it does not
2. Organize the collected information into Markdown format
3. Save the report to `{{ haijunbot_data_dir }}/reports/system_profile.md`

**Report template:**

```markdown
# System Environment Profile Report

**Generation time**: YYYY-MM-DD HH:MM:SS

## 1. System Overview

| Item                | Info |
| ------------------- | ---- |
| Operating system    | ...  |
| Kernel version      | ...  |
| System architecture | ...  |
| Hostname            | ...  |

## 2. Hardware Resources

### 2.1 CPU

- **Model**: ...
- **Cores**: ...
- **Threads**: ...
- **Clock speed**: ...

### 2.2 Memory

- **Total memory**: ...
- **Available memory**: ...
- **Usage**: ...

### 2.3 Disk

| Mount point | Total size | Used | Available | Usage |
| ----------- | ---------- | ---- | --------- | ----- |
| /           | ...        | ...  | ...       | ...   |

### 2.4 GPU

- **Model**: ...
- **Video memory**: ...
- **CUDA support**: ...

## 3. Software Environment

### 3.1 Development Tools

| Tool    | Version |
| ------- | ------- |
| Python  | ...     |
| Node.js | ...     |
| Docker  | ...     |
| Git     | ...     |

### 3.2 Programming Language Environments

- ...

## 4. Network Configuration

- **IP address**: ...
- **Network interfaces**: ...

## 5. Recommended Work Types

Based on the configuration above, this system is suitable for the following work:

| Work type          | Suitability | Description                                  |
| ------------------ | ----------- | -------------------------------------------- |
| AI/ML training     | ⭐⭐⭐⭐⭐      | Ample GPU memory, suitable for large model training |
| Web development    | ⭐⭐⭐⭐⭐      | Complete environment, suitable for full-stack development |
| Compilation/build  | ⭐⭐⭐⭐        | Many CPU cores, fast compilation             |
| Data processing    | ⭐⭐⭐⭐        | Ample memory, suitable for big data processing |

## 6. Suggestions and Optimizations

- ...
```

### Operation 3: Work type assessment

**Evaluation dimensions:**

1. **AI/ML training**: evaluate GPU model, video memory size, and CUDA support
2. **Web development**: evaluate Node.js, Python, Docker, and other environments
3. **Compilation/build**: evaluate CPU core count, memory size, and disk speed
4. **Data processing**: evaluate memory size, disk space, and Python/R environments
5. **Containerized deployment**: evaluate Docker, Kubernetes, and other environments

## Checklist

After completing the task, be sure to confirm:

- [ ] The report file has been created at `{{ haijunbot_data_dir }}/reports/system_profile.md`
- [ ] The report includes system overview, hardware resources, software environment, network configuration, and other information
- [ ] The report includes work type recommendations
- [ ] The report is in Markdown format and easy to read
- [ ] The report includes the generation time
- [ ] The old report has been overwritten
