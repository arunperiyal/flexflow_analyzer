"""
Command registry for FlexFlow CLI

This module provides a registry pattern for managing commands.
Commands register themselves at startup and can be looked up by name.
"""


class CommandRegistry:
    """
    Registry for managing FlexFlow commands
    
    The registry maintains a collection of available commands and provides
    methods for registration, lookup, and categorization.
    """
    
    def __init__(self):
        """Initialize an empty command registry"""
        self._commands = {}
    
    def register(self, command_class):
        """
        Register a command class
        
        Parameters:
            command_class: A class that inherits from BaseCommand
            
        Returns:
            BaseCommand: The instantiated command object
            
        Raises:
            ValueError: If a command with the same name is already registered
        """
        cmd = command_class()
        
        if cmd.name in self._commands:
            raise ValueError(f"Command '{cmd.name}' is already registered")
        
        self._commands[cmd.name] = cmd
        return cmd
    
    def get(self, name):
        """
        Get a command by name
        
        Parameters:
            name (str): The command name
            
        Returns:
            BaseCommand: The command object, or None if not found
        """
        return self._commands.get(name)
    
    def all(self):
        """
        Get all registered commands
        
        Returns:
            list: List of all command objects
        """
        return list(self._commands.values())
    
    def by_category(self):
        """
        Get commands grouped by category
        
        Returns:
            dict: Dictionary mapping category names to lists of commands
        """
        categories = {}
        for cmd in self._commands.values():
            cat = cmd.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cmd)
        return categories
    
    def has_command(self, name):
        """
        Check if a command is registered
        
        Parameters:
            name (str): The command name
            
        Returns:
            bool: True if command exists, False otherwise
        """
        return name in self._commands
    
    def list_names(self):
        """
        Get a list of all command names
        
        Returns:
            list: Sorted list of command names
        """
        return sorted(self._commands.keys())


# Global registry instance
registry = CommandRegistry()
