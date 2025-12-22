# Tecplot Progress Output Troubleshooting

## Issue
User reports that `flexflow tecplot convert` shows no progress messages even though the macro file contains $!PRINT statements.

## Investigation

### 1. Macro File is Correct ✓
The generated macro contains all the progress messages:
```tcl
$!PRINT "Converting [1/3]: riser.50.plt -> riser.50.h5"
$!PRINT "Progress: 33%"
```

### 2. Possible Causes

#### A. Tecplot Output Buffering
Tecplot might buffer its output, preventing real-time display.

**Solution**: The code now:
- Uses `subprocess.Popen` instead of `subprocess.run`
- Streams output line-by-line
- Merges stderr into stdout
- Forces flush with `sys.stdout.flush()`

#### B. Tecplot Batch Mode Silent
Tecplot's `-b` (batch) flag might suppress $!PRINT output.

**Test**: Try running manually:
```bash
/usr/local/tecplot/360ex_2022r1/bin/tec360 -b -p CS4SG1U1/convert_plt.mcr
```

If no output appears, Tecplot batch mode might not display $!PRINT.

**Alternative Solutions**:
1. Use `-mesa` flag for offscreen rendering
2. Write progress to a log file
3. Use Python to monitor file creation

#### C. License Issues
If license is expired/invalid, Tecplot might fail silently.

**Check**: Look for "License Expired" in output

### 3. Current Implementation

```python
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,  # Merge streams
    text=True,
    bufsize=1,  # Line buffered
    universal_newlines=True
)

for line in iter(process.stdout.readline, ''):
    if line:
        print(line.rstrip())
        sys.stdout.flush()  # Force display
```

## Alternative Approaches

### Option 1: Monitor File Creation (Most Reliable)
Instead of relying on Tecplot output, monitor the output directory:

```python
import time
from pathlib import Path

def convert_with_monitoring(converter, ...):
    # Start conversion in background
    process = subprocess.Popen(...)
    
    # Monitor output directory
    output_dir = Path('CS4SG1U1/binary/converted')
    expected_files = len(plt_files)
    
    while process.poll() is None:  # While running
        existing = len(list(output_dir.glob('*.h5')))
        progress = (existing * 100) // expected_files
        print(f"\rConverted: {existing}/{expected_files} ({progress}%)", end='', flush=True)
        time.sleep(5)  # Check every 5 seconds
    
    print()  # New line after completion
```

### Option 2: Log File Approach
Write progress to a separate log file:

```tcl
# In macro
$!SYSTEM "echo 'Converting [1/3]' >> conversion.log"
$!ReadDataSet "file.plt"
$!WriteDataSet "file.h5"
$!SYSTEM "echo 'Completed [1/3]' >> conversion.log"
```

Python reads and displays the log:
```python
import threading

def tail_log(logfile):
    with open(logfile, 'r') as f:
        while True:
            line = f.readline()
            if line:
                print(line.rstrip())
            else:
                time.sleep(0.1)

# Start log monitor in thread
thread = threading.Thread(target=tail_log, args=('conversion.log',))
thread.daemon = True
thread.start()

# Run conversion
process.wait()
```

### Option 3: Use tec360-env wrapper
Try using the tec360-env script which might handle output differently:

```python
cmd = ['/usr/local/tecplot/360ex_2022r1/bin/tec360-env', 
       '--', 'tec360', '-b', '-p', macro_file]
```

### Option 4: Add Verbose Tecplot Flag
Check if Tecplot has verbose flags:
```bash
tec360 -b -v -p macro.mcr  # Try -v for verbose
tec360 -b -mesa -p macro.mcr  # Try -mesa
```

## Recommended Fix

**Short-term** (Current implementation):
- Code now streams output properly
- Should work if Tecplot outputs anything

**If still no output**:
Implement file monitoring (Option 1) as it's most reliable:

```python
def convert_with_file_monitoring(self, plt_files, output_format, output_dir, ...):
    # Start conversion
    process = subprocess.Popen([self.tec360_path, '-b', '-p', macro_file], ...)
    
    # Monitor progress by counting created files
    import time
    total = len(plt_files)
    last_count = 0
    
    while process.poll() is None:
        current_count = len(list(output_dir.glob(f'*.{ext}')))
        if current_count > last_count:
            progress = (current_count * 100) // total
            print(f"[{current_count}/{total}] Progress: {progress}% - {current_count} files converted")
            last_count = current_count
        time.sleep(2)  # Check every 2 seconds
    
    # Final check
    final_count = len(list(output_dir.glob(f'*.{ext}')))
    print(f"✓ Conversion complete: {final_count}/{total} files")
```

This approach:
- ✓ Doesn't depend on Tecplot output
- ✓ Works regardless of buffering
- ✓ Shows real progress
- ✓ More reliable

## Testing

To test which approach works:

1. **Test manual run**:
```bash
cd CS4SG1U1
/usr/local/tecplot/360ex_2022r1/bin/tec360 -b -p convert_plt.mcr
# Watch if any output appears
```

2. **Test with small files**:
```bash
flexflow tecplot convert CS4SG1U1 --start-step 50 --end-step 100 --verbose
# Should show progress for 2 files
```

3. **Monitor files manually**:
```bash
watch -n 1 'ls -lh CS4SG1U1/binary/converted/*.h5 2>/dev/null | wc -l'
# See files being created
```

## Next Steps

1. User should test current implementation
2. If no progress shows, implement file monitoring
3. Check Tecplot documentation for output options
