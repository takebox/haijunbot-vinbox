---
name: remote-deployment
description: Triggered when HaijunBot needs to be deployed remotely or a remote development environment needs to be configured. Triggered whenever the user mentions "remote deployment", "remote development", "remote environment", "remote configuration", "remote server", "SSH deployment". Not triggered: only local deployment (use the opensource-deployment rules); only discussing remote concepts without specific operations.
---

# Remote Deployment Standards

## Connection Management

### SSH Connection

- Use SSH key authentication and avoid password login
- Configure the SSH config file (`~/.ssh/config`) to simplify connections
- Forward ports via SSH tunnels when necessary

### Secure Connection

- Forbid direct root login
- Use a non-standard port to reduce the risk of being scanned
- Configure the firewall to only allow trusted IPs
- Enable Fail2Ban to prevent brute-force attacks

## Environment Configuration

### System Preparation

- Update system packages
- Install necessary tools (git, curl, wget, etc.)
- Configure the timezone and locale
- Create a dedicated deployment user

### Installing Dependencies

- Install the Python environment (pyenv or conda)
- Install the Node.js environment (nvm)
- Install Docker and Docker Compose
- Install databases (PostgreSQL, MySQL, Redis, etc.)

## Deployment Process

### 1. Code Transfer

- Transfer code with `git clone` or `rsync`
- Configure git hooks for automatic deployment
- Automate deployment with a CI/CD pipeline

### 2. Environment Variables

- Create a `.env` file to configure environment variables
- Use a secrets management service to store sensitive information
- Keep development, test, and production configuration separate

### 3. Service Management

- Manage services with systemd
- Configure log rotation
- Set up monitoring and alerts

### 4. Reverse Proxy

- Configure Nginx or Caddy as a reverse proxy
- Configure SSL certificates (such as Let's Encrypt)
- Set up load balancing

## Checklist

- [ ] SSH connection configured
- [ ] Security configuration completed
- [ ] System dependencies installed
- [ ] Code transferred
- [ ] Environment variables configured
- [ ] Services started
- [ ] Reverse proxy configured
- [ ] HTTPS enabled
- [ ] Monitoring configured
