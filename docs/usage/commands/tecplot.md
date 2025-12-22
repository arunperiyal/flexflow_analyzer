# FlexFlow Tecplot Command

Work with Tecplot PLT binary files - view information and extract data.

## Overview

The `tecplot` command provides tools for working with Tecplot binary files (.plt) generated during FlexFlow simulations. These files contain spatial field data (velocity, pressure, etc.) at specific time steps. The command supports inspecting file metadata and extracting data to CSV format.

## Usage

```bash
flexflow tecplot <subcommand> [options]
```

## Subcommands

### `info` - Inspect PLT Files

Display comprehensive information about PLT files in a case directory, including consistency checks and data structure details.

```bash
flexflow tecplot info <case_dir> [options]
```

#### Options

**Section Filters (combine multiple):**
```
--basic             Show only basic file information
--variables         Show only variable information
--zones             Show only zone information
--checks            Show only consistency checks
--stats             Show only data statistics
```

Note: If no section filter is specified, all sections are shown.

**Additional Options:**
```
--detailed          Show detailed statistics for all variables
--sample-file STEP  Analyze specific timestep file (default: first)
--verbose, -v       Show verbose output including errors
--help, -h          Show help message
```

#### Information Displayed

**Basic Information:**
- Total number of PLT files
- Timestep range (first to last)
- File sizes and statistics
- Definition file status

**Variables:**
- List of all variables in PLT files
- Variable count
- Variable categories (coordinates, velocities, etc.)

**Zones:**
- Zone names and types
- Zone dimensions (ORDERED, FELINESEG, etc.)
- Node/element information

**Consistency Checks:**
- ✓ Zero-size file detection
- ✓ Naming convention validation
- ✓ Sequential timestep verification
- ✓ File corruption detection (basic header check)
- ✓ Variable consistency across files

**Statistics:**
- File size statistics (min/max/average/median)
- Timestep increment statistics
- Storage estimates

#### Examples

**Show all information:**
```bash
flexflow tecplot info CS4SG1U1
```

**Show only variables:**
```bash
flexflow tecplot info CS4SG1U1 --variables
```

**Show consistency checks:**
```bash
flexflow tecplot info CS4SG1U1 --checks
```

**Combine filters:**
```bash
flexflow tecplot info CS4SG1U1 --variables --checks --zones
```

**Show detailed statistics:**
```bash
flexflow tecplot info CS4SG1U1 --stats --detailed
```

### `extract` - Extract Data from PLT Files

Extract data from Tecplot PLT binary files to CSV format using pytecplot.

```bash
flexflow tecplot extract <case_dir> [options]
```

#### Required Options

```
--variables VAR1,VAR2  Comma-separated list of variables to extract (e.g., Y, X,Y,Z, U,V,W)
--zone ZONE            Zone name to extract from (e.g., FIELD, BODY)
--timestep STEP        Timestep number to extract (e.g., 1000, 2000)
```

#### Optional Arguments

```
--output-file FILE     Output CSV file path (default: case/extracted_STEP.csv)
--verbose, -v          Show detailed extraction progress
--help, -h             Show help message
```

#### Examples

**Extract single variable:**
```bash
flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD
```

**Extract multiple variables:**
```bash
flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables X,Y,Z,U,V,W --zone FIELD
```

**Extract with custom output file:**
```bash
flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD --output-file results.csv
```

**Extract with verbose output:**
```bash
flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD -v
```

## PLT File Structure

FlexFlow cases contain PLT files in the `binary/` subdirectory:

```
CS4SG1U1/
├── simflow.config
├── riser.def
├── binary/
│   ├── riser.100.plt
│   ├── riser.200.plt
│   ├── riser.300.plt
│   └── ...
├── othd_files/
└── oisd_files/
```

### File Naming Convention

PLT files follow the pattern: `<problem>.<timestep>.plt`
- `problem`: Defined in `simflow.config`
- `timestep`: Integer timestep number (100, 200, 300, etc.)

### File Contents

Each PLT file typically contains:
- **Zones**: Spatial mesh data
- **Variables**: Field quantities (velocity, pressure, density, etc.)
- **Node/Element Data**: Mesh coordinates and connectivity
- **Solution Time**: Simulation time for the snapshot

## Requirements

The `tecplot extract` command uses the `pytecplot` library to read Tecplot binary files. This requires:
- Tecplot 360 installation
- `pytecplot` Python package

The `tecplot info` command can parse basic PLT file structure without pytecplot.

## Common Use Cases

### Check Data Availability

Before starting analysis, verify what variables and zones are available:
```bash
flexflow tecplot info CS4SG1U1 --variables --zones
```

### Validate Simulation Integrity

Check for missing timesteps or corrupted files:
```bash
flexflow tecplot info CS4SG1U1 --checks
```

### Extract Specific Data

Extract variables from a specific zone and timestep:
```bash
flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y,U,V --zone FIELD
```

### Typical Workflow

1. First, discover available variables and zones:
```bash
flexflow tecplot info CS4SG1U1 --variables --zones
```

2. Then extract the data you need:
```bash
flexflow tecplot extract CS4SG1U1 --timestep 1000 --variables Y --zone FIELD
```

## Troubleshooting

### No PLT Files Found

**Problem:** Command reports no PLT files in the directory.

**Solutions:**
- Verify the case directory path is correct
- Check that `binary/` subdirectory exists
- Ensure PLT files were generated during simulation

### File Corruption Detected

**Problem:** Consistency checks report corrupted files.

**Solutions:**
- Re-run the simulation to regenerate files
- Check disk space during simulation
- Verify file permissions

### Missing Variables

**Problem:** Expected variables not present in PLT files.

**Solutions:**
- Check FlexFlow simulation output configuration
- Verify the correct output variables were specified
- Ensure simulation completed successfully

### Extraction Fails

**Problem:** Extract command fails or produces no output.

**Solutions:**
- Ensure pytecplot is installed: `pip install pytecplot`
- Check that Tecplot 360 is installed
- Verify the zone name matches exactly (case-sensitive)
- Use `info` command to verify available zones and variables

## See Also

- [plot command](./plot.md) - Plot time-series data from OTHD/OISD files
- [compare command](./compare.md) - Compare multiple cases
- [info command](./info.md) - Display case information

## Additional Resources

For more information on Tecplot file formats and `pytecplot`:
- Tecplot 360 User's Manual
- PyTecplot Documentation: https://www.tecplot.com/docs/pytecplot/
