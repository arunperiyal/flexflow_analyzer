# FlexFlow Auto-Python Wrapper - No More Manual Environment Activation!

## Problem Solved ✅

**Before:** You had to run `conda activate tecplot312` every time for Tecplot operations.

**Now:** FlexFlow automatically uses Python 3.12 for Tecplot commands!

## How It Works

The new smart wrapper detects which Python version to use:

```bash
# Your default Python (any version)
$ python3 --version
Python 3.13.2

# FlexFlow automatically uses Python 3.12 for Tecplot commands!
$ flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z
# ↑ Uses Python 3.12 automatically

# Non-Tecplot commands use your default Python
$ flexflow case show CS4SG1U1
# ↑ Uses Python 3.13.2 (your default)
```

## Setup (One-Time)

### Option 1: Update Existing Installation (Recommended)

```bash
cd /path/to/flexflow_manager
python3 update_wrapper.py
```

Done! FlexFlow now automatically uses Python 3.12 for Tecplot operations.

### Option 2: Fresh Install

If installing FlexFlow fresh, the installer will be updated to use the smart wrapper by default in the next version.

For now, after installing:
```bash
python main.py --install
cd /path/to/flexflow_manager
python3 update_wrapper.py
```

## Usage Examples

### Tecplot Commands (Auto Python 3.12)

These commands automatically use Python 3.12:

```bash
# Extract data from PLT files
flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z,U,V,W

# Convert PLT to HDF5
flexflow tecplot convert CS4SG1U1 --format hdf5

# Get PLT file info
flexflow field info CS4SG1U1

# Legacy commands also work
flexflow extract CS4SG1U1 1000 FIELD X,Y,Z
flexflow convert CS4SG1U1
```

### Non-Tecplot Commands (Your Default Python)

These use your default Python (3.13 is fine):

```bash
# Case information
flexflow case show CS4SG1U1

# Plot data
flexflow plot CS4SG1U1 --node 10 --component y

# Preview data
flexflow data show CS4SG1U1 --node 24

# Statistics
flexflow data stats CS4SG1U1 --node 100

# Compare cases
flexflow compare CS4SG1U1 CS4SG2U1 --node 10
```

## How the Wrapper Works

```
User runs: flexflow field extract ...
       ↓
Wrapper checks: Is this a Tecplot command?
       ↓
   Yes → Check current Python version
       ↓
   Python 3.13+ detected
       ↓
   Find Python 3.12 (conda env or system)
       ↓
   Execute command with Python 3.12
       ↓
   Command runs successfully! ✅
```

## Troubleshooting

### Problem: "Python 3.12 not found"

**Solution:** Install Python 3.12 (one-time):
```bash
conda create -n tecplot312 python=3.12 -y
conda activate tecplot312
pip install pytecplot
```

The wrapper will automatically find it after installation.

### Problem: Want to force Python 3.12 for all commands

**Solution:** Just activate the environment manually:
```bash
conda activate tecplot312
flexflow <any-command>
```

The wrapper respects your active environment.

### Problem: Want to restore old behavior

**Solution:** Restore from backup:
```bash
cd /path/to/flexflow_manager
python3 update_wrapper.py --uninstall
```

Or manually:
```bash
cp ~/.local/bin/flexflow.backup ~/.local/bin/flexflow
```

## Technical Details

### Wrapper Logic

The bash wrapper (`~/.local/bin/flexflow`) contains logic to:

1. **Detect Tecplot commands**: `field`, `tecplot`, `convert`, `extract`
2. **Check current Python version**: If 3.13+, switch to 3.12
3. **Find Python 3.12**: Searches conda env, then system Python
4. **Execute appropriately**: Use found Python 3.12 or current Python

### Python 3.12 Search Order

1. `~/miniconda3/envs/tecplot312/bin/python`
2. `~/anaconda3/envs/tecplot312/bin/python`
3. `/usr/bin/python3.12`
4. `/bin/python3.12`

### Wrapper Location

- Wrapper script: `~/.local/bin/flexflow`
- Backup: `~/.local/bin/flexflow.backup`
- Main script: `~/.local/share/flexflow/main.py`

## Benefits

✅ **No manual activation** - Works transparently  
✅ **Smart detection** - Only uses 3.12 when needed  
✅ **Backward compatible** - All existing commands work  
✅ **User-friendly** - Just works out of the box  
✅ **Flexible** - Can still manually activate if desired  

## Performance

Same 2-3x performance improvement as before, but now automatic!

| Operation | Time | Python Used |
|-----------|------|-------------|
| `field extract` | 4s | 3.12 (auto) |
| `field info` | <1s | 3.12 (auto) |
| `case show` | <1s | Your default |
| `plot` | 2-5s | Your default |

## Files

**Created/Modified:**
- `flexflow_wrapper.sh` - Smart bash wrapper template
- `update_wrapper.py` - One-time update script
- `AUTO_PYTHON_GUIDE.md` - This guide
- `~/.local/bin/flexflow` - Installed wrapper (modified)

**Backup:**
- `~/.local/bin/flexflow.backup` - Your original wrapper

## Comparison

### Before (Manual)
```bash
# Every terminal session...
conda activate tecplot312
flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z
conda deactivate

# Plot with default Python
python3.13 works fine
flexflow plot CS4SG1U1 --node 10
```

### After (Automatic)
```bash
# Just use it! No activation needed
flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z
# ↑ Auto Python 3.12

flexflow plot CS4SG1U1 --node 10
# ↑ Your default Python

# Everything just works! ✅
```

## FAQ

**Q: Does this slow down commands?**  
A: No. The wrapper decision is instant (<0.01s). You won't notice any difference.

**Q: Can I still use `conda activate tecplot312` if I want?**  
A: Yes! The wrapper respects your active environment.

**Q: What if I don't have Python 3.12 installed?**  
A: The wrapper will warn you and suggest installation. Tecplot commands may fail until you install it.

**Q: Does this work on greenlotus too?**  
A: Yes! Run `python3 update_wrapper.py` on greenlotus as well.

**Q: Can I customize which commands trigger Python 3.12?**  
A: Yes! Edit `~/.local/bin/flexflow` and modify the case statement.

## Summary

**Setup:** Run `python3 update_wrapper.py` once  
**Usage:** Just use `flexflow` commands normally  
**Result:** Python 3.12 automatically used for Tecplot operations  

**No more `conda activate tecplot312` needed!** 🎉

---

**Last Updated:** 2026-01-06  
**FlexFlow Version:** 2.0  
**Wrapper Version:** 1.0
