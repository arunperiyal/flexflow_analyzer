#!/usr/bin/env python3
"""Test pytecplot with correct initialization"""
import sys
import os

# Run in batch mode - this must be done BEFORE importing tecplot
import tecplot as tp
from tecplot.constant import LoaderType

# This is critical: connect to tecplot in batch mode
tp.session.connect(port=7600)

try:
    print("Loading PLT file...")
    
    datafile = os.path.join("CS4SG1U1", "binary", "riser.1050.plt")
    
    # Load dataset
    dataset = tp.data.load_tecplot(datafile)
    
    print("Success! Dataset loaded")
    print(f"Variables: {[v.name for v in dataset.variables()]}")
    print(f"Zones: {[z.name for z in dataset.zones()]}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
