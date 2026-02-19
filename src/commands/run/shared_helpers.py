"""Shared helper functions for run subcommands."""

from pathlib import Path


def apply_partition_header(script_path: Path, partition: str, script_type: str, console) -> bool:
    """
    Replace the #SBATCH header block in *script_path* with the contents of
    src/templates/scripts/headers/<partition>.header.

    Args:
        script_path: Path to the job script file
        partition: Partition name (e.g. 'shared', 'medium')
        script_type: Script type ('pre', 'main', 'post') for {SCRIPT_TYPE} substitution
        console: Rich console for warnings

    Returns:
        True if a header file was found and applied, False otherwise.
    """
    # Locate the header file relative to this source file
    headers_dir = Path(__file__).parent.parent.parent / 'templates' / 'scripts' / 'headers'
    header_file = headers_dir / f'{partition}.header'

    if not header_file.exists():
        return False

    # Read header template and substitute {CASE_NAME} and {SCRIPT_TYPE}
    case_name = script_path.parent.name
    header_text = header_file.read_text()
    header_text = header_text.replace('{CASE_NAME}', case_name)
    header_text = header_text.replace('{SCRIPT_TYPE}', script_type)

    # Read the script and replace its #SBATCH block
    script_text = script_path.read_text()
    lines = script_text.splitlines(keepends=True)

    # Find the span of #SBATCH lines (may start after #!/bin/bash)
    sbatch_start = None
    sbatch_end = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#SBATCH'):
            if sbatch_start is None:
                sbatch_start = i
            sbatch_end = i

    if sbatch_start is None:
        console.print(f"[yellow]Warning: no #SBATCH lines found in {script_path.name} — header not applied[/yellow]")
        return False

    new_lines = (
        lines[:sbatch_start]
        + [header_text if header_text.endswith('\n') else header_text + '\n']
        + lines[sbatch_end + 1:]
    )
    script_path.write_text(''.join(new_lines))
    return True
