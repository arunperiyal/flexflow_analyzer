# FlexFlow Interactive Installer

## Quick Start

```bash
./install.sh
```

That's it! The installer will guide you through everything.

## What It Does

✅ Checks for Anaconda/Miniconda  
✅ Creates Python 3.12 environment (`tecplot312`)  
✅ Installs all dependencies (numpy, matplotlib, pytecplot, etc.)  
✅ Installs FlexFlow (4 options to choose from)  
✅ Sets up shell aliases  
✅ Configures tab completion (optional)  

## Installation Time

⏱️ **2-3 minutes**

## Installation Options

Choose during installation:

| Option | Command | Startup | Setup |
|--------|---------|---------|-------|
| **1. Fast Alias** | `ff` | 0.4s | alias |
| **2. User Install** | `flexflow` | 0.75s | ~/.local/bin |
| **3. System Install** | `flexflow` | 0.75s | /usr/local/bin |
| **4. Both** | `ff` + `flexflow` | 0.4s/0.75s | both |

**Recommended:** Option 1 (Fast Alias) for development

## After Installation

```bash
# Reload shell
source ~/.bashrc

# Test it
ff -v                    # Version info
ff case show CS4SG1U1   # Analyze a case
```

## Requirements

- Anaconda or Miniconda installed
- Bash shell
- ~500 MB disk space

## Full Documentation

See `docs/setup/INSTALL_INTERACTIVE.md` for complete guide.
