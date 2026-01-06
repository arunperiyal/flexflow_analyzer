# Tecplot Crash Issue - Root Cause and Solution

## Problem
- **Your System (RedLotus)**: Python 3.13.2 + Tecplot 360 2024 R1 → **Aborted (core dumped)**
- **Other System (GreenLotus)**: Python 3.12.3 → Works fine

## Root Cause
**Tecplot 360 2024 R1 is NOT compatible with Python 3.13**

The pytecplot library (version 1.7.2) was built and tested with Python 3.12 and earlier versions. Python 3.13 introduced changes that cause segmentation faults when Tecplot tries to initialize.

## Solution
Use Python 3.12 instead of Python 3.13

### Option 1: Use the conda environment (RECOMMENDED)
```bash
# Activate the Python 3.12 environment
conda activate tecplot312

# Now use Tecplot
python -c "import tecplot; tecplot.new_layout()"
```

### Option 2: Use system Python 3.12 directly
```bash
# Use python3.12 explicitly
python3.12 -m pip install --user pytecplot==1.7.2

# Then use it
python3.12 your_script.py
```

### Option 3: Set Python 3.12 as default in current shell
```bash
alias python3='/usr/bin/python3.12'
alias python='/usr/bin/python3.12'
```

## Verification
```bash
# Test with Python 3.12
conda activate tecplot312
python -c "import tecplot; tecplot.new_layout(); print('SUCCESS!')"
```

## Why GreenLotus Works
GreenLotus is using system Python 3.12.3, which is compatible with Tecplot 360 2024 R1.

## Future Solution
Wait for Tecplot to release a Python 3.13 compatible version, or upgrade to a newer Tecplot version that supports Python 3.13.
