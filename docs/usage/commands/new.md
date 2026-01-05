# FlexFlow `new` Command

Create a new FlexFlow case directory from a reference template with automatic configuration.

## Overview

The `new` command streamlines the process of creating new FlexFlow simulation cases by copying files from a reference case template and automatically updating configuration files, SLURM scripts, and parametric values.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Command-Line Options](#command-line-options)
- [YAML Configuration](#yaml-configuration)
- [Parametric Substitution](#parametric-substitution)
- [Examples](#examples)
- [Reference Case Structure](#reference-case-structure)

## Basic Usage

```bash
# Create a new case using default reference directory (./refCase)
flexflow new myCase

# Create a new case with specific reference directory
flexflow new myCase --ref-case /path/to/refCase

# Create a new case with custom problem name
flexflow new myCase --problem-name cylinder

# Create a new case with custom processors and output frequency
flexflow new myCase --np 64 --freq 100

# Create case from YAML configuration
flexflow new --from-config case_config.yaml

# List available variables in reference case
flexflow new --list-vars --ref-case ./refCase

# Preview changes without creating files (dry-run)
flexflow new myCase --dry-run
```

## Command-Line Options

### Required Arguments

- **`case_name`** - Name of the new case directory to create (not required when using `--from-config`)

### Optional Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--ref-case PATH` | Path to reference case directory | `./refCase` |
| `--problem-name NAME` | Override problem name in simflow.config | From reference |
| `--np NUM` | Number of processors | `36` |
| `--freq NUM` | Output frequency | `50` |
| `--from-config FILE` | Load configuration from YAML file | - |
| `--force` | Overwrite existing directory if it exists | `false` |
| `--list-vars` | List available variables in reference case | `false` |
| `--dry-run` | Preview changes without creating files | `false` |
| `-v, --verbose` | Enable verbose output | `false` |
| `-h, --help` | Show help message | - |
| `--examples` | Show usage examples | - |

## What Gets Updated Automatically

When you create a new case, the command automatically:

1. **Copies mandatory files** from reference case:
   - `simflow.config`
   - `<problem>.geo`
   - `<problem>.def`
   - `preFlex.sh`
   - `mainFlex.sh`
   - `postFlex.sh`

2. **Updates SLURM job names** in shell scripts:
   - `preFlex.sh`: `#SBATCH -J <casename>_pre`
   - `mainFlex.sh`: `#SBATCH -J <casename>_main`
   - `postFlex.sh`: `#SBATCH -J <casename>_post`

3. **Updates simflow.config**:
   - `problem` - Problem name (if `--problem-name` specified)
   - `np` - Number of processors (from `--np`)
   - `nsg` - Number of subgroups (same as `np`)
   - `outFreq` - Output frequency (from `--freq`)

4. **Updates mainFlex.sh**:
   - `#SBATCH -n` - Number of processors (from `--np`)

5. **Updates postFlex.sh**:
   - `PROBLEM` - Problem name
   - `OUTFREQ` - Output frequency (from `--freq`)

6. **Renames files** (if problem name changed):
   - `<old_problem>.geo` → `<new_problem>.geo`
   - `<old_problem>.def` → `<new_problem>.def`

## YAML Configuration

### Single Case Configuration

Create a YAML file (e.g., `case_config.yaml`):

```yaml
case_name: CS4SG3U1
problem_name: riser
processors: 80
output_frequency: 75

# Geometry parameters (for .geo file)
geo:
  groove_depth: 0.06
  groove_width: 0.12
  cylinder_diameter: 0.5

# Flow parameters (for .def file)
def:
  Ur: 5.8
  Re: 15000
  dt: 0.001
```

Run:
```bash
flexflow new --from-config case_config.yaml
```

### Batch Case Configuration

Create a YAML file with multiple cases (e.g., `batch_cases.yaml`):

```yaml
cases:
  - case_name: CS4SG1U1
    processors: 64
    output_frequency: 50
    geo:
      groove_depth: 0.04
    def:
      Ur: 4.5
  
  - case_name: CS4SG2U1
    processors: 80
    output_frequency: 75
    geo:
      groove_depth: 0.06
    def:
      Ur: 5.8
  
  - case_name: CS4SG3U1
    processors: 120
    output_frequency: 100
    geo:
      groove_depth: 0.08
    def:
      Ur: 7.2
```

Run:
```bash
flexflow new --from-config batch_cases.yaml
```

This creates all three cases automatically with their respective parameters.

### Overriding YAML Values

Command-line flags override YAML values:

```bash
# Override processors and frequency from YAML
flexflow new --from-config case_config.yaml --np 120 --freq 100
```

## Parametric Substitution

### Geometry Parameters (.geo files)

Use `#parameter_name` placeholders in your reference `.geo` file:

```
// In reference riser.geo file
cylinder {
  diameter = #cylinder_diameter
  height = 10.0
}

groove {
  depth = #groove_depth
  width = #groove_width
}
```

These placeholders are replaced with values from the YAML `geo:` section.

### Flow Parameters (.def files)

Define variables in `define{}` blocks in your `.def` file:

```
define {
  variable = Ur
  value    = 5.0
}

define {
  variable = Re
  value    = 10000
}

define {
  variable = dt
  value    = 0.001
}
```

These are updated with values from the YAML `def:` section.

### Listing Available Variables

To see what parameters are available in your reference case:

```bash
flexflow new --list-vars --ref-case ./refCase
```

Output:
```
Reference Case Variables:
  Problem name: riser

.geo file placeholders:
  #cylinder_diameter
  #groove_depth
  #groove_width

.def file variables:
  Ur                   = 5.0
  Re                   = 10000
  dt                   = 0.001
```

## Examples

### Example 1: Basic Case Creation

```bash
flexflow new myCase
```

Creates `myCase/` with default settings (36 processors, frequency 50).

### Example 2: Custom Configuration

```bash
flexflow new experiment_1 --problem-name exp1 --np 80 --freq 75
```

Creates `experiment_1/` with:
- Problem name: `exp1`
- 80 processors
- Output frequency: 75

### Example 3: Parametric Study

Create `parametric_study.yaml`:

```yaml
cases:
  - case_name: Ur_4_5
    geo:
      groove_depth: 0.04
    def:
      Ur: 4.5
  
  - case_name: Ur_5_8
    geo:
      groove_depth: 0.06
    def:
      Ur: 5.8
  
  - case_name: Ur_7_2
    geo:
      groove_depth: 0.08
    def:
      Ur: 7.2
```

```bash
flexflow new --from-config parametric_study.yaml --verbose
```

Creates three cases with different Ur values and groove depths.

### Example 4: Dry-Run Preview

Preview changes without creating files:

```bash
flexflow new testCase --problem-name test --np 64 --dry-run
```

Shows what would be created and updated without actually making changes.

### Example 5: Force Overwrite

Replace existing case directory:

```bash
flexflow new myCase --force
```

Removes existing `myCase/` directory and creates a new one.

### Example 6: Custom Reference Case

```bash
flexflow new myCase --ref-case /path/to/custom/template --verbose
```

Uses a custom reference directory instead of `./refCase`.

## Reference Case Structure

Your reference case directory must contain these mandatory files:

```
refCase/
├── simflow.config        # Configuration file (must contain 'problem = <name>')
├── <problem>.geo         # Geometry file
├── <problem>.def         # Definition file (time parameters, variables)
├── preFlex.sh           # Pre-processing SLURM script
├── mainFlex.sh          # Main simulation SLURM script
└── postFlex.sh          # Post-processing SLURM script
```

Where `<problem>` is the problem name specified in `simflow.config`.

### Example simflow.config

```
problem = riser
np      = 36
nsg     = 36
outFreq = 50
```

### Example Shell Scripts

All three shell scripts should contain SLURM directives:

```bash
#!/bin/bash
#SBATCH -J riser_main
#SBATCH -n 36
#SBATCH -t 24:00:00
# ... rest of script
```

## Tips and Best Practices

1. **Use meaningful case names**: `CS4SG2U1` is better than `case1`
2. **Keep a clean reference case**: Test your reference case thoroughly before using it as a template
3. **Use YAML for batch studies**: Create multiple cases with consistent structure
4. **Use dry-run first**: Preview changes with `--dry-run` before creating
5. **List variables**: Use `--list-vars` to see available parameters before configuring
6. **Version control**: Keep your YAML configuration files in version control
7. **Document parameters**: Add comments in YAML files explaining parameter choices

## Troubleshooting

### "Reference case directory does not exist"

Ensure your reference case path is correct:
```bash
flexflow new myCase --ref-case /full/path/to/refCase
```

### "Missing mandatory files in reference case"

Check that all required files exist in reference case:
```bash
ls refCase/
# Should show: simflow.config, *.geo, *.def, *.sh files
```

### "Target directory already exists"

Use `--force` to overwrite:
```bash
flexflow new myCase --force
```

Or remove the directory manually:
```bash
rm -rf myCase
flexflow new myCase
```

### "Unassigned .geo placeholders"

The command warns about placeholders in `.geo` files that weren't given values. This is informational - the placeholders remain as `#variable_name` in the output file.

To fix, add the missing parameters to your YAML `geo:` section or remove unused placeholders from the reference `.geo` file.

## See Also

- [info command](info.md) - Display case information
- [plot command](plot.md) - Plot case data
- [compare command](compare.md) - Compare multiple cases
- [template command](template.md) - Generate YAML templates
