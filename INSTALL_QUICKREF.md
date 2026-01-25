# FlexFlow Installation Quick Reference

## Installation Structure

```
flexflow_manager/
├── install.sh              # Main installer (orchestrator)
├── install/                # Modular installation scripts
│   ├── config.sh          # Configuration (CONDA_ENV_NAME=flexflow_env)
│   ├── ui.sh              # User interface functions
│   ├── conda.sh           # Conda environment management
│   ├── installer.sh       # Installation methods
│   └── uninstaller.sh     # Uninstallation functions
├── src/                    # Source code (renamed from flexflow/)
├── main.py                 # Entry point
└── requirements.txt        # Python dependencies
```

## Quick Commands

```bash
# Install
./install.sh

# Uninstall
./install.sh --uninstall

# Help
./install.sh --help

# Test after install
ff --version
ff case show CS4SG1U1
```

## Configuration

Edit `install/config.sh` to customize:
- `CONDA_ENV_NAME="flexflow_env"` - Environment name
- `PYTHON_VERSION="3.12"` - Python version
- Installation paths

## Installation Options

1. **Fast Alias** (recommended)
   - Command: `ff`
   - Startup: 0.4s
   - Uses source directly

2. **User Install**
   - Command: `flexflow`
   - Location: `~/.local/bin`
   - No sudo required

3. **System Install**
   - Command: `flexflow`
   - Location: `/usr/local/bin`
   - Requires sudo

4. **Both**
   - Both `ff` and `flexflow` available

## Module Functions

### config.sh
- Exports: `CONDA_ENV_NAME`, `PYTHON_VERSION`, paths, colors

### ui.sh
- `print_header()`, `print_step()`, `print_info()`
- `print_success()`, `print_warning()`, `print_error()`
- `ask_yes_no()`, `print_summary()`

### conda.sh
- `check_conda()` - Detect conda
- `create_conda_env()` - Create environment
- `install_dependencies()` - Install packages
- `remove_conda_env()` - Cleanup

### installer.sh
- `choose_installation_type()` - User selection
- `install_alias()` - Fast alias setup
- `install_wrapper()` - Wrapper script
- `setup_completion()` - Shell completion
- `perform_installation()` - Execute

### uninstaller.sh
- `uninstall_flexflow()` - Complete removal

## Migration Notes

### Old Environment Users
If you have `tecplot312`:
```bash
# Uninstall old
./install.sh --uninstall

# Remove old environment
conda env remove -n tecplot312

# Reinstall with new environment
./install.sh
```

### Import Changes (Internal)
- Old: `from flexflow.cli import ...`
- New: `from src.cli import ...`

## Troubleshooting

### Module not found
Ensure you're in project root and run:
```bash
python3 -c "import sys; sys.path.insert(0, '.'); from src.cli.registry import registry; print('OK')"
```

### Conda not found
Install Miniconda:
```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

### Install script errors
Check syntax:
```bash
bash -n install.sh
bash -n install/*.sh
```

## For Developers

### Adding New Installation Method
1. Add function to `install/installer.sh`
2. Update `choose_installation_type()`
3. Update `perform_installation()`
4. Test with `./install.sh`

### Changing Configuration
Edit `install/config.sh` and reinstall

### Testing Modules
```bash
# Test individual module
source install/config.sh
source install/ui.sh
print_success "Test"
```

## Support

- Documentation: `docs/INDEX.md`
- Installation Guide: `INSTALL.md`
- Refactoring Summary: `REFACTOR_SUMMARY.md`
