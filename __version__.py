"""
FlexFlow Version Information
"""

__version__ = "2.0.0"
__version_info__ = (2, 0, 0)

# Release information
VERSION = "2.0.0"
VERSION_NAME = "Standalone"
BUILD_DATE = "2026-01-06"
PYTHON_VERSION = "3.12+"

# Feature summary for this version
FEATURES = [
    "Standalone executable with embedded Python 3.12",
    "PyTecplot integration (2-3x faster)",
    "Auto Python 3.12 wrapper support",
    "Domain-driven command structure",
    "OTHD/OISD file analysis",
    "Multi-case comparison",
    "Tecplot PLT file operations",
    "HDF5/SZPLT conversion",
]

def get_version_string():
    """Get formatted version string"""
    return f"FlexFlow v{VERSION} ({VERSION_NAME})"

def get_full_version_info():
    """Get complete version information"""
    return f"""FlexFlow Version {VERSION} - {VERSION_NAME}

Build Date:    {BUILD_DATE}
Python:        {PYTHON_VERSION}

Features:
  • Standalone executable (no Python required)
  • PyTecplot integration (2-3x faster)
  • Auto Python 3.12 wrapper
  • OTHD/OISD analysis
  • Multi-case comparison
  • Tecplot operations
  • Format conversion (HDF5/SZPLT)

Repository: https://github.com/arunperiyal/flexflow_analyzer
Documentation: docs/INDEX.md
"""

if __name__ == "__main__":
    print(get_full_version_info())
