# FlexFlow PyTecplot Quick Reference

## Setup (One Time)

```bash
# Activate Python 3.12 environment
conda activate tecplot312

# Verify setup
python --version  # Should show 3.12.x
python -c "import tecplot; print('✓ PyTecplot', tecplot.__version__)"
```

## Common Tasks

### Extract Data from PLT File

```bash
# Basic extraction
flexflow field extract CS4SG1U1 --timestep 1000 --variables X,Y,Z,U,V,W

# Extract specific zone
flexflow field extract CS4SG1U1 --timestep 1000 --zone FIELD --variables U,V,W

# Extract with subdomain filter
flexflow field extract CS4SG1U1 \
    --timestep 1000 \
    --variables X,Y,Z,U,V,W,Pressure \
    --subdomain xmin=0 xmax=10 ymin=-5 ymax=5 zmin=0 zmax=20
```

### Convert PLT to Other Formats

```bash
# Convert all files to HDF5
flexflow tecplot convert CS4SG1U1 --format hdf5

# Convert specific timestep range
flexflow tecplot convert CS4SG1U1 --format hdf5 --start-step 1000 --end-step 2000

# Convert single timestep
flexflow tecplot convert CS4SG1U1 --format hdf5 --start-step 1000 --end-step 1000
```

### Get PLT File Information

```bash
# Show file info (zones, variables, etc.)
flexflow field info CS4SG1U1
```

## Python API

### Extract Data

```python
from module.tecplot_pytec import extract_data_pytecplot

success, output = extract_data_pytecplot(
    case_dir='CS4SG1U1',
    timestep=1000,
    zone='FIELD',  # or None for all zones
    variables=['X', 'Y', 'Z', 'U', 'V', 'W'],
    output_file='extracted.csv',  # optional
    subdomain={'xmin': 0, 'xmax': 10}  # optional
)

if success:
    print(f"Data saved to: {output}")
    import pandas as pd
    df = pd.read_csv(output)
    print(df.head())
```

### Convert Files

```python
from module.tecplot_pytec import convert_plt_to_format

success, files = convert_plt_to_format(
    case_dir='CS4SG1U1',
    output_format='hdf5',  # or 'szplt', 'plt', 'dat'
    start_step=1000,
    end_step=2000,
    keep_original=True,
    output_dir='converted'  # optional
)

if success:
    print(f"Converted {len(files)} files")
    for f in files:
        print(f"  - {f}")
```

### Get File Info

```python
from module.tecplot_pytec import get_plt_info

info = get_plt_info('CS4SG1U1/binary/riser.1000.plt')

print(f"Zones: {info['num_zones']}")
print(f"Variables: {', '.join(info['variables'])}")

for zone in info['zones']:
    print(f"{zone['name']}: {zone['num_points']} points")
```

## Troubleshooting

### "Aborted (core dumped)"
➜ **Using Python 3.13+**
```bash
conda activate tecplot312
```

### "pytecplot not installed"
```bash
conda activate tecplot312
pip install pytecplot==1.7.2
```

### PyTecplot fails, falls back to macros
✓ **Normal behavior** - macros still work

### Both PyTecplot and macros fail
```bash
# Check Tecplot
/usr/local/tecplot/360ex_2024r1/bin/tec360 -v

# Check environment
echo $LD_LIBRARY_PATH | grep tecplot
```

## Performance Tips

1. **Use PyTecplot** (2-3x faster than macros)
   - Activate tecplot312 environment
   - FlexFlow uses it automatically

2. **Subdomain Filtering** reduces extracted data size
   ```bash
   --subdomain xmin=0 xmax=10 ymin=-5 ymax=5
   ```

3. **Select Variables** only what you need
   ```bash
   --variables X,Y,Z,U,V,W  # Not all 16 variables
   ```

4. **Batch Processing** convert multiple files at once
   ```bash
   flexflow tecplot convert CASE --format hdf5  # All files
   ```

## Format Comparison

| Format | Extension | Size | Speed | Use Case |
|--------|-----------|------|-------|----------|
| HDF5/SZPLT | .h5, .szplt | Small | Fast | **Recommended** |
| PLT | .plt | Large | Medium | Tecplot native |
| DAT | .dat | Largest | Slow | ASCII, debugging |

## Environment Variables

```bash
# Set Tecplot home (if needed)
export TEC360HOME=/usr/local/tecplot/360ex_2024r1

# Add to LD_LIBRARY_PATH (if needed)
export LD_LIBRARY_PATH=$TEC360HOME/bin:$TEC360HOME/lib:$LD_LIBRARY_PATH
```

## Test Your Setup

```bash
# Run test suite
conda activate tecplot312
python test_pytecplot_new.py

# Expected: 5/5 tests pass
```

## More Information

- **Full Guide:** [PYTECPLOT_GUIDE.md](PYTECPLOT_GUIDE.md)
- **Migration Notes:** [PYTECPLOT_MIGRATION.md](PYTECPLOT_MIGRATION.md)
- **Python 3.13 Issue:** [tecplot_fix_summary.md](tecplot_fix_summary.md)
- **FlexFlow Docs:** [README.md](README.md)

---

**Quick Start:** `conda activate tecplot312` → Use FlexFlow normally!
