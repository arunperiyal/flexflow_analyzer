from pathlib import Path

from src.cli.interactive import InteractiveShell


class TestLsColoring:
    def setup_method(self):
        self.shell = InteractiveShell.__new__(InteractiveShell)

    def test_shell_script_is_colored(self):
        formatted = self.shell._format_ls_file_name(Path("mainFlex.sh"))
        assert formatted == "[yellow]mainFlex.sh[/yellow]"

    def test_slurm_prefixed_file_is_colored(self):
        formatted = self.shell._format_ls_file_name(Path("slurm-123456.out"))
        assert formatted == "[yellow]slurm-123456.out[/yellow]"

    def test_existing_data_file_color_preserved(self):
        formatted = self.shell._format_ls_file_name(Path("riser.othd"))
        assert formatted == "[magenta]riser.othd[/magenta]"
