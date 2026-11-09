"""case add — scan a directory for FlexFlow cases and write a .cases.yml registry."""

from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box


_CASES_FILE = '.cases.yml'


def execute_add(args):
    """Scan a directory for cases and build / refresh the .cases.yml registry."""
    console = Console()

    if hasattr(args, 'help') and args.help:
        _show_help(console)
        return

    # Resolve the directory to scan
    scan_dir = Path(getattr(args, 'dir', None) or '.').resolve()
    if not scan_dir.is_dir():
        console.print(f"[red]Error:[/red] Not a directory: {scan_dir}")
        return

    console.print()
    console.print(f"[bold cyan]Scanning:[/bold cyan] {scan_dir}")
    console.print()

    found = scan_for_cases(scan_dir)

    if not found:
        console.print("[yellow]No case directories found (no simflow.config in immediate children).[/yellow]")
        console.print()
        return

    # Show the found cases in a numbered table
    tbl = Table(box=box.ROUNDED, show_header=True, header_style='bold')
    tbl.add_column('#',    style='dim',  justify='right', no_wrap=True)
    tbl.add_column('Case', style='cyan', no_wrap=True)
    tbl.add_column('Path', style='dim')

    for i, p in enumerate(found, 1):
        tbl.add_row(str(i), p.name, str(p))

    console.print(tbl)
    console.print()
    console.print(f"Found [bold]{len(found)}[/bold] case(s).")
    console.print()

    # Ask for exclusions
    console.print("[dim]Enter the numbers of cases to EXCLUDE (comma-separated), or press Enter to add all:[/dim]")
    console.print("Exclude: ", end='')
    try:
        raw = input().strip()
    except (EOFError, KeyboardInterrupt):
        console.print()
        console.print("[yellow]Aborted[/yellow]")
        return

    excluded = set()
    if raw:
        for token in raw.split(','):
            token = token.strip()
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(found):
                    excluded.add(idx - 1)  # 0-based
                else:
                    console.print(f"[yellow]Warning:[/yellow] index {idx} out of range, ignored.")

    selected = [p for i, p in enumerate(found) if i not in excluded]

    if not selected:
        console.print("[yellow]All cases excluded — nothing written.[/yellow]")
        console.print()
        return

    cases_path = write_cases_file(scan_dir, selected)

    console.print()
    console.print(f"[green]✓[/green] Wrote [bold]{len(selected)}[/bold] case(s) to [cyan]{cases_path}[/cyan]")
    if excluded:
        console.print(f"[dim]  Excluded {len(excluded)} case(s).[/dim]")
    console.print()


def scan_for_cases(directory: Path) -> list:
    """Return the immediate children of *directory* that contain simflow.config."""
    return [
        child for child in sorted(directory.iterdir())
        if child.is_dir() and (child / 'simflow.config').exists()
    ]


def write_cases_file(directory: Path, cases: list) -> Path:
    """Write *cases* (a list of Paths) as the `cases` of directory/.cases.yml,
    replacing the list and keeping its `remotes` and `auto`. Returns the path."""
    from ....core import cases_file
    cf = cases_file.read_or_new(directory)
    cf.cases = [{'name': p.name, 'path': str(p)} for p in cases]
    return cases_file.write(cf)


def load_cases_file(directory: Path) -> list:
    """The cases of directory/.cases.yml, as dicts with 'name' and 'path';
    [] when there is none or it cannot be read."""
    from ....core import cases_file
    try:
        return cases_file.read(directory).cases
    except cases_file.CasesFileError:
        return []


def _show_help(console):
    console.print()
    console.print("[bold cyan]case add[/bold cyan] — Build or refresh the .cases.yml registry")
    console.print()
    console.print("[bold]USAGE:[/bold]")
    console.print("    case add [--dir PATH]")
    console.print()
    console.print("[bold]OPTIONS:[/bold]")
    console.print("    --dir PATH    Directory to scan (default: current directory)")
    console.print("    -h, --help    Show this help message")
    console.print()
    console.print("[bold]DESCRIPTION:[/bold]")
    console.print("    Scans the immediate children of a directory for folders that contain")
    console.print("    a simflow.config file.  Presents the list and lets you exclude entries")
    console.print("    by number before writing a .cases.yml file (YAML) in the scanned directory.")
    console.print("    Re-running always replaces the previous .cases.yml file.")
    console.print()
    console.print("[bold]EXAMPLES:[/bold]")
    console.print("    case add                    # scan current directory")
    console.print("    case add --dir /scratch/me/project")
    console.print()
