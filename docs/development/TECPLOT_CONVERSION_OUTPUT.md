# Tecplot Conversion - Expected Output

## Example Conversion Session

### Command
```bash
$ flexflow tecplot convert CS4SG1U1 --format hdf5 --start-step 50 --end-step 150
```

### Expected Output

```
[INFO] Using Tecplot: /usr/local/tecplot/360ex_2022r1/bin/tec360
[INFO] Discovering PLT files...
[INFO] Found 80 PLT files
[INFO] Filtered to 3 files (steps 50 to 150)
[INFO] Converting 3 files
[INFO] Estimated time: ~3.0 minutes
[INFO] Output directory: CS4SG1U1/binary/converted
[INFO] Creating Tecplot macro...
[INFO] Created conversion macro: CS4SG1U1/convert_plt.mcr
[INFO] Running Tecplot batch conversion...
[INFO] This may take several minutes depending on file size...
```

### Tecplot Batch Output (from macro)

```
=
FlexFlow PLT to HDF5 Conversion
Total files: 3
Output directory: CS4SG1U1/binary/converted
=
 
Converting [1/3]: riser.50.plt -> riser.50.h5
Progress: 33%
✓ Completed: riser.50.h5
 
Converting [2/3]: riser.100.plt -> riser.100.h5
Progress: 66%
✓ Completed: riser.100.h5
 
Converting [3/3]: riser.150.plt -> riser.150.h5
Progress: 100%
✓ Completed: riser.150.h5
 
=
✓ Conversion Complete!
Total files converted: 3
Output location: CS4SG1U1/binary/converted
Format: HDF5
 
Files can now be read with:
  flexflow tecplot read <case> --timestep <N>
=
```

### FlexFlow Final Messages

```
[SUCCESS] Conversion completed successfully!
[INFO] Created 3 converted files
[INFO] Files saved to: CS4SG1U1/binary/converted
```

## Progress Tracking Features

### 1. File Counter
Shows current file being processed:
```
Converting [1/3]: riser.50.plt -> riser.50.h5
Converting [2/3]: riser.100.plt -> riser.100.h5
Converting [3/3]: riser.150.plt -> riser.150.h5
```

### 2. Progress Percentage
Displays completion percentage:
```
Progress: 33%
Progress: 66%
Progress: 100%
```

### 3. Completion Status
Confirms each file is successfully converted:
```
✓ Completed: riser.50.h5
✓ Completed: riser.100.h5
✓ Completed: riser.150.h5
```

### 4. Time Estimation
Before conversion starts:
```
[INFO] Converting 80 files
[INFO] Estimated time: ~80.0 minutes
```

### 5. Summary at End
Final statistics:
```
✓ Conversion Complete!
Total files converted: 80
Output location: CS4SG1U1/binary/converted
Format: HDF5
```

## Conversion with Different Options

### Keep Original Files
```bash
$ flexflow tecplot convert CS4SG1U1 --keep-original
```
Output includes:
```
[INFO] Original PLT files will be kept
```

### VTK Format
```bash
$ flexflow tecplot convert CS4SG1U1 --format vtk
```
Output shows:
```
FlexFlow PLT to VTK Conversion
...
Format: VTK
```

### Full Case (All Timesteps)
```bash
$ flexflow tecplot convert CS4SG1U1
```
Output:
```
[INFO] Found 80 PLT files
[INFO] Converting 80 files
[INFO] Estimated time: ~80.0 minutes
```

## Error Messages

### Tecplot Not Found
```
[ERROR] Tecplot 360 not found. Please install Tecplot or set TEC360HOME environment variable.
Example: export TEC360HOME=/usr/local/tecplot/360ex_2022r1
```

### No PLT Files
```
[ERROR] No PLT files found in CS4SG1U1/binary
```

### Conversion Failed
```
[ERROR] Tecplot conversion failed
[ERROR] Error output: <error details>
```

### License Expired
```
[ERROR] License Expired
```

## Tips for Long Conversions

### Monitor Progress
Tecplot will continuously output progress messages, so you can track:
- Which file is currently being processed
- How many files remain
- Overall progress percentage

### Run in Background (Optional)
For very long conversions:
```bash
$ nohup flexflow tecplot convert CS4SG1U1 > conversion.log 2>&1 &
$ tail -f conversion.log  # Monitor progress
```

### Interrupt and Resume
If interrupted, run again with time range:
```bash
# First run converts 50-200
$ flexflow tecplot convert CS4SG1U1 --start-step 50 --end-step 200

# Later, continue from 250
$ flexflow tecplot convert CS4SG1U1 --start-step 250 --end-step 4000
```

## File Size Reference

- PLT file: ~187 MB
- HDF5 file: ~150 MB (20% smaller)
- VTK file: ~200 MB
- Conversion time: ~1 minute per file

For 80 files:
- Total PLT size: ~15 GB
- Total HDF5 size: ~12 GB  
- Total time: ~80 minutes
