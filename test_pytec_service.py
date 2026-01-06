#!/usr/bin/env python3
"""Test pytecplot with service approach"""
import os
import sys

# According to PyTecplot docs, for batch mode we need to use pytecplot.utils.run_in_batch
# OR start tec360 in service mode and connect to it

# Try the utils approach
try:
    import tecplot as tp
    from tecplot.constant import LoaderType
    
    print("Starting Tecplot engine in batch mode...")
    
    # Load data - this should auto-start engine
    with tp.session.suspend():
        dataset = tp.data.load_tecplot("CS4SG1U1/binary/riser.1050.plt")
        print("Dataset loaded!")
        vars = [v.name for v in dataset.variables()]
        print(f"Variables: {vars}")
        
        # Get data from first zone
        zone = dataset.zone(0)
        print(f"Zone 0: {zone.name}")
        
        # Extract Y variable
        if 'Y' in vars:
            y_data = zone.values('Y')[:]
            print(f"Y data shape: {y_data.shape}")
            print(f"Y range: [{y_data.min()}, {y_data.max()}]")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
