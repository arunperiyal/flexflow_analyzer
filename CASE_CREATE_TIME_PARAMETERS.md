# How `case create` Replaces `maxTimeSteps` from YAML

## Overview

When using `flexflow case create --from-config`, the `time` section in your YAML file allows you to set time stepping parameters that will be automatically updated in the `.def` file.

## The Replacement Process

### 1. YAML Configuration

In your case configuration YAML file, add a `time` section with time stepping parameters:

```yaml
case_name: myCase
problem_name: riser
processors: 80
output_frequency: 50

# Time stepping parameters for .def file
time:
  maxsteps: 16000      # Maps to maxTimeSteps in .def file
  dt: 0.05             # Maps to initialTimeIncrement in .def file
```

### 2. Parameter Mapping

The `case create` command maps YAML parameters to `.def` file parameters:

| YAML Key | .def File Parameter | Purpose |
|----------|-------------------|---------|
| `time.maxsteps` | `maxTimeSteps` | Total number of time steps for simulation |
| `time.dt` | `initialTimeIncrement` | Initial time increment (step size) |

### 3. Implementation Details

The replacement happens in `src/commands/case/create_impl/command.py`:

**Step 1: Extract time parameters from YAML** (lines 522-530)
```python
time_params = case_config.get('time', {})

# Map time parameters to .def file parameter names
# time.maxsteps -> maxTimeSteps, time.dt -> initialTimeIncrement
if time_params:
    if 'maxsteps' in time_params:
        def_params['maxTimeSteps'] = time_params['maxsteps']
    if 'dt' in time_params:
        def_params['initialTimeIncrement'] = time_params['dt']
```

**Step 2: Apply parameters to .def file** (function `_update_def_parameters`)
- Detects the `timeSteppingControl{}` block
- Updates matching parameter values using regex pattern matching
- Preserves original formatting and indentation

### 4. .def File Structure

The `.def` file has a `timeSteppingControl` block that looks like:

```
timeSteppingControl {
    maxTimeSteps          = 5000
    initialTimeIncrement  = 0.05
    order                 = 2
    highFrequencyDampingFactor = 0.1
}
```

When you run `case create` with time parameters, these values are updated.

## Usage Examples

### Single Case

```yaml
# case_config.yaml
case_name: TestCase001
problem_name: riser
processors: 80
output_frequency: 50

time:
  maxsteps: 16000
  dt: 0.05
```

Then run:
```bash
flexflow case create --from-config case_config.yaml --ref-case ./reference_case
```

Result: The created case's `.def` file will have:
```
timeSteppingControl {
    maxTimeSteps          = 16000
    initialTimeIncrement  = 0.05
    ...
}
```

### Batch Cases with Different Time Steps

```yaml
# batch_config.yaml
problem_name: riser
processors: 80

# Global time settings
time:
  maxsteps: 16000
  dt: 0.05

cases:
  - name: Case005_short
    output_frequency: 50
    time:
      maxsteps: 8000    # Override: shorter simulation
      dt: 0.05
  
  - name: Case010_long
    output_frequency: 100
    time:
      maxsteps: 32000   # Override: longer simulation
      dt: 0.05
  
  - name: Case015_default
    output_frequency: 75
    # Uses global time settings: 16000 steps, 0.05 dt
```

When both global and case-specific time settings exist, **case-specific values override global values**.

## Other Time Control Parameters

The `_update_def_parameters` function also supports other time control parameters:

```yaml
time:
  maxsteps: 16000
  dt: 0.05
  order: 2                        # Time stepping order
  highFrequencyDampingFactor: 0.1 # High frequency damping
```

All of these correspond to fields in the `timeSteppingControl{}` block of the `.def` file.

## What Gets Updated

### `.def` File
- Values in the `timeSteppingControl{}` block
- Formatting and indentation are preserved
- Only the values are changed, structure remains the same

### NOT Updated
- Other parts of the `.def` file (define{} blocks are updated via `def` section)
- The `.geo` file (uses `geo` section)
- The `.config` file (uses different mechanism)

## Template Files Updated

The following template files now show the `time` section:

1. **src/templates/example_case_config.yaml** - Default case config template
2. **src/templates/example_case_single.yaml** - Single case template
3. **src/templates/example_case_multi.yaml** - Batch case template

