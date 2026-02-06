# FlexFlow Installation Guide

Complete installation guide for FlexFlow Manager.

## Quick Install

```bash
./install.sh
source ~/.bashrc
ff --version
```

Installation takes approximately 2 minutes on a standard system.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Step-by-Step Installation](#step-by-step-installation)
- [Installation Options](#installation-options)
- [Post-Installation](#post-installation)
- [Uninstallation](#uninstallation)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Prerequisites

### Required

**Anaconda or Miniconda**
- Required for Python 3.12 environment management
- Download: https://docs.conda.io/en/latest/miniconda.html

```bash
# Check if conda is installed
which conda

# Check conda version
conda --version
```

**Linux Operating System**
- Tested on Ubuntu 20.04+, CentOS 7+, and similar distributions
- Bash shell (for installation script)

### Optional

**Tecplot 360 EX**
- Required for PLT file operations
- PyTecplot library will be configured during installation
- Set `TECPLOT_360` environment variable if installed in non-standard location

### System Requirements

- **Disk Space**: ~500 MB for conda environment and dependencies
- **Memory**: 2 GB minimum, 4 GB recommended
- **Python**: 3.12 (automatically installed in conda environment)

## Installation Methods

FlexFlow offers four installation methods:

### 1. Fast Alias (Recommended)

**Best for:** Daily use, maximum performance

```bash
./install.sh
# Select Option 1: Fast Alias
```

**Features:**
- Command: `ff`
- Startup time: ~0.4s
- Uses source code directly
- Automatic conda environment activation

**How it works:**
Adds an alias to `~/.bashrc`:
```bash
alias ff='conda run -n flexflow_env --no-capture-output python /path/to/main.py'
```

### 2. User Install

**Best for:** Personal use, no sudo access

```bash
./install.sh
# Select Option 2: User Install
```

**Features:**
- Command: `flexflow`
- Installs to: `~/.local/bin`
- No sudo required
- Portable across shell sessions

**What gets installed:**
- Wrapper script in `~/.local/bin/flexflow`
- PATH automatically updated in `~/.bashrc`

### 3. System Install

**Best for:** Multi-user systems, system-wide availability

```bash
./install.sh
# Select Option 3: System Install
```

**Features:**
- Command: `flexflow`
- Installs to: `/usr/local/bin`
- Requires: sudo access
- Available to all users

**Note:** Each user needs their own `flexflow_env` conda environment.

### 4. Both (Alias + User/System)

**Best for:** Flexibility, development work

```bash
./install.sh
# Select Option 4: Both
```

**Features:**
- Commands: Both `ff` and `flexflow`
- Fast alias for daily use
- Wrapper for scripting and portability

## Step-by-Step Installation

### Interactive Installation

The installation script guides you through the process:

```bash
cd /path/to/flexflow_manager
./install.sh
```

**Installation steps:**

1. **Conda Detection**
   - Checks for Anaconda/Miniconda
   - Validates conda functionality
   - Prompts for installation if missing

2. **Environment Setup**
   - Creates `flexflow_env` with Python 3.12
   - Installs dependencies from `requirements.txt`
   - Configures PyTecplot if Tecplot is available

3. **Installation Type Selection**
   - Presents 4 installation options
   - Validates user choice
   - Explains each option

4. **Installation**
   - Creates aliases/wrapper scripts
   - Updates shell configuration
   - Sets up tab completion

5. **Verification**
   - Tests command availability
   - Verifies environment activation
   - Displays installation summary

### Non-Interactive Installation

For automated deployments:

```bash
# Use default settings (Fast Alias)
FLEXFLOW_INSTALL_TYPE=1 ./install.sh --non-interactive

# User install
FLEXFLOW_INSTALL_TYPE=2 ./install.sh --non-interactive

# System install (requires sudo)
FLEXFLOW_INSTALL_TYPE=3 sudo -E ./install.sh --non-interactive
```

## Installation Options

### Tab Completion

Enable shell completion during installation:

```bash
./install.sh
# Answer "yes" when prompted for tab completion
```

**Supports:**
- Bash
- Zsh
- Fish

**Features:**
- Command completion: `ff <TAB>`
- Subcommand completion: `ff case <TAB>`
- Option completion: `ff plot --data-type <TAB>`
- Path completion for file arguments

**Manual setup:**
```bash
# Bash
ff --completion bash >> ~/.bashrc
source ~/.bashrc

# Zsh
ff --completion zsh >> ~/.zshrc
source ~/.zshrc

# Fish
ff --completion fish > ~/.config/fish/completions/ff.fish
```

### Custom Environment Name

Edit configuration before installation:

```bash
# Edit config
vim install/config.sh

# Change environment name
CONDA_ENV_NAME="my_custom_env"

# Run installer
./install.sh
```

### Custom Python Version

```bash
# Edit config
vim install/config.sh

# Change Python version (must be compatible)
PYTHON_VERSION="3.11"

# Run installer
./install.sh
```

## Post-Installation

### Verify Installation

```bash
# Reload shell
source ~/.bashrc

# Check command availability
which ff
# or
which flexflow

# Verify version
ff --version

# Test basic functionality
ff --help
```

### First Run

```bash
# Test with help
ff --help

# View examples
ff --examples

# Test case command (if you have cases)
ff case show CS4SG1U1
```

### Configuration

**Environment variables** (optional):

Add to `~/.bashrc`:
```bash
# Default case directory
export FLEXFLOW_CASE_DIR=/path/to/cases

# Default output directory
export FLEXFLOW_OUTPUT_DIR=/path/to/output

# Tecplot installation (if non-standard)
export TECPLOT_360=/opt/tecplot/360ex_2023r1

# Enable debug logging
export FLEXFLOW_DEBUG=1
```

## Uninstallation

### Complete Removal

```bash
./install.sh --uninstall
```

**Removes:**
- Conda environment (`flexflow_env`)
- Aliases from `~/.bashrc`
- Wrapper scripts from `~/.local/bin` or `/usr/local/bin`
- Tab completion scripts

**Preserves:**
- Source code
- Configuration files
- Case directories
- Generated data

### Manual Uninstallation

If the uninstall script doesn't work:

```bash
# Remove conda environment
conda env remove -n flexflow_env

# Remove alias from ~/.bashrc
# Edit ~/.bashrc and remove the ff alias line

# Remove wrapper scripts
rm ~/.local/bin/flexflow
# or
sudo rm /usr/local/bin/flexflow

# Remove completions
rm ~/.local/share/bash-completion/completions/ff

# Reload shell
source ~/.bashrc
```

## Troubleshooting

### Conda Not Found

**Problem:** `conda: command not found`

**Solution:**
```bash
# Install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# Follow prompts, then reload shell
source ~/.bashrc

# Verify
which conda
```

### Command Not Found After Installation

**Problem:** `ff: command not found` or `flexflow: command not found`

**Solution:**
```bash
# Reload shell configuration
source ~/.bashrc

# Check if alias exists
alias | grep ff

# Check if wrapper exists
which flexflow
ls ~/.local/bin/flexflow

# Check PATH
echo $PATH | grep ~/.local/bin
```

### Environment Activation Fails

**Problem:** `conda: error: environment does not exist`

**Solution:**
```bash
# List environments
conda env list

# Recreate environment
conda create -n flexflow_env python=3.12 -y

# Install dependencies
conda activate flexflow_env
cd /path/to/flexflow_manager
pip install -r requirements.txt
```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'tecplot'`

**Solution:**
```bash
# Activate environment
conda activate flexflow_env

# Reinstall dependencies
pip install -r requirements.txt

# Check installation
pip list | grep pytecplot

# If Tecplot is not installed
pip install pytecplot
```

### Permission Denied

**Problem:** Permission errors during system install

**Solution:**
```bash
# Use sudo for system install
sudo ./install.sh

# Or use user install instead
./install.sh
# Select Option 2: User Install
```

### PyTecplot License Issues

**Problem:** PyTecplot fails with license error

**Solution:**
```bash
# Check Tecplot 360 installation
which tec360

# Set environment variable
export TECPLOT_360=/path/to/tecplot/360ex

# Add to ~/.bashrc for persistence
echo 'export TECPLOT_360=/path/to/tecplot/360ex' >> ~/.bashrc

# Restart shell
source ~/.bashrc
```

### Installation Script Errors

**Problem:** Syntax errors in installation script

**Solution:**
```bash
# Check script syntax
bash -n install.sh
bash -n install/*.sh

# Ensure line endings are correct (not Windows format)
dos2unix install.sh install/*.sh

# Make executable
chmod +x install.sh
```

## Advanced Configuration

### Multiple Installations

Install different versions side-by-side:

```bash
# First installation
cd flexflow_v1
./install.sh
# Use environment name: flexflow_env_v1

# Second installation
cd flexflow_v2
vim install/config.sh  # Change CONDA_ENV_NAME
./install.sh
```

### Development Installation

For development work:

```bash
# Use Fast Alias for quick testing
./install.sh
# Select Option 1

# Edit source code directly
vim src/cli/commands/case_cmd.py

# Changes take effect immediately (no reinstall needed)
ff case show CS4SG1U1
```

### Custom Wrapper Script

Create your own wrapper:

```bash
#!/bin/bash
# ~/bin/my_ff

# Custom environment variables
export FLEXFLOW_DEBUG=1
export FLEXFLOW_CASE_DIR=/my/cases

# Run FlexFlow
conda run -n flexflow_env --no-capture-output \
  python /path/to/flexflow_manager/main.py "$@"
```

Make executable:
```bash
chmod +x ~/bin/my_ff
export PATH="$HOME/bin:$PATH"
my_ff --help
```

### Migrating from Old Installation

If you have a previous installation:

```bash
# Uninstall old version
cd old_flexflow
./install.sh --uninstall

# Remove old environment (if different name)
conda env remove -n old_env_name

# Install new version
cd flexflow_manager
./install.sh
```

## Getting Help

If installation fails:

1. **Check prerequisites:** Ensure conda is installed and working
2. **Read error messages:** Installation script provides detailed errors
3. **Check logs:** Installation creates logs in `/tmp/flexflow_install.log`
4. **Review documentation:**
   - This guide
   - [INSTALL_QUICKREF.md](INSTALL_QUICKREF.md)
   - [docs/setup/INSTALL_INTERACTIVE.md](docs/setup/INSTALL_INTERACTIVE.md)

5. **Report issues:**
   - GitHub: https://github.com/arunperiyal/flexflow_analyzer/issues
   - Include: OS version, conda version, error messages, installation log

## Next Steps

After successful installation:

1. **Read the usage guide:** [docs/USAGE.md](docs/USAGE.md)
2. **Try examples:** `ff --examples`
3. **Explore commands:** `ff --help`
4. **Test with your data:** `ff case show YOUR_CASE`

## Summary

**Quick install:**
```bash
./install.sh && source ~/.bashrc && ff --version
```

**Recommended for most users:** Fast Alias (Option 1)

**Typical installation time:** 2 minutes

**Support:** https://github.com/arunperiyal/flexflow_analyzer/issues
