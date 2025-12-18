# `info` Command

Display case information and preview timestep data.

## Usage

```bash
flexflow info <case_directory> [options]
```

## Description

The `info` command displays summary information about a FlexFlow case directory, including:
- Problem name from simflow.config
- Time increment from .def file
- Available data files (OTHD, OISD)
- Number of time steps
- Time range

With the `--preview` option, it displays the first 20 time steps with sample node data.

## Options

```
<case_directory>    Path to FlexFlow case directory (required)
--preview           Show first 20 time steps with sample data
-v, --verbose       Show detailed information
--examples          Show usage examples
-h, --help          Show help message
```

## Examples

### Basic Information

Display basic case information:
```bash
flexflow info CS4SG1U1
```

### Preview Mode

Preview first 20 timesteps with sample data:
```bash
flexflow info CS4SG1U1 --preview
```

### Verbose Output

Show detailed information:
```bash
flexflow info CS4SG1U1 --verbose
```

## Output Format

### Basic Info Output
```
FlexFlow Case Information
Case Directory: /path/to/CS4SG1U1
Problem Name: riser

OTHD Files: 7 file(s)
  Nodes: 49
  Timesteps: 4430
  Time Range: 0.050000 to 221.500000

OISD Files: 7 file(s)
  Timesteps: 4430
  Time Range: 0.050000 to 221.500000
```

### Preview Output
```
Data Preview (Steps 0 to 19):
Step     Time         Node 0 - dx     Node 0 - dy     Node 0 - dz    
-----------------------------------------------------------------
0        0.050000     0.000000e+00    0.000000e+00    0.000000e+00   
1        0.100000     0.000000e+00    0.000000e+00    0.000000e+00   
...
```

## Use Cases

1. **Quick verification** - Check if case data is loaded correctly
2. **Time range discovery** - Find the available time range for plotting
3. **Data validation** - Verify number of nodes and timesteps
4. **Preview data** - Quickly inspect sample displacement values

## See Also

- [plot command](../plot/README.md) - Create plots from case data
- [compare command](../compare/README.md) - Compare multiple cases
- [Main Usage Guide](../../USAGE.md)
