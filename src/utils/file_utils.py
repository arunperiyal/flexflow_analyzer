"""File utility functions."""

import os
import re
import glob


def natural_sort_key(path):
    """Sort key that orders numbers within a file name numerically.

    Archived restarts are named riser1, riser2, ... riser10; a plain string
    sort puts riser10 between riser1 and riser2, which is out of run order.
    """
    name = os.path.basename(str(path))
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r'(\d+)', name)]


def find_files(directory, pattern):
    """Find all files matching pattern in directory."""
    search_pattern = os.path.join(directory, pattern)
    return sorted(glob.glob(search_pattern), key=natural_sort_key)


def ensure_directory_exists(directory):
    """Ensure directory exists, create if it doesn't."""
    os.makedirs(directory, exist_ok=True)
