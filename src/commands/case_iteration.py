"""
Utilities for handling case iteration when case name is '*'.

When a command receives case name '*', it should iterate over all cases
from the .cases file and execute its logic for each case.
"""

import json
from pathlib import Path
from typing import List, Optional


def is_wildcard_case(case_name: Optional[str]) -> bool:
    """
    Check if case name is the wildcard '*' marker for all cases.
    
    Args:
        case_name: Case name to check
        
    Returns:
        True if case_name is '*', False otherwise
    """
    return case_name == "*"


def load_cases_from_directory(base_dir: Path) -> List[dict]:
    """
    Load cases from the .cases file in the given directory.
    
    The .cases file is a JSON file with format:
    [
      {'name': 'Case001', 'path': '/full/path/to/Case001'},
      {'name': 'Case002', 'path': '/full/path/to/Case002'},
      ...
    ]
    
    Args:
        base_dir: Directory containing the .cases file
        
    Returns:
        List of case dicts with 'name' and 'path' keys, or empty list if error
    """
    cases_file = Path(base_dir) / '.cases'
    
    if not cases_file.exists():
        return []
    
    try:
        with open(cases_file) as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return data
        else:
            return []
    except Exception:
        return []
