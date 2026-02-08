"""Execute run check command - Validate case directory."""

import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box


def execute_check(args):
    """Execute run check command to validate case directory."""

    # Handle help flag
    if hasattr(args, 'help') and args.help:
        show_check_help()
        return

    # Get case directory
    case_dir = get_case_directory(args)
    if not case_dir:
        return

    console = Console()
    verbose = hasattr(args, 'verbose') and args.verbose

    # Validate case directory
    console.print()
    console.print(f"[bold cyan]Validating case directory:[/bold cyan] {case_dir.name}")
    console.print()

    results = {}

    # 1. Check required files
    results['files'] = check_required_files(case_dir, verbose, console)

    # 2. Check required directories
    results['directories'] = check_required_directories(case_dir, verbose, console)

    # 3. Check job scripts
    results['scripts'] = check_job_scripts(case_dir, verbose, console)

    # 4. Check executable paths (if verbose)
    if verbose:
        results['executables'] = check_executable_paths(case_dir, verbose, console)

    # Display summary
    display_summary(results, console)


def get_case_directory(args):
    """Get and validate case directory from args or context."""
    from src.cli.interactive import InteractiveShell

    case_dir = None

    # Try to get from args
    if hasattr(args, 'case') and args.case:
        case_dir = Path(args.case)
    # Try to get from context (if in interactive mode)
    elif hasattr(InteractiveShell, '_instance') and InteractiveShell._instance:
        shell = InteractiveShell._instance
        if shell._current_case:
            case_dir = Path(shell._current_case)

    if not case_dir:
        print("Error: Case directory not specified")
        print("\nUsage: run check <case_directory>")
        print("   or: use case:<directory>, then run check")
        return None

    if not case_dir.exists():
        print(f"Error: Case directory not found: {case_dir}")
        return None

    if not case_dir.is_dir():
        print(f"Error: Not a directory: {case_dir}")
        return None

    return case_dir.resolve()


def check_required_files(case_dir, verbose, console):
    """Check for required files in case directory."""
    required_files = {
        'simflow.config': 'Simulation configuration',
        '*.geo': 'Geometry file for mesh generation',
        '*.def': 'Problem definition file',
        '*.srfs': 'Surface definitions',
        '*.vols': 'Volume definitions'
    }

    results = []

    for pattern, description in required_files.items():
        if '*' in pattern:
            # Glob pattern
            matches = list(case_dir.glob(pattern))
            if matches:
                for match in matches:
                    results.append(('✓', match.name, description, 'green'))
                    if verbose:
                        console.print(f"  [green]✓[/green] {match.name} - {description}")
            else:
                results.append(('✗', pattern, description, 'red'))
                if verbose:
                    console.print(f"  [red]✗[/red] {pattern} - {description} [dim](not found)[/dim]")
        else:
            # Exact filename
            file_path = case_dir / pattern
            if file_path.exists():
                results.append(('✓', pattern, description, 'green'))
                if verbose:
                    console.print(f"  [green]✓[/green] {pattern} - {description}")
            else:
                results.append(('✗', pattern, description, 'red'))
                if verbose:
                    console.print(f"  [red]✗[/red] {pattern} - {description} [dim](not found)[/dim]")

    return results


def check_required_directories(case_dir, verbose, console):
    """Check for required directories."""
    required_dirs = {
        'othd_files': 'OTHD output files storage',
        'oisd_files': 'OISD output files storage',
        'binary': 'Binary data files',
    }

    # Check for rundir in simflow.config
    config_file = case_dir / 'simflow.config'
    if config_file.exists():
        try:
            with open(config_file) as f:
                for line in f:
                    if 'dir' in line and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        if key == 'dir':
                            output_dir = value.strip().strip('"').strip("'")
                            output_dir = output_dir.replace('./', '')
                            if output_dir and output_dir != 'dir':
                                required_dirs[output_dir] = 'Output directory (from simflow.config)'
        except Exception:
            pass

    results = []

    for dir_name, description in required_dirs.items():
        dir_path = case_dir / dir_name
        if dir_path.exists() and dir_path.is_dir():
            results.append(('✓', dir_name + '/', description, 'green'))
            if verbose:
                console.print(f"  [green]✓[/green] {dir_name}/ - {description}")
        else:
            results.append(('✗', dir_name + '/', description, 'yellow'))
            if verbose:
                console.print(f"  [yellow]✗[/yellow] {dir_name}/ - {description} [dim](will be created)[/dim]")

    return results


def check_job_scripts(case_dir, verbose, console):
    """Check for job scripts."""
    # Check for scripts in priority order
    script_checks = [
        (['preFlex.sh', 'pre.sh', 'preprocessing.sh'], 'Preprocessing script'),
        (['mainFlex.sh', 'submit.sh', 'main.sh'], 'Main simulation script'),
        (['postFlex.sh', 'PostSubmit.sh', 'post.sh'], 'Postprocessing script'),
    ]

    results = []

    for script_names, description in script_checks:
        found = None
        for script_name in script_names:
            script_path = case_dir / script_name
            if script_path.exists():
                found = script_name
                # Check if executable
                is_executable = os.access(script_path, os.X_OK)
                if is_executable:
                    results.append(('✓', script_name, description + ' (executable)', 'green'))
                    if verbose:
                        console.print(f"  [green]✓[/green] {script_name} - {description} [dim](executable)[/dim]")
                else:
                    results.append(('⚠', script_name, description + ' (not executable)', 'yellow'))
                    if verbose:
                        console.print(f"  [yellow]⚠[/yellow] {script_name} - {description} [dim](not executable, run: chmod +x {script_name})[/dim]")
                break

        if not found:
            expected = script_names[0]
            results.append(('✗', expected, description, 'red'))
            if verbose:
                console.print(f"  [red]✗[/red] {expected} - {description} [dim](not found, looking for: {', '.join(script_names)})[/dim]")

    return results