Each template includes examples of using the `time` section with clear comments.

## Common Use Cases

### Use Case 1: Parameter Sweep with Different Time Scales

```yaml
cases:
  - name: coarse_short
    time:
      maxsteps: 5000
      dt: 0.1
  
  - name: medium_standard
    time:
      maxsteps: 16000
      dt: 0.05
  
  - name: fine_long
    time:
      maxsteps: 32000
      dt: 0.025
```

### Use Case 2: Quick Test vs Production Run

```yaml
# Test configuration
case_name: test_run
time:
  maxsteps: 1000       # Quick test
  dt: 0.1

---

# Production configuration
case_name: production_run
time:
  maxsteps: 50000      # Full simulation
  dt: 0.01
```

### Use Case 3: Refinement Study

```yaml
cases:
  - name: study_dt0p1
    time:
      dt: 0.1
      maxsteps: 16000
  
  - name: study_dt0p05
    time:
      dt: 0.05
      maxsteps: 16000
  
  - name: study_dt0p01
    time:
      dt: 0.01
      maxsteps: 16000
```

## Global Defaults for Batch Cases

For batch case generation, you can define common parameters once at the root level instead of repeating them in every case. This greatly reduces YAML file size and improves maintainability.

### Global Defaults Syntax

```yaml
# These apply to all cases below
problem_name: riser
processors: 120
output_frequency: 50
time:
  maxsteps: 16000
  dt: 0.05

cases:
  - name: Case001
    geo:
      groove_depth: 0.03
    def:
      Ur: 4.0
    # Inherits: problem_name, processors, output_frequency, time
  
  - name: Case002
    processors: 60              # Override just this field
    time:
      maxsteps: 32000           # Override just maxsteps, inherits dt: 0.05
    geo:
      groove_depth: 0.05
    def:
      Ur: 5.0
```

### Merge Behavior

When both global and case-specific values exist:

1. **Simple fields** (problem_name, processors, output_frequency):
   - Case-specific value completely overrides global value
   - If case doesn't specify, global value is used

2. **Dict fields** (time, geo, def):
   - Individual parameters within the dict merge intelligently
   - Case-specific parameters override global parameters
   - Unspecified parameters inherit from global
   - Example: If global has `dt: 0.05` and case specifies `maxsteps: 32000`, case gets both values

### Benefits

- **50% reduction** in YAML file size for typical parametric studies
- **Easier maintenance** - change global value once, affects all cases
- **Clearer intent** - common pattern appears once, differences stand out
- **Less error-prone** - less repetition means less chance of typos

### Example: Before and After

**Without Global Defaults (60 lines):**
```yaml
cases:
  - name: Case1
    problem_name: riser
    processors: 120
    output_frequency: 50
    time:
      maxsteps: 16000
      dt: 0.05
    geo:
      groove_depth: 0.03
  
  - name: Case2
    problem_name: riser
    processors: 120
    output_frequency: 50
    time:
      maxsteps: 16000
      dt: 0.05
    geo:
      groove_depth: 0.05
```

**With Global Defaults (25 lines):**
```yaml
problem_name: riser
processors: 120
output_frequency: 50
time:
  maxsteps: 16000
  dt: 0.05

cases:
  - name: Case1
    geo:
      groove_depth: 0.03
  
  - name: Case2
    geo:
      groove_depth: 0.05
```

**Savings: 58% reduction!**

### Real-World Example

See `examples/case_multi_with_globals.yaml` for a complete working example showing:
- Global defaults setup
- Multiple cases with various overrides
- Time parameter overriding
- Detailed comments explaining each case

## Verification

To verify your time parameters were applied:

1. Create a case with `--dry-run` first:
   ```bash
   flexflow case create --from-config config.yaml --dry-run --verbose
   ```

2. Check the log output for time parameter confirmation

3. After creation, inspect the `.def` file:
   ```bash
   cat caseDir/problem.def | grep -A 5 "timeSteppingControl"
   ```

## Related Help

For more information:
```bash
flexflow case create --help
flexflow case create --examples
```

To see examples in the help system:
```
flexflow case create --examples
# Look for "Example 5" and "Example 9" which show time parameter usage
```
