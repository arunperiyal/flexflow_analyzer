# FlexFlow Installation Scripts

This directory contains modular installation scripts for FlexFlow.

## Structure

```
install/
├── README.md          # This file
├── config.sh          # Configuration and constants
├── ui.sh              # User interface functions (print, ask, etc.)
├── conda.sh           # Conda environment management
├── installer.sh       # Installation methods (alias, user, system)
└── uninstaller.sh     # Uninstallation functions
```

## Modules

### config.sh
- Configuration variables and constants
- Environment names, paths, colors
- Exported variables used by all modules

### ui.sh
- User interface functions
- `print_header()`, `print_step()`, `print_info()`, etc.
- `ask_yes_no()` for user prompts
- `print_summary()` for installation summary

### conda.sh
- Conda environment management
- `check_conda()` - Detect and load conda
- `create_conda_env()` - Create flexflow_env
- `install_dependencies()` - Install Python packages
- `remove_conda_env()` - Remove environment during uninstall

### installer.sh
- Installation methods
- `choose_installation_type()` - Interactive selection
- `install_alias()` - Fast alias installation
- `install_wrapper()` - User/system wrapper installation
- `setup_completion()` - Shell completion setup
- `perform_installation()` - Execute chosen method

### uninstaller.sh
- Uninstallation functions
- `uninstall_flexflow()` - Remove all FlexFlow components
- Cleans up aliases, wrappers, completion, and environment

## Configuration

Edit `config.sh` to change:
- `CONDA_ENV_NAME` - Default: `flexflow_env`
- `PYTHON_VERSION` - Default: `3.12`
- Installation paths and directories

## Usage

These modules are sourced by the main `../install.sh` script. 
Do not run them directly.

## Adding New Features

1. Add new functions to appropriate module
2. Update `../install.sh` if needed
3. Document changes here
4. Test with `./install.sh --help` and full installation
