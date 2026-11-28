# HaijunBot Offline Installation Guide

## Overview

The HaijunBot offline installation package allows you to quickly deploy the HaijunBot AI assistant in an environment without network connectivity. The offline package contains all necessary dependencies, including the Python environment, a virtual environment, built-in tools, and frontend build artifacts.

## Use Cases

- **Network-restricted environments**: environments that cannot access PyPI or GitHub
- **Rapid deployment**: when you need to deploy quickly on multiple machines
- **Stable version distribution**: ensures all machines use the same dependency versions
- **Offline demonstration**: demonstrating HaijunBot features in places without network access

## System Requirements

### Supported Architectures

- **x86_64** (AMD64/Intel64)
- **aarch64** (ARM64)

### Minimum Requirements

- **Operating system**: Linux (Ubuntu 20.04+ or CentOS 7+ recommended)
- **Disk space**: at least 2GB of available space
- **Memory**: at least 1GB RAM
- **Optional**: Git (for version management and updates)

## Creating an Offline Installation Package

### Step 1: Prepare the Environment

Make sure you have successfully installed HaijunBot and that the virtual environment works properly:

```bash
# Check whether HaijunBot works properly
haijunbot --version

# Check the virtual environment
ls -la .venv/
```

### Step 2: Run the Packaging Script

```bash
# Enter the HaijunBot project directory
cd ~/HaijunBot

# Run the packaging script
./scripts/create_offline_package.sh

# Or specify the output directory
./scripts/create_offline_package.sh /path/to/output
```

### Step 3: View the Packaging Result

After packaging completes, the following files are generated in the output directory:

```bash
# View the offline package
ls -lh offline_package/

# Example output:
# haijunbot-offline-20250115-143022.tar.gz  (about 1-2GB)
```

### Packaging Contents

The offline package contains the following:

| Directory/File | Description                        | Approximate Size |
| -------------- | ---------------------------------- | ---------------- |
| source/        | HaijunBot source code                 | ~50MB            |
| venv/          | Python virtual environment         | ~900MB           |
| python/        | Python 3.12 standalone environment | ~50MB            |
| deps/          | Built-in tools (uv, rg, fd, etc.)  | ~160MB           |
| frontend/dist/ | Frontend build artifacts           | ~10MB            |
| install.sh     | Installation script                | ~10KB            |
| README.md      | Usage instructions                 | ~5KB             |

## Using the Offline Installation Package

### Step 1: Transfer the Offline Package

Transfer the offline package to the target machine:

```bash
# Transfer using scp
scp haijunbot-offline-*.tar.gz user@target-machine:/home/user/

# Or use a USB storage device
cp haijunbot-offline-*.tar.gz /media/usb/
```

### Step 2: Extract the Offline Package

Extract on the target machine:

```bash
# Extract the offline package
tar -xzf haijunbot-offline-*.tar.gz

# Enter the extracted directory
cd haijunbot-offline
```

### Step 3: Run the Installation Script

```bash
# Install to ~/HaijunBot by default
./install.sh

# Or specify the installation directory
./install.sh /opt/haijunbot
```

### Step 4: Activate the Environment

After installation completes, activate the environment:

```bash
# Bash users
source ~/.bashrc

# Zsh users
source ~/.zshrc

# Fish users
source ~/.config/fish/config.fish

# Or directly activate the virtual environment
source ~/HaijunBot/.venv/bin/activate
```

### Step 5: Verify the Installation

```bash
# Check the HaijunBot version
haijunbot --version

# Start HaijunBot
haijunbot
```

## Installation Process Details

### Installation Script Execution Flow

1. **Source installation**: copy the HaijunBot source code to the target directory
2. **Virtual environment configuration**: copy the virtual environment and fix path references
3. **Python environment configuration**: configure the Python 3.12 environment
4. **Built-in dependency installation**: install built-in tools (uv, rg, fd, etc.)
5. **Frontend build artifacts**: install the frontend build results
6. **System installation**: install HaijunBot into the system PATH
7. **Shell configuration**: update the shell configuration file
8. **Installation verification**: verify the installation result

### Path Repair Mechanism

The virtual environment in the offline package contains path references from the original packaging machine. The installation script automatically fixes the following:

- **Scripts in the bin directory**: update the Python interpreter path
- **pyvenv.cfg**: update the home directory configuration
- **shebang lines**: fix the script execution path

## FAQ

### Q1: What should I do if the offline package is too large?

**Solution**:

1. **Exclude node_modules**: the packaging script already excludes node_modules automatically, and it will be rebuilt during installation
2. **Clean the cache**: clean the virtual environment cache before packaging
   ```bash
   find .venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
   find .venv -type f -name "*.pyc" -delete 2>/dev/null || true
   ```
3. **Compression optimization**: use a higher compression ratio
   ```bash
   tar -cvf haijunbot-offline.tar haijunbot-offline/
   gzip -9 haijunbot-offline.tar
   ```

### Q2: The haijunbot command is unavailable after installation?

**Solution**:

1. **Check the PATH configuration**:

   ```bash
   echo $PATH
   # Should contain ~/HaijunBot/.venv/bin
   ```