def check_executable_paths(case_dir, verbose, console):
    """Check if executable paths in scripts are valid."""
    executables_to_check = ['gmsh', 'simGmshCnvt', 'mpiSimflow', 'simPlt', 'simPlt2Bin']

    # Find all .sh files
    scripts = list(case_dir.glob('*.sh'))

    results = []

    if not scripts:
        return results

    console.print()
    console.print("[bold]Checking executable paths in scripts:[/bold]")

    for executable in executables_to_check:
        found_in_scripts = False
        valid_path = False

        # Check if mentioned in any script
        for script in scripts:
            try:
                with open(script) as f:
                    content = f.read()
                    if executable in content:
                        found_in_scripts = True
                        # Try to find if it's a valid path
                        import subprocess
                        result = subprocess.run(['which', executable], capture_output=True, text=True)
                        if result.returncode == 0:
                            valid_path = True
                            path = result.stdout.strip()
                            results.append(('✓', executable, f'Found in PATH: {path}', 'green'))
                            console.print(f"  [green]✓[/green] {executable} - [dim]{path}[/dim]")
                        break
            except Exception:
                pass

        if found_in_scripts and not valid_path:
            results.append(('⚠', executable, 'Mentioned in scripts but not in PATH', 'yellow'))
            console.print(f"  [yellow]⚠[/yellow] {executable} - [dim]mentioned in scripts but not in PATH[/dim]")
        elif not found_in_scripts:
            results.append(('—', executable, 'Not mentioned in scripts', 'dim'))
            console.print(f"  [dim]—[/dim] {executable} - [dim]not mentioned in scripts[/dim]")

    return results


def display_summary(results, console):
    """Display validation summary."""
    console.print()
    console.print("[bold cyan]Validation Summary:[/bold cyan]")
    console.print()

    # Count results
    total_checks = 0
    passed = 0
    warnings = 0
    errors = 0

    for category, items in results.items():
        for item in items:
            total_checks += 1
            if item[0] == '✓':
                passed += 1
            elif item[0] == '✗':
                errors += 1
            elif item[0] in ['⚠', '—']:
                warnings += 1

    # Create summary table
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("[green]✓ Passed[/green]", str(passed))
    table.add_row("[yellow]⚠ Warnings[/yellow]", str(warnings))
    table.add_row("[red]✗ Errors[/red]", str(errors))
    table.add_row("[dim]Total checks[/dim]", str(total_checks))

    console.print(table)
    console.print()

    # Overall status
    if errors == 0:
        console.print("[bold green]✓ Case directory is valid![/bold green]")
        console.print()
        console.print("[dim]You can now submit jobs with:[/dim]")
        console.print("[dim]  run pre     # Submit preprocessing[/dim]")
        console.print("[dim]  run main    # Submit main simulation[/dim]")
        console.print("[dim]  run post    # Submit postprocessing[/dim]")
    else:
        console.print("[bold red]✗ Case directory has errors![/bold red]")
        console.print()
        console.print("[dim]Please fix the errors before submitting jobs.[/dim]")
        console.print("[dim]Run with --verbose for more details:[/dim]")
        console.print("[dim]  run check --verbose[/dim]")

    console.print()


def show_check_help():
    """Show help for run check command."""
    from src.utils.colors import Colors

    print(f"""
{Colors.BOLD}{Colors.CYAN}Run Check - Validate Case Directory{Colors.RESET}

Verify that the case directory has all required files and structure.

{Colors.BOLD}USAGE:{Colors.RESET}
    run check [case_directory] [options]

{Colors.BOLD}OPTIONS:{Colors.RESET}
    {Colors.YELLOW}-v, --verbose{Colors.RESET}  Show detailed validation results
    {Colors.YELLOW}-h, --help{Colors.RESET}     Show this help message

{Colors.BOLD}EXAMPLES:{Colors.RESET}
    # Check specific case
    run check Case001

    # Check with detailed output
    run check Case001 --verbose

    # Check current case (from context)
    use case:Case001
    run check

{Colors.BOLD}WHAT IT CHECKS:{Colors.RESET}
    {Colors.GREEN}Files:{Colors.RESET}
    • simflow.config - Simulation configuration
    • *.geo - Geometry file for mesh generation
    • *.def - Problem definition file
    • *.srfs - Surface definitions
    • *.vols - Volume definitions

    {Colors.GREEN}Directories:{Colors.RESET}
    • othd_files/ - OTHD output storage
    • oisd_files/ - OISD output storage
    • binary/ - Binary data files
    • Output directory (from simflow.config)

    {Colors.GREEN}Job Scripts:{Colors.RESET}
    • preFlex.sh (or pre.sh, preprocessing.sh)
    • mainFlex.sh (or submit.sh, main.sh)
    • postFlex.sh (or PostSubmit.sh, post.sh)

    {Colors.GREEN}Executables (with --verbose):{Colors.RESET}
    • gmsh - Mesh generator
    • simGmshCnvt - Mesh converter
    • mpiSimflow - Main simulation
    • simPlt - PLT file generator
    • simPlt2Bin - Binary PLT converter

{Colors.BOLD}OUTPUT:{Colors.RESET}
    • {Colors.GREEN}✓{Colors.RESET} - Check passed
    • {Colors.YELLOW}⚠{Colors.RESET} - Warning (non-critical)
    • {Colors.RED}✗{Colors.RESET} - Error (must be fixed)
""")
