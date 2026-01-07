"""
Base command class for FlexFlow CLI commands
"""

from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """
    Base class for all FlexFlow commands
    
    Each command should inherit from this class and implement the required methods.
    This ensures consistency across all commands and enables the registry pattern.
    """
    
    @property
    @abstractmethod
    def name(self):
        """
        Command name (e.g., 'info', 'plot', 'compare')
        
        Returns:
            str: The command name
        """
        pass
    
    @property
    @abstractmethod
    def description(self):
        """
        Short description for help message
        
        Returns:
            str: Brief description of what the command does
        """
        pass
    
    @property
    def category(self):
        """
        Command category for grouped help display
        
        Returns:
            str: Category name (default: 'General')
        """
        return "General"
    
    @abstractmethod
    def setup_parser(self, subparsers):
        """
        Configure argument parser for this command
        
        Parameters:
            subparsers: argparse subparsers object to add this command's parser to
            
        Returns:
            argparse.ArgumentParser: The configured parser for this command
        """
        pass
    
    @abstractmethod
    def execute(self, args):
        """
        Execute the command with parsed arguments
        
        Parameters:
            args: Parsed command-line arguments (argparse.Namespace)
        """
        pass
    
    def show_help(self):
        """
        Show detailed help for this command
        
        Override this method to provide custom help output.
        Default implementation does nothing.
        """
        pass
    
    def show_examples(self):
        """
        Show usage examples for this command
        
        Override this method to provide example usage.
        Default implementation does nothing.
        """
        pass