2. **Manually activate the environment**:

   ```bash
   source ~/HaijunBot/.venv/bin/activate
   ```

3. **Reinstall**:
   ```bash
   cd ~/HaijunBot
   pip install -e .
   ```

### Q3: What should I do if the architecture does not match?

**Solution**:

The offline package is packaged for a specific architecture, so you must ensure the architecture matches:

```bash
# Check the current architecture
uname -m

# Check the offline package architecture (see README.md)
cat haijunbot-offline/README.md
```

If the architecture does not match, you need to repackage or use the online installation method.

### Q4: Python version conflict?

**Solution**:

HaijunBot strictly requires Python 3.12. The offline package already includes the Python 3.12 environment, but if the system has other Python versions, conflicts may occur:

```bash
# Check the system Python version
python --version
python3 --version

# Use the Python in the virtual environment
~/HaijunBot/.venv/bin/python --version
```

### Q5: The frontend is inaccessible?

**Solution**:

If the frontend build artifacts are missing, you need to rebuild:

```bash
cd ~/HaijunBot/src/haijunbot/haijunbot_service/frontend
npm install
npm run build
```

## Advanced Usage

### Customizing the Packaging Contents

Modify the packaging script to include/exclude specific content:

```bash
# Edit the packaging script
vim scripts/create_offline_package.sh

# Customize EXCLUDE_PATTERNS
EXCLUDE_PATTERNS="
--exclude=.git
--exclude=node_modules
--exclude=tests  # Exclude test files
--exclude=docs   # Exclude documentation
"
```

### Multi-architecture Packaging

Create offline packages for different architectures:

```bash
# Package on an x86_64 machine
./scripts/create_offline_package.sh output_x86_64

# Package on an aarch64 machine
./scripts/create_offline_package.sh output_aarch64
```

### Version Management

Create an offline package for a specific version:

```bash
# Switch to a specific version
git checkout v3.1.20

# Create the offline package
./scripts/create_offline_package.sh output_v3.1.20
```

## Updates and Maintenance

### Updating the Offline Package

After HaijunBot is updated, recreate the offline package:

```bash
# Update the source code
git pull origin main

# Update dependencies
pip install -e .

# Repackage
./scripts/create_offline_package.sh
```

### Updating in an Offline Environment

Update HaijunBot in an offline environment:

1. **Create an offline package for the new version** (on a networked machine)
2. **Transfer it to the offline environment**
3. **Back up the old version**:
   ```bash
   mv ~/HaijunBot ~/HaijunBot.backup
   ```
4. **Install the new version**:
   ```bash
   ./install.sh ~/HaijunBot
   ```

## Security Considerations

### Offline Package Security

- **Transfer security**: use an encrypted transfer method (e.g. scp over SSH)
- **Storage security**: keep the offline package safe and avoid unauthorized access
- **Version verification**: verify the integrity and source of the offline package

### Post-installation Security

- **API keys**: pay attention to secure storage when configuring API keys
- **Configuration files**: protect sensitive information in configuration files
- **Log files**: regularly clean up sensitive information in log files

## Technical Support

### Getting Help

- **GitHub Issues**: https://github.com/takebox/HaijunBot/issues
- **Documentation**: https://github.com/takebox/HaijunBot/docs
- **Community**: join the HaijunBot community for support

### Reporting Issues

When you encounter a problem, please provide the following information:

1. System architecture and version
2. Offline package creation time and architecture
3. Installation log output
4. Error messages and screenshots

## Appendix

### Packaging Script Parameters

```bash
./scripts/create_offline_package.sh [output directory]
```

| Parameter        | Description                 | Default           |
| ---------------- | --------------------------- | ----------------- |
| Output directory | Offline package output path | ./offline_package |

### Installation Script Parameters

```bash
./install.sh [installation directory]
```

| Parameter              | Description              | Default  |
| ---------------------- | ------------------------ | -------- |
| Installation directory | HaijunBot installation path | ~/HaijunBot |

### Offline Package File Structure

```
haijunbot-offline/
├── source/              # HaijunBot source code
│   ├── src/
│   ├── builtin/
│   ├── pyproject.toml
│   └── ...
├── venv/                # Python virtual environment
│   ├── bin/             # Executable files
│   ├── lib/             # Python libraries
│   └── pyvenv.cfg       # Virtual environment configuration
├── python/              # Python standalone environment
│   └── cpython-3.12.x-linux-x86_64-gnu/  # cpython subdirectory created by uv
│       ├── bin/         # Python executable files
│       │   └── python3.12
│       └── lib/         # Python standard library
├── deps/                # Built-in tools (current architecture only)
│   └── x86_64_linux/    # or aarch64_linux, depending on the packaging machine architecture
│       ├── bin/         # uv, rg, fd, etc.
│       └── lib/         # Dependency libraries
├── frontend/            # Frontend build artifacts
│   └── dist/            # Build results
├── install.sh           # Installation script
└── README.md            # Usage instructions
```

---

**Last updated**: 2025-01-15
**Version**: 1.0
**Author**: HaijunBot Team
