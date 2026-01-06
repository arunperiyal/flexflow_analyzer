# FlexFlow Documentation Index

## Quick Start

**New Users:** Start here! 👇

1. **[Standalone Success](guides/STANDALONE_SUCCESS.md)** - Download and run (recommended)
2. **[Quick Reference](guides/PYTECPLOT_QUICKREF.md)** - Command cheatsheet
3. **[Project Status](../PROJECT_STATUS.md)** - Current state overview

## User Guides

### Getting Started
- **[Standalone Executable](guides/STANDALONE_SUCCESS.md)** - No Python needed! (Recommended)
- **[Auto-Wrapper Setup](guides/AUTO_PYTHON_GUIDE.md)** - Alternative method with auto Python 3.12
- **[PyTecplot Guide](guides/PYTECPLOT_GUIDE.md)** - Complete usage guide

### Quick Reference
- **[Command Quickref](guides/PYTECPLOT_QUICKREF.md)** - All commands at a glance

## Technical Documentation

### Implementation Details
- **[PyTecplot Migration](technical/PYTECPLOT_MIGRATION.md)** - How we implemented pytecplot
- **[PyTecplot Complete](technical/PYTECPLOT_COMPLETE.md)** - Technical summary
- **[Standalone Build](technical/STANDALONE_BUILD.md)** - How to build standalone executable

### Python Version Issues
- **[Python 3.13 Investigation](technical/PYTHON_3.13_INVESTIGATION.md)** - Root cause analysis
- **[Version Verification](technical/PYTHON_VERSION_VERIFICATION.md)** - Test results
- **[Tecplot Fix Summary](technical/tecplot_fix_summary.md)** - Original fix documentation

## Setup & Installation

### Installation Methods
- **[Install Guide](setup/INSTALL.md)** - Standard installation
- **[Update Guide](setup/UPDATE.md)** - Updating FlexFlow
- **[Uninstall Guide](setup/UNINSTALL.md)** - Removing FlexFlow

## Usage Documentation

### Commands & Features
- **[Usage Overview](USAGE.md)** - All features and commands
- **[Command Reference](usage/commands/)** - Detailed command documentation

### Module Documentation
- **[Core Module](usage/core/)** - Core functionality
- **[CLI Module](usage/cli/)** - Command-line interface
- **[Utils Module](usage/utils/)** - Utility functions

## Development

### For Contributors
- **[Autocompletion](AUTOCOMPLETION.md)** - Shell completion
- **[Development Docs](development/)** - Implementation details
  - Autocompletion implementation
  - Tecplot integration
  - Refactoring summaries
  - Session summaries

## Archive

### Historical Documents
- **[Complete Solution](archive/COMPLETE_SOLUTION.md)** - Original complete solution doc
- **[Final Checklist](archive/FINAL_CHECKLIST.md)** - Implementation checklist
- **[Modern Libraries](archive/MODERN_LIBRARIES.md)** - Library analysis
- **[Architecture Analysis](archive/OPTIMAL_ARCHITECTURE_ANALYSIS.md)** - Design decisions

## Root Documentation

### Essential Files
- **[README.md](../README.md)** - Main project readme
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history
- **[PROJECT_STATUS.md](../PROJECT_STATUS.md)** - Current project status

---

## Documentation Structure

```
docs/
├── guides/              # User-facing guides
│   ├── STANDALONE_SUCCESS.md
│   ├── PYTECPLOT_QUICKREF.md
│   ├── PYTECPLOT_GUIDE.md
│   └── AUTO_PYTHON_GUIDE.md
│
├── technical/           # Technical documentation
│   ├── PYTECPLOT_MIGRATION.md
│   ├── STANDALONE_BUILD.md
│   └── PYTHON_3.13_INVESTIGATION.md
│
├── setup/              # Installation & setup
│   ├── INSTALL.md
│   ├── UPDATE.md
│   └── UNINSTALL.md
│
├── usage/              # Usage & API docs
│   ├── commands/
│   ├── core/
│   └── utils/
│
├── development/        # Development docs
│   └── (implementation details)
│
└── archive/           # Historical documents
    └── (old docs)
```

## Recommended Reading Path

### For End Users:
1. Start with [Standalone Success](guides/STANDALONE_SUCCESS.md)
2. Check [Quick Reference](guides/PYTECPLOT_QUICKREF.md)
3. Read [Project Status](../PROJECT_STATUS.md) for overview

### For Developers:
1. Read [PyTecplot Migration](technical/PYTECPLOT_MIGRATION.md)
2. Check [Standalone Build](technical/STANDALONE_BUILD.md)
3. Review [Development Docs](development/)

### For Troubleshooting:
1. Check [Python 3.13 Investigation](technical/PYTHON_3.13_INVESTIGATION.md)
2. Read [Version Verification](technical/PYTHON_VERSION_VERIFICATION.md)
3. See [Tecplot Fix Summary](technical/tecplot_fix_summary.md)

---

**Last Updated:** 2026-01-06  
**FlexFlow Version:** 2.0 (Standalone)  
**Documentation Version:** 1.0
