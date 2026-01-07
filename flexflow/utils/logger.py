"""Logging utility for FlexFlow."""

import sys
from .colors import Colors


class Logger:
    """Logger with color support and verbosity control."""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
    
    def info(self, message):
        """Print info message."""
        if self.verbose:
            print(f"{Colors.CYAN}[INFO]{Colors.RESET} {message}")
    
    def success(self, message):
        """Print success message."""
        if self.verbose:
            print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {message}")
    
    def warning(self, message):
        """Print warning message."""
        print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} {message}", file=sys.stderr)
    
    def error(self, message):
        """Print error message."""
        print(f"{Colors.RED}[ERROR]{Colors.RESET} {message}", file=sys.stderr)
    
    def debug(self, message):
        """Print debug message."""
        if self.verbose:
            print(f"{Colors.GRAY}[DEBUG]{Colors.RESET} {message}")
