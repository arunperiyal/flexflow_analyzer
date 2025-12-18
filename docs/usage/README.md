# FlexFlow Command Usage Documentation

This directory contains detailed documentation for each FlexFlow command.

## Available Commands

### [info](./info/README.md)
Display case information and preview timestep data.

```bash
flexflow info <case_directory> [options]
```

### [plot](./plot/README.md)
Create plots from a single FlexFlow case with various plot types and customization options.

```bash
flexflow plot <case_directory> [options]
```

### [compare](./compare/README.md)
Compare multiple cases on a single plot using YAML configuration.

```bash
flexflow compare <config.yaml> [options]
```

### [template](./template/README.md)
Generate template YAML configuration files for plotting and comparison.

```bash
flexflow template [options]
```

## Quick Links

- [Main Usage Guide](../USAGE.md) - Complete documentation with all commands
- [Installation Guide](../USAGE.md#installation)
- [Quick Start](../USAGE.md#quick-start)
- [YAML Configuration](../USAGE.md#yaml-configuration)
- [Examples](../USAGE.md#examples)

## Getting Help

For command-specific help, run:
```bash
flexflow <command> --help
flexflow <command> --examples
```

For general help:
```bash
flexflow --help
```
