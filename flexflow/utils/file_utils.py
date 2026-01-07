"""File utility functions."""

import os
import glob


def find_files(directory, pattern):
    """Find all files matching pattern in directory."""
    search_pattern = os.path.join(directory, pattern)
    return sorted(glob.glob(search_pattern))


def ensure_directory_exists(directory):
    """Ensure directory exists, create if it doesn't."""
    os.makedirs(directory, exist_ok=True)
