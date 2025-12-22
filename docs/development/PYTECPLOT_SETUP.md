# PyTecplot Setup and Testing Summary

## Test Date
December 19, 2025

## Installation Status

### PyTecplot Package
✅ **Successfully Installed**
- Version: 1.7.2
- Location: `/home/arunperiyal/miniconda3/lib/python3.13/site-packages/`
- Dependencies: protobuf, pyzmq

```bash
pip install pytecplot
```

### Tecplot 360 Installation
✅ **Detected**
- Version: Tecplot 360 EX 2022 R1 (2022.1.0.14449)
- Location: `/usr/local/tecplot/360ex_2022r1/`
- Binary: `/usr/local/tecplot/360ex_2022r1/bin/tec360`

### License Status
❌ **Expired**
- Current license has expired
- Need to renew license to use PyTecplot functionality

## Testing Results

### Test 1: PyTecplot Import
✅ **PASS** - Module imports successfully

```python
import tecplot as tp
print(tp.__version__)  # 1.7.2
```

### Test 2: Batch Mode Initialization
✅ **PASS** - Batch mode can be enabled

```python
tp.session.suspend()  # No GUI required
```

### Test 3: PLT File Loading
❌ **FAIL** - License expired
- Error: `tecplot.exception.TecplotLicenseError: License Expired`
- File to test: `CS4SG1U1/binary/riser.100.plt`
- File format: Tecplot binary (version TDV112)
- File size: 187 MB

## Usage Instructions

### Method 1: Using tec360-env Wrapper (Recommended)

PyTecplot must be run through the Tecplot environment wrapper:

```bash
/usr/local/tecplot/360ex_2022r1/bin/tec360-env -- python3 your_script.py
```

### Method 2: Environment Variables

Set these before running Python:

```bash
export TEC360HOME=/usr/local/tecplot/360ex_2022r1
export PATH=$TEC360HOME/bin:$PATH
export LD_LIBRARY_PATH=$TEC360HOME/lib:$LD_LIBRARY_PATH
```

## Example Code (When License is Valid)

```python
import tecplot as tp
from tecplot.exception import *
from tecplot.constant import *

# Use batch mode (no GUI)
tp.session.suspend()

# Load PLT file
dataset = tp.data.load_tecplot('CS4SG1U1/binary/riser.100.plt')

# Get information
print(f"Zones: {dataset.num_zones}")
print(f"Variables: {dataset.num_variables}")

# List variables
for var in dataset.variables():
    print(f"  - {var.name}")

# List zones
for zone in dataset.zones():
    print(f"Zone: {zone.name}")
    print(f"  Type: {zone.zone_type}")
    print(f"  Points: {zone.num_points}")

# Extract data from first zone
zone = dataset.zone(0)

# Get coordinate arrays
x = zone.values('X')
y = zone.values('Y')
z = zone.values('Z')

# Get field data
pressure = zone.values('Pressure')
velocity_x = zone.values('U')
velocity_y = zone.values('V')
velocity_z = zone.values('W')

# Get displacements
disp_x = zone.values('dispX')
disp_y = zone.values('dispY')
disp_z = zone.values('dispZ')

# Data is numpy arrays
print(f"Pressure range: [{pressure.min()}, {pressure.max()}]")
```

## PLT File Information

### Detected Variables in riser.100.plt:
Based on hexdump analysis:
- **Coordinates**: X, Y, Z
- **Velocity**: U, V, W
- **Pressure**: Pressure
- **Displacements**: dispX, dispY, dispZ
- **Vorticity**: xVor, yVor, zVor
- **Turbulence**: eddy (eddy viscosity)
- **Flow Features**: QCriterion, orderPar

### File Properties:
- Format: Tecplot binary (TDV112)
- Size: ~187 MB per timestep
- Naming: `riser.{step}.plt` (e.g., riser.100.plt, riser.150.plt)
- Frequency: Every 50 timesteps (50, 100, 150, ...)
- Location: `{case_dir}/binary/`

## Integration with FlexFlow

Once license is renewed, PyTecplot can be integrated into FlexFlow:

### Proposed Features:

1. **PLT Reader Module**
   ```python
   from module.core.readers import PLTReader
   
   reader = PLTReader('CS4SG1U1/binary', frequency=50)
   data = reader.read_timestep(100)
   ```

2. **Visualization Commands**
   ```bash
   # Plot pressure contours
   flexflow viz CS4SG1U1 --timestep 100 --variable Pressure --type contour
   
   # Create velocity vectors
   flexflow viz CS4SG1U1 --timestep 100 --variable Velocity --type vector
   
   # Animate time series
   flexflow viz CS4SG1U1 --animate --start 100 --end 1000 --step 50
   ```

3. **3D Field Analysis**
   - Extract slice data
   - Compute derived quantities
   - Export to other formats (VTK, CSV)

## Next Steps

1. **Renew Tecplot License**
   - Contact: Tecplot support
   - License file location: Check `/usr/local/tecplot/360ex_2022r1/`

2. **Verify License**
   ```bash
   /usr/local/tecplot/360ex_2022r1/bin/tec360 -v
   ```

3. **Retest PyTecplot**
   Run the test script again after license renewal

4. **Develop PLTReader Class**
   Integrate into FlexFlow module structure

## Alternative Solutions (If License Not Available)

### 1. Convert PLT to Other Formats
Use Tecplot batch mode to export:
```bash
tec360 -b -p convert_to_vtk.mcr
```

### 2. Use Open-Source Readers
- **pytecio**: GitHub alternative for PLT reading
- **VTK/ParaView**: May support some PLT formats

### 3. Request Academic License
Tecplot offers academic licenses for research institutions

## References

- PyTecplot Documentation: https://www.tecplot.com/docs/pytecplot/
- Tecplot 360 User Manual: Check installation directory
- FlexFlow Documentation: `docs/README.md`

## Testing Checklist

- [x] Install PyTecplot
- [x] Verify Tecplot 360 installation
- [x] Test import
- [x] Test batch mode
- [ ] Test PLT file loading (pending license)
- [ ] Test data extraction (pending license)
- [ ] Develop PLTReader class (pending license)
- [ ] Integrate with FlexFlow (pending license)

