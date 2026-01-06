#!/usr/bin/env python3
import os
os.environ['TEC360BATCH'] = '1'  # Force batch mode

import tecplot as tp
from tecplot.exception import *

print("Tecplot version:", tp.__version__)

# Try to load in batch mode
try:
    print("Loading data...")
    ds = tp.data.load_tecplot("CS4SG1U1/binary/riser.1050.plt")
    print("Success!")
    print("Variables:", [v.name for v in ds.variables()])
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
