"""`case check history --remote [NAME]`: the OTHD/OISD history here against its copy on the
remote, by size and md5 read now (src/core/transfer/history_check.py). Read-only."""

from pathlib import Path

from rich.markup import escape
from rich.table import Table


def _context_remote():
    from shellkit import current_runtime
    rt = current_runtime()
    return rt.get('remote') if rt else None


def print_history_remote(case_dir: Path, cfg, console, remote, parts) -> bool:
    """Print the comparison; True when every history file here has an identical copy."""
    from ....core import history
    from ....core.transfer.cloud import CloudError, open_for_folder, remote_name_for
    from ....core.transfer.history_check import compare_history

    remote = remote or _context_remote() or None
    problem = getattr(cfg, 'problem', None) or history.problem_of(case_dir)
    console.print("[bold]History vs remote[/bold]")
    try:
        used = remote_name_for(case_dir.parent, remote)
        cloud = open_for_folder(case_dir.parent, remote)
    except CloudError as e:
        console.print(f"  [red]✗[/red]  The remote was not looked at: {escape(str(e))}")
        console.print()
        return False
    try:
        console.print(f"  [dim]{escape(case_dir.name)}: othd_files/ and oisd_files/ against "
                      f"{escape(cloud.where)} ({escape(used or '')})[/dim]")
        try:
            result = compare_history(case_dir, problem, cloud, parts)
        except CloudError as e:
            console.print(f"  [red]✗[/red]  {escape(str(e))}")
            console.print()
            return False
    finally:
        cloud.close()
    rows = Table.grid(padding=(0, 2))
    rows.add_column(no_wrap=True)
    rows.add_column()
    names = lambda rels: ', '.join(Path(r).name for r in rels)
    if result.same:
        rows.add_row("[green]identical[/green]", names(result.same))
    if result.size_only:
        rows.add_row("[yellow]size only[/yellow]",
                     f"{names(result.size_only)}  [dim]the remote gave no md5[/dim]")
    for rel, why in result.differs.items():
        rows.add_row("[red]differs[/red]", f"{escape(rel)}: {escape(why)}")
    if result.not_there:
        rows.add_row("[red]not on the remote[/red]", names(result.not_there))
    if result.only_there:
        rows.add_row("[yellow]only on the remote[/yellow]",
                     f"{names(result.only_there)}  [dim]archive/ pruned here? "
                     f"`case download history --archive --case {escape(case_dir.name)}`[/dim]")
    console.print(rows)
    mark = "[green]✓[/green]" if result.ok else "[red]✗[/red]"
    console.print(f"  {mark} {escape(result.summary())}")
    console.print()
    return result.ok
