"""
Application configuration for FlexFlow
"""

import os


class Config:
    """Application-level configuration"""
    
    # Version
    VERSION = "1.0.0"
    
    # Installation paths
    INSTALL_SCRIPT = "flexflow"
    BASH_RC_PATHS = ["~/.bashrc", "~/.bash_profile", "~/.profile", "~/.zshrc"]
    
    # Alias configuration
    ALIAS_NAME = "flexflow"
    
    # Default plot settings
    DEFAULT_FIGSIZE = (12, 8)
    DEFAULT_LINEWIDTH = 1.5
    DEFAULT_GRID_ALPHA = 0.3
    
    # Color scheme for terminal output
    COLORS_ENABLED = True
    
    @staticmethod
    def get_install_dir():
        """Get the installation directory"""
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    @staticmethod
    def get_main_script():
        """Get the path to main.py"""
        return os.path.join(Config.get_install_dir(), "..", "main.py")
