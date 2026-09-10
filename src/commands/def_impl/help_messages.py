"""Help messages for the `def` command."""

from rich.console import Console
from rich.table import Table
from rich import box


def print_def_help():
    """Show help for the def command."""
    console = Console()
    console.print()
    console.print("[bold cyan]FlexFlow Def Command[/bold cyan]")
    console.print()
    console.print("Inspect and edit parameters and fields in a case's .def file.")
    console.print()
    console.print("[bold]USAGE:[/bold]")
    console.print("    flexflow def <subcommand> [options]")
    console.print()

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
    table.add_column("Subcommand", style="cyan")
    table.add_column("Description", style="white")
    table.add_row("var", "Show or edit define{} block variables")
    table.add_row("time", "Show or edit timeSteppingControl{} values (maxTime, inc)")

    console.print("[bold]SUBCOMMANDS:[/bold]")
    console.print(table)
    console.print()
    console.print("[bold]EXAMPLES:[/bold]")
    console.print("    flexflow def var                 # List all variables in a table")
    console.print("    flexflow def var Ur              # Show the value of Ur")
    console.print("    flexflow def var Ur 2.0          # Set Ur = 2.0 in the .def file")
    console.print("    flexflow def var --case CS4SG1U1 # Operate on a specific case")
    console.print()
    console.print("    flexflow def time                     # List maxTimeSteps, initialTimeIncrement, etc.")
    console.print("    flexflow def time maxTime             # Show maxTimeSteps")
    console.print("    flexflow def time maxTime 7000        # Set maxTimeSteps = 7000")
    console.print("    flexflow def time inc                 # Show initialTimeIncrement")
    console.print("    flexflow def time inc 0.05            # Set initialTimeIncrement = 0.05")
    console.print()
