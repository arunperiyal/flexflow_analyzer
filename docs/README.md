# FlexFlow Documentation

Comprehensive documentation for the FlexFlow post-processing toolkit.

## Quick Links

- **[Main README](../README.md)** - Project overview and quick start
- **[CHANGELOG](../CHANGELOG.md)** - Version history and changes
- **[Usage Guide](USAGE.md)** - Detailed usage instructions
- **[Autocompletion Guide](AUTOCOMPLETION.md)** - Shell tab completion setup

## Documentation Structure

### Setup Guides
- **[Installation](setup/INSTALL.md)** - Complete installation guide
- **[Update](setup/UPDATE.md)** - How to update FlexFlow
- **[Uninstallation](setup/UNINSTALL.md)** - How to remove FlexFlow

### Command References
- **[info command](usage/commands/info.md)** - Display case information
- **[plot command](usage/commands/plot.md)** - Create plots from single cases
- **[compare command](usage/commands/compare.md)** - Compare multiple cases
- **[template command](usage/commands/template.md)** - Generate YAML templates

### User Guides
- **[Usage Guide](usage/README.md)** - General usage patterns
- **[Autocompletion](AUTOCOMPLETION.md)** - Tab completion for bash/zsh/fish
- **[Quick Start](../COMPLETION_QUICKSTART.md)** - Autocompletion quick reference

### Developer Documentation
- **[Autocompletion Implementation](development/AUTOCOMPLETION_IMPLEMENTATION.md)** - Technical details
- **[Autocompletion Summary](development/AUTOCOMPLETION_SUMMARY.md)** - Feature summary
- **[Refactoring Summary](development/REFACTORING_SUMMARY.md)** - Code reorganization notes
- **[Permission Fix](development/PERMISSION_FIX.md)** - Installation permission handling

## Key Features by Version

### Version 2.2.0 (Current)
- **Separate Plots Mode** - Generate individual files for each case
- **Enhanced Time Range** - Proper tsId (time step ID) support
- **Output Format Control** - PNG, PDF, SVG support
- **Improved YAML Support** - Better configuration handling

### Version 2.1.0
- **Shell Autocompletion** - Tab completion for bash, zsh, fish
- **Context-Aware Completion** - Smart suggestions based on command
- **Dynamic Directory Completion** - Automatic case directory discovery

### Version 2.0.0
- **Modular Architecture** - Clean code organization
- **Git-Style CLI** - Subcommand structure (info, plot, compare, etc.)
- **YAML Configuration** - Batch processing support
- **Template System** - Easy configuration generation

## Getting Help

### Command-Line Help
```bash
# General help
flexflow --help

# Command-specific help
flexflow plot --help
flexflow compare --help

# Show examples
flexflow plot --examples
flexflow compare --examples
```

### Interactive Documentation
```bash
# View documentation in browser
flexflow docs

# View specific topics
flexflow docs plot
flexflow docs compare
```

## Common Workflows

### Quick Analysis
```bash
# View case info
flexflow info CS4SG2U1

# Create a quick plot
flexflow plot CS4SG2U1 --data-type displacement --node 10 --component y
```

### Comparison Study
```bash
# Generate template
flexflow template multi --output comparison.yaml

# Edit comparison.yaml, then:
flexflow compare --input-file comparison.yaml
```

### Batch Processing
```bash
# Generate separate plots for multiple cases
flexflow compare CS4SG1U1 CS4SG2U1 CS4SG3U1 \
    --data-type displacement --node 10 --component y \
    --separate --output-prefix result_ --output-format pdf
```

## Support and Contribution

For issues, suggestions, or contributions, please refer to the project repository.

## License

See the main README for license information.
