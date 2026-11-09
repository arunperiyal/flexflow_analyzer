"""
Utilities for handling case iteration when case name is '*'.

When a command receives case name '*', it should iterate over all cases
from the .cases.yml file and execute its logic for each case.
"""

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
    Load cases from the .cases.yml file in the given directory.
    
    The `cases` section of .cases.yml (src/core/cases_file.py):
      cases:
        - name: Case001
          path: /full/path/to/Case001
    
    Args:
        base_dir: Directory containing the .cases.yml file
        
    Returns:
        List of case dicts with 'name' and 'path' keys, or empty list if error
    """
    from src.core import cases_file
    try:
        return cases_file.read(base_dir).cases
    except cases_file.CasesFileError:
        return []
