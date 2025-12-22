# Tecplot PLT Binary File Reading - Open-Source Options

## Problem Statement
FlexFlow needs to read Tecplot binary PLT files (`riser.100.plt`, etc.) containing 3D field data (pressure, velocity, displacements, vorticity, etc.) without using PyTecplot (requires license).

## File Analysis
- **Format**: Tecplot binary (TDV112)
- **Size**: ~187 MB per timestep
- **Variables**: X, Y, Z, U, V, W, Pressure, dispX, dispY, dispZ, eddy, xVor, yVor, zVor, QCriterion, orderPar
- **Location**: `{case_dir}/binary/riser.{step}.plt`
- **Frequency**: Every 50 timesteps

## Tested Solutions

### ❌ PyTecplot
- **Status**: Requires valid Tecplot 360 license
- **Result**: License expired, cannot use

### ❌ meshio
- **Status**: Installed and tested
- **Result**: Only supports ASCII Tecplot format (.dat), not binary (.plt)
- **Use case**: Could work if you convert PLT → DAT first

### ✅ Custom Binary Reader (Partial Success)
- **Status**: Successfully parsed header and variable names
- **Result**: Can extract metadata but full data extraction needs more work
- **Pros**: No dependencies, full control
- **Cons**: Requires understanding binary format, time-consuming

## RECOMMENDED OPTIONS

### Option 1: One-Time Conversion (BEST FOR YOU)
**Convert PLT → HDF5/VTK once, then use open-source tools**

#### Step 1: Create Tecplot Macro for Batch Export
```tcl
# convert_plt_to_h5.mcr
#!MC 1410

$!VARSET |CASE| = "CS4SG1U1"
$!VARSET |BINARY_DIR| = "|CASE|/binary"
$!VARSET |OUTPUT_DIR| = "|CASE|/hdf5"

# Create output directory
$!SYSTEM "mkdir -p |OUTPUT_DIR|"

# Loop through PLT files
$!LOOP 100
  $!VARSET |STEP| = (|LOOP| * 50)
  $!IF |STEP| >= 100
    $!VARSET |INFILE| = "|BINARY_DIR|/riser.|STEP|.plt"
    $!VARSET |OUTFILE| = "|OUTPUT_DIR|/riser_|STEP|.h5"
    
    # Check if file exists
    $!IF EXISTS("|INFILE|")
      $!ReadDataSet '|INFILE|'
      $!WriteDataSet '|OUTFILE|'
        IncludeText = No
        IncludeGeom = No
        Binary = Yes
        Precision = Double
    $!ENDIF
  $!ENDIF
$!ENDLOOP
```

#### Step 2: Run Conversion (One Time)
```bash
# Using GUI
tec360 -p convert_plt_to_h5.mcr

# Or batch mode
tec360 -b -p convert_plt_to_h5.mcr
```

#### Step 3: Use Python with HDF5 files
```python
import h5py
import numpy as np

# Read converted file
with h5py.File('CS4SG1U1/hdf5/riser_100.h5', 'r') as f:
    x = f['X'][:]
    y = f['Y'][:]
    z = f['Z'][:]
    pressure = f['Pressure'][:]
    # ... all other variables
```

**Advantages:**
- ✅ Do conversion once
- ✅ Use fast, open-source HDF5 library
- ✅ No license needed after conversion
- ✅ HDF5 files can be smaller than PLT
- ✅ Works with all Python visualization tools

### Option 2: Develop Complete Custom Reader
**Reverse-engineer the binary format**

#### What We've Done:
```python
class SimplePLTReader:
    """Successfully parses PLT header and variable names"""
    
    def __init__(self, filename):
        # ✅ Read magic string: #!TDV112
        # ✅ Parse title: "Tecplot output"
        # ✅ Extract variables: X, Y, Z, U, V, W, Pressure, etc.
        pass
    
    def read_zone_data(self):
        # ❌ TODO: Parse zone information
        # ❌ TODO: Read data blocks
        # ❌ TODO: Handle different zone types
        pass
```

#### What's Needed:
1. Parse zone headers (dimensions, type, etc.)
2. Locate data blocks in file
3. Read binary data arrays
4. Handle different zone types (ordered, FE, etc.)
5. Test with various PLT files

#### Estimated Effort:
- **Basic functionality**: 1-2 weeks
- **Robust implementation**: 1-2 months
- **Maintenance**: Ongoing

**Advantages:**
- ✅ No external dependencies
- ✅ Full control
- ✅ Can be optimized for your specific needs

**Disadvantages:**
- ❌ Time-consuming development
- ❌ May break with format changes
- ❌ Need to handle edge cases

### Option 3: Use VTK/ParaView
**If you can access ParaView**

ParaView (free, open-source) sometimes can read PLT files:

```bash
# Try opening in ParaView GUI
paraview riser.100.plt

# Or use Python bindings
from paraview.simple import *
reader = TecplotReader(FileName='riser.100.plt')
# Extract data...
```

### Option 4: Hybrid Approach
**Use Tecplot for preprocessing, Python for analysis**

1. Use Tecplot to extract specific data you need:
   - Slices at specific locations
   - Reduced resolution
   - Specific variables only

2. Export to simple format (CSV, ASCII)

3. Use Python/FlexFlow for analysis and visualization

## RECOMMENDATION FOR FLEXFLOW

Given your situation, I recommend **Option 1: One-Time Conversion**

### Implementation Plan:

1. **Create conversion utility**:
   ```bash
   flexflow convert CS4SG1U1 --format hdf5
   ```

2. **Develop HDF5 reader**:
   ```python
   # module/core/readers/hdf5_reader.py
   class HDF5FieldReader:
       """Read converted field data from HDF5"""
       
       def __init__(self, directory, frequency=50):
           self.directory = directory
           self.frequency = frequency
           
       def read_timestep(self, step):
           filename = f'{self.directory}/riser_{step}.h5'
           with h5py.File(filename, 'r') as f:
               return {
                   'coords': (f['X'][:], f['Y'][:], f['Z'][:]),
                   'velocity': (f['U'][:], f['V'][:], f['W'][:]),
                   'pressure': f['Pressure'][:],
                   'displacement': (f['dispX'][:], f['dispY'][:], f['dispZ'][:])
               }
   ```

3. **Add visualization commands**:
   ```bash
   flexflow field CS4SG1U1 --timestep 100 --variable Pressure --slice z=0
   flexflow field CS4SG1U1 --timestep 100 --variable Velocity --type vector
   ```

### Why This is Best:

1. **One-time effort**: Convert all files once
2. **Open-source**: HDF5 is free, fast, widely supported
3. **Flexible**: Can convert to other formats too (VTK, NetCDF)
4. **Maintainable**: No need to maintain custom PLT reader
5. **Fast**: HDF5 is optimized for scientific data

## Implementation Steps

### Phase 1: Conversion Setup (1 day)
1. Create Tecplot macro for batch conversion
2. Test on one file
3. Run conversion on all timesteps

### Phase 2: HDF5 Reader (2-3 days)
1. Create HDF5FieldReader class
2. Test data extraction
3. Integration with FlexFlow

### Phase 3: Visualization (1 week)
1. Add field visualization commands
2. Slice extraction
3. Vector plots
4. Contour plots

### Total Time: ~2 weeks for full implementation

## Next Steps

Would you like me to:
1. ✅ Create the Tecplot conversion macro?
2. ✅ Develop the HDF5Reader class?
3. ✅ Design the field visualization commands?
4. ⚠️ Continue developing the custom binary PLT reader?

Choose option 1-3 for fastest, most reliable solution.
Choose option 4 if you want complete independence from Tecplot.
