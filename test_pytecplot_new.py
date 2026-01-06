#!/usr/bin/env python3
"""
Test script for pytecplot-based FlexFlow operations.

This script tests the new pytecplot implementation for:
1. Data extraction from PLT files
2. PLT file information retrieval
3. PLT to HDF5 conversion

NOTE: This requires Python 3.12 or earlier. Run with:
      conda activate tecplot312
      python test_pytecplot_new.py
"""

import sys
import os
from pathlib import Path

# Add module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_python_version():
    """Test if Python version is compatible"""
    print("="*70)
    print("TEST 1: Python Version Check")
    print("="*70)
    
    from module.tecplot_pytec import check_python_version
    
    compatible, msg = check_python_version()
    print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"Compatible: {compatible}")
    print(f"Message: {msg}")
    
    if not compatible:
        print("\n⚠️  WARNING: Python 3.13+ detected!")
        print("   Please use Python 3.12 or earlier:")
        print("   conda activate tecplot312")
        return False
    
    print("\n✓ Python version is compatible")
    return True


def test_initialization():
    """Test pytecplot initialization"""
    print("\n" + "="*70)
    print("TEST 2: PyTecplot Initialization")
    print("="*70)
    
    from module.tecplot_pytec import initialize_tecplot_batch
    
    success, result = initialize_tecplot_batch()
    
    if success:
        print(f"✓ PyTecplot initialized successfully")
        print(f"  Version: {result.__version__}")
        return True
    else:
        print(f"✗ Initialization failed: {result}")
        return False


def test_plt_info():
    """Test getting PLT file information"""
    print("\n" + "="*70)
    print("TEST 3: Get PLT File Information")
    print("="*70)
    
    # Find a test PLT file
    test_cases = ['CS4SG1U1', 'CS4SG2U1']
    plt_file = None
    
    for case in test_cases:
        case_path = Path(case)
        if case_path.exists():
            binary_dir = case_path / 'binary'
            if binary_dir.exists():
                plt_files = list(binary_dir.glob('*.plt'))
                if plt_files:
                    plt_file = plt_files[0]
                    break
    
    if not plt_file:
        print("✗ No test PLT files found")
        print(f"  Searched in: {', '.join(test_cases)}")
        return False
    
    print(f"Testing with: {plt_file}")
    
    from module.tecplot_pytec import get_plt_info
    
    info = get_plt_info(plt_file)
    
    if 'error' in info:
        print(f"✗ Failed: {info['error']}")
        return False
    
    print(f"\n✓ Successfully read PLT file")
    print(f"  Zones: {info['num_zones']}")
    print(f"  Variables: {info['num_variables']}")
    print(f"  Variable names: {', '.join(info['variables'][:5])}...")
    
    for i, zone in enumerate(info['zones'][:3]):
        print(f"\n  Zone {i+1}: {zone['name']}")
        print(f"    Type: {zone['zone_type']}")
        print(f"    Points: {zone['num_points']}")
    
    return True


def test_data_extraction():
    """Test data extraction from PLT file"""
    print("\n" + "="*70)
    print("TEST 4: Extract Data from PLT File")
    print("="*70)
    
    # Find a test case
    test_cases = ['CS4SG1U1', 'CS4SG2U1']
    case_dir = None
    timestep = None
    
    for case in test_cases:
        case_path = Path(case)
        if case_path.exists():
            binary_dir = case_path / 'binary'
            if binary_dir.exists():
                plt_files = sorted(binary_dir.glob('*.plt'))
                if plt_files:
                    case_dir = case_path
                    # Extract timestep from filename
                    import re
                    match = re.search(r'\.(\d+)\.plt$', str(plt_files[0]))
                    if match:
                        timestep = int(match.group(1))
                    break
    
    if not case_dir or not timestep:
        print("✗ No test case found")
        return False
    
    print(f"Testing with case: {case_dir}, timestep: {timestep}")
    
    from module.tecplot_pytec import extract_data_pytecplot
    
    # Extract a few variables
    variables = ['X', 'Y', 'Z', 'U', 'V', 'W']
    output_file = case_dir / f"test_extract_{timestep}.csv"
    
    success, result = extract_data_pytecplot(
        str(case_dir),
        timestep,
        zone=None,  # Extract all zones
        variables=variables,
        output_file=str(output_file),
        subdomain=None
    )
    
    if success:
        print(f"\n✓ Data extraction successful")
        print(f"  Output file: {result}")
        
        # Check if file exists and has content
        if Path(result).exists():
            size = Path(result).stat().st_size
            print(f"  File size: {size:,} bytes")
            
            # Clean up test file
            Path(result).unlink()
            print(f"  Test file cleaned up")
        
        return True
    else:
        print(f"\n✗ Data extraction failed: {result}")
        return False


