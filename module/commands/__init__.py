"""Command implementations"""

from .info_cmd import command as info
from .plot_cmd import command as plot
from .compare_cmd import command as compare
from .template_cmd import command as template

__all__ = ['info', 'plot', 'compare', 'template']
