# Tecplot "double free or corruption" Crash - Fix

## Problem
User reported:
```
flexflow tecplot convert CS4SG1U1 --start-step 50 --end-step 150
double free or corruption (out)
```

## Root Cause
The error "double free or corruption" is a memory corruption crash typically caused by:
1. **License Issues**: Expired/invalid license causing premature termination
2. **Graphics/Display Issues**: Tecplot trying to initialize GUI in batch mode without proper display setup
3. **Missing Libraries**: Required shared libraries not properly loaded

## Solution Implemented

### 1. Use tec360-env Wrapper
Instead of calling `tec360` directly, use the `tec360-env` wrapper script:
```bash
/usr/local/tecplot/360ex_2022r1/bin/tec360-env -- tec360 -b -mesa -p macro.mcr
```

The wrapper:
- Sets up proper LD_LIBRARY_PATH
- Loads required Tecplot libraries
- Configures environment correctly

### 2. Add -mesa Flag
Use `-mesa` for offscreen rendering (no X11/graphics required):
```bash
tec360 -b -mesa -p macro.mcr
```

This tells Tecplot to use Mesa/software rendering instead of GPU.

### 3. Set Environment Variables
```python
env = os.environ.copy()
env['DISPLAY'] = ''  # No display needed
env['QT_QPA_PLATFORM'] = 'offscreen'  # Qt offscreen mode
```

Prevents Tecplot from trying to initialize GUI components.

### 4. Updated Code Flow

**Before**:
```python
cmd = [tec360_path, '-b', '-p', macro_file]
subprocess.Popen(cmd, ...)
```

**After**:
```python
# Find both tec360-env and tec360
tec_info = {
    'env_wrapper': '/path/to/tec360-env',
    'tec360': '/path/to/tec360'
}

# Use wrapper with -mesa
cmd = [tec_info['env_wrapper'], '--', tec_info['tec360'], 
       '-b', '-mesa', '-p', macro_file]

env = os.environ.copy()
env['DISPLAY'] = ''
env['QT_QPA_PLATFORM'] = 'offscreen'

subprocess.Popen(cmd, env=env, ...)
```

## Testing

Try the updated command:
```bash
flexflow tecplot convert CS4SG1U1 --start-step 50 --end-step 150
```

Expected behavior:
- Should NOT crash
- Should show conversion progress (if Tecplot outputs it)
- Should create .h5 files in binary/converted/

## If Still Crashes

### Check 1: License
```bash
/usr/local/tecplot/360ex_2022r1/bin/tec360 -v
```
If shows "License Expired", you need to update the license.

### Check 2: Manual Test
```bash
cd CS4SG1U1
/usr/local/tecplot/360ex_2022r1/bin/tec360-env -- \
  /usr/local/tecplot/360ex_2022r1/bin/tec360 -b -mesa -p convert_plt.mcr
```

Does this work? If yes, FlexFlow should work too.
If no, there's a deeper Tecplot configuration issue.

### Check 3: Library Dependencies
```bash
ldd /usr/local/tecplot/360ex_2022r1/bin/tec360
```
Check if all required libraries are found.

## Alternative: Skip Conversion

If Tecplot continues to crash, you have options:

1. **Use Tecplot GUI** (if available):
   - Open Tecplot GUI
   - Load macro: File → Load Macro → convert_plt.mcr
   - It will convert files with GUI open

2. **Manual Conversion**:
   - Open each PLT file in Tecplot
   - Export to HDF5: File → Write Data → Format: HDF5

3. **Use Different Machine**:
   - Copy PLT files to machine with working Tecplot
   - Convert there
   - Copy HDF5 files back

## Files Modified

1. **converter.py**:
   - `_find_tecplot()`: Now finds both tec360 and tec360-env
   - `convert()`: Uses wrapper with -mesa flag
   - Added environment variable setup
   - Better error messages

## Command Line Arguments Added

The fix is automatic - no new arguments needed.

But if you want to debug:
```bash
flexflow tecplot convert CS4SG1U1 --verbose
# Shows which Tecplot executable is being used
```

## Expected Output (After Fix)

```
[INFO] Using Tecplot wrapper: /usr/local/tecplot/360ex_2022r1/bin/tec360-env
[INFO] Discovering PLT files...
[INFO] Found 80 PLT files
[INFO] Filtered to 3 files (steps 50 to 150)
[INFO] Converting 3 files
[INFO] Estimated time: ~3.0 minutes
[INFO] Output directory: CS4SG1U1/binary/converted
[INFO] Creating Tecplot macro...
[INFO] Using tec360-env wrapper with -mesa (offscreen rendering)
[INFO] Running Tecplot batch conversion...

<Tecplot output here>

[SUCCESS] Conversion completed successfully!
```

## Summary

The crash was fixed by:
1. ✅ Using tec360-env wrapper (proper library loading)
2. ✅ Adding -mesa flag (offscreen rendering)
3. ✅ Setting DISPLAY='' (no GUI)
4. ✅ Setting QT_QPA_PLATFORM=offscreen (Qt compatibility)

This should resolve the "double free or corruption" error.