def test_conversion():
    """Test PLT to HDF5 conversion"""
    print("\n" + "="*70)
    print("TEST 5: Convert PLT to HDF5")
    print("="*70)
    
    # Find a test case
    test_cases = ['CS4SG1U1', 'CS4SG2U1']
    case_dir = None
    
    for case in test_cases:
        case_path = Path(case)
        if case_path.exists():
            binary_dir = case_path / 'binary'
            if binary_dir.exists():
                plt_files = list(binary_dir.glob('*.plt'))
                if plt_files:
                    case_dir = case_path
                    break
    
    if not case_dir:
        print("✗ No test case found")
        return False
    
    print(f"Testing with case: {case_dir}")
    print("  Converting first PLT file only...")
    
    from module.tecplot_pytec import convert_plt_to_format
    
    # Get first timestep
    binary_dir = case_dir / 'binary'
    plt_files = sorted(binary_dir.glob('*.plt'))
    
    import re
    match = re.search(r'\.(\d+)\.plt$', str(plt_files[0]))
    if match:
        start_step = int(match.group(1))
    else:
        print("✗ Could not determine timestep")
        return False
    
    output_dir = binary_dir / 'test_converted'
    
    success, result = convert_plt_to_format(
        str(case_dir),
        output_format='hdf5',
        start_step=start_step,
        end_step=start_step,  # Convert only one file
        keep_original=True,
        output_dir=str(output_dir)
    )
    
    if success:
        print(f"\n✓ Conversion successful")
        print(f"  Converted files: {len(result)}")
        for f in result:
            print(f"    - {Path(f).name}")
        
        # Clean up test files
        for f in result:
            Path(f).unlink()
        output_dir.rmdir()
        print(f"  Test files cleaned up")
        
        return True
    else:
        print(f"\n✗ Conversion failed: {result}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("PYTECPLOT IMPLEMENTATION TEST SUITE")
    print("="*70)
    print("\nThis tests the new pytecplot-based implementation")
    print("for FlexFlow Tecplot operations.\n")
    
    results = {}
    
    # Test 1: Python version
    results['Python Version'] = test_python_version()
    
    if not results['Python Version']:
        print("\n" + "="*70)
        print("TESTS SKIPPED: Incompatible Python version")
        print("="*70)
        print("\nPlease activate Python 3.12 environment:")
        print("  conda activate tecplot312")
        return
    
    # Test 2: Initialization
    results['Initialization'] = test_initialization()
    
    if not results['Initialization']:
        print("\n" + "="*70)
        print("TESTS ABORTED: PyTecplot not available")
        print("="*70)
        return
    
    # Test 3: PLT info
    results['PLT Info'] = test_plt_info()
    
    # Test 4: Data extraction
    results['Data Extraction'] = test_data_extraction()
    
    # Test 5: Conversion
    results['Conversion'] = test_conversion()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name:<20} {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
        print("\nThe pytecplot implementation is working correctly.")
        print("You can now use FlexFlow with pytecplot instead of MCR files.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("\nSome features may not work correctly.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
