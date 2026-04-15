# Time Parameters Documentation - Summary

## Issue Resolved

**Problem:** The `case create` command documentation didn't explain how to use the `time` section in YAML configuration files. Users couldn't find examples showing how to set `maxTimeSteps` and `initialTimeIncrement` values.

**Solution:** Created comprehensive documentation with template examples and implementation details.

## What Was Done

### 1. Updated Template Files

Three template files in `src/templates/` were updated to include the `time` section:

#### `example_case_config.yaml`
- Added `time:` section with `maxsteps` and `dt` parameters
- Added examples to batch case generation section
- Includes inline comments explaining what each parameter does

#### `example_case_single.yaml`
- Added `time:` section with detailed comments
- Clarifies that values update `timeSteppingControl{}` in .def file

#### `example_case_multi.yaml`
- Added `time:` section to all three example cases
- Shows how to use same or different time parameters across batch

### 2. Created Comprehensive Documentation

**File:** `CASE_CREATE_TIME_PARAMETERS.md`

Contains:
- **Overview** - What the feature does
- **The Replacement Process** - Step-by-step explanation
- **Parameter Mapping Table** - YAML keys to .def file parameters
  - `time.maxsteps` → `maxTimeSteps`
  - `time.dt` → `initialTimeIncrement`
- **Implementation Details** - Code references and mechanics
- **Usage Examples** - Single case, batch, and parameter sweeps
- **Other Parameters** - Additional time control parameters
- **Common Use Cases** - Practical scenarios with examples
- **Verification** - How to check that changes were applied

### 3. Updated README

Added to main README.md:
- Highlighted "Unix Piping" in features section
- Updated case management description to mention time parameters
- Added link to Case Creation documentation

## How It Works

### YAML to .def File Mapping

Users add a `time` section to their YAML configuration:

```yaml
time:
  maxsteps: 16000      # Maps to maxTimeSteps
  dt: 0.05             # Maps to initialTimeIncrement
```

When `case create` runs:
1. YAML file is parsed (lines 522-530 in create_impl/command.py)
2. Time parameters are extracted
3. Parameter names are mapped to .def file names
4. The `.def` file's `timeSteppingControl{}` block is updated
5. Original formatting and indentation are preserved

### Example Usage

**Single Case:**
```bash
flexflow case create --from-config case_config.yaml --ref-case ./reference
```

**Batch with Overrides:**
```yaml
cases:
  - name: Case005
    time:
      maxsteps: 16000
  - name: Case010
    time:
      maxsteps: 32000
```

## Files Changed

1. **src/templates/example_case_config.yaml** - Added time section
2. **src/templates/example_case_single.yaml** - Added time section
3. **src/templates/example_case_multi.yaml** - Added time section to all examples
4. **CASE_CREATE_TIME_PARAMETERS.md** - New comprehensive documentation
5. **README.md** - Updated features and documentation links

## Git Commits

1. **a1702bd** - `docs: Add time parameter documentation to case create templates`
   - 4 files changed
   - ~290 lines added
   - Added templates and documentation

2. **551ef73** - `docs: Highlight piping and time parameters in README`
   - Updated features section
   - Added documentation link

## Key Features of Documentation

✅ **Clear mapping** - YAML keys to .def file parameters  
✅ **Code references** - Specific line numbers in implementation  
✅ **Working examples** - Copy-paste ready configurations  
✅ **Use cases** - Real-world scenarios explained  
✅ **Verification** - How to check results  
✅ **Related features** - Links to help and examples  

## User Impact

**Before:**
- Templates didn't show `time` section at all
- Users had to read source code to find the feature
- No documentation of the mapping
- Parameter names weren't intuitive

**After:**
- Templates show the `time` section prominently
- Documentation explains the "why" and "how"
- Parameter mapping is clearly documented
- Examples are ready to use
- Verification instructions provided

## Help System Integration

The help system already documented this (in help_messages.py lines 129-131, 156-158, 164-165), but users couldn't discover it without looking at source code. Now it's surfaced in templates.

Users can access help with:
```bash
flexflow case create --help      # Shows basic help
flexflow case create --examples  # Shows detailed examples (includes time parameters)
```

## Documentation Quality

- **Completeness** - Covers all aspects of the feature
- **Clarity** - Uses plain language with clear examples
- **Accuracy** - References actual source code
- **Usability** - Templates ready to copy and modify
- **Discoverability** - Linked from README and templates
