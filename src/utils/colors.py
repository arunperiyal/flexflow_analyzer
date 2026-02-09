"""Color codes for terminal output."""

class Colors:
    """ANSI color codes for terminal output."""
    # Basic colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    GRAY = '\033[90m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    
    # Reset
    RESET = '\033[0m'
    
    @staticmethod
    def color(text, color_code):
        """Apply color to text"""
        return f"{color_code}{text}{Colors.RESET}"
    
    @staticmethod
    def bold(text):
        """Make text bold"""
        return f"{Colors.BOLD}{text}{Colors.RESET}"
    
    @staticmethod
    def red(text):
        """Make text red"""
        return Colors.color(text, Colors.RED)
    
    @staticmethod
    def green(text):
        """Make text green"""
        return Colors.color(text, Colors.GREEN)
    
    @staticmethod
    def yellow(text):
        """Make text yellow"""
        return Colors.color(text, Colors.YELLOW)
    
    @staticmethod
    def blue(text):
        """Make text blue"""
        return Colors.color(text, Colors.BLUE)
    
    @staticmethod
    def cyan(text):
        """Make text cyan"""
        return Colors.color(text, Colors.CYAN)
    
    @staticmethod
    def magenta(text):
        """Make text magenta"""
        return Colors.color(text, Colors.MAGENTA)

    @staticmethod
    def dim(text):
        """Make text dim"""
        return f"{Colors.DIM}{text}{Colors.RESET}"
