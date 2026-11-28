---
name: opensource-deployment
description: Triggered when an open source project needs to be deployed or open source software needs to be configured. Triggered whenever the user mentions "deploy open source project", "open source deployment", "open source software deployment", "open source project deployment", "deploy open source software", "open source configuration". Not triggered: only developing an open source project without deployment; only using open source software without deploying it; discussing open source concepts without specific deployment operations.
---

# Open Source Deployment Standards

## Pre-Deployment Preparation

### Environment Assessment

- Check the system requirements (operating system, dependency libraries, hardware resources)
- Determine the network configuration (ports, firewall, DNS resolution)
- Prepare the deployment user account and permissions

### Obtaining the Source Code

- Clone or download the stable version from the official repository
- Verify source integrity (checksums, GPG signatures)
- Check version and environment compatibility

## Deployment Process

### 1. Install Dependencies

- Install system dependency packages
- Install project dependencies (e.g. `npm install`, `pip install`)
- Configure environment variables

### 2. Build the Project

- Run the build command (e.g. `make`, `gradle build`)
- Handle compilation errors
- Generate the deployment package

### 3. Configuration Management

- Copy the configuration template into the production configuration
- Modify configurations such as database connections and API keys
- Configure auxiliary capabilities such as logging and monitoring

### 4. Database Initialization

- Create the database and user
- Run database migration scripts
- Import initial data

### 5. Start Services

- Start using a process manager (such as systemd, supervisor)
- Configure auto-start on boot
- Verify the service status is normal

## Security Configuration

- Change default passwords
- Disable debug mode
- Configure HTTPS certificates
- Set firewall rules
- Update security patches regularly

## Checklist

- [ ] Environment assessment completed
- [ ] Source code obtained and verified
- [ ] Dependencies installed
- [ ] Build succeeded
- [ ] Configuration updated
- [ ] Database initialized
- [ ] Services started
- [ ] Security configuration completed
- [ ] Functional verification passed
