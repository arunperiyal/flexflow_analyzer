"""Tests for `case upload --files`.

--files carries the small things that describe a case rather than its data, so
these check what the globs resolve to, that a case root's subdirectories are
never swept in, and that asking for files alone does not drag the default data
directories along with them.
"""

import argparse
from unittest.mock import MagicMock

import pytest

from src.commands.case.download_impl.command import (CaseUploadCommand,
                                                     DEFAULT_UPLOAD_FILES)


@pytest.fixture
def uploader():
    return CaseUploadCommand()


@pytest.fixture
def case(tmp_path):
    """A case root holding definition files, maps, and data directories."""
    (tmp_path / "simflow.config").write_text("problem = riser\n")
    (tmp_path / "riser.def").write_text("solve { }\n")
    (tmp_path / "riser.geo").write_text("geometry\n")
    (tmp_path / "othd.cyl_nodes.map").write_text("row,node,x,y,z\n0,2,0,0,0\n")
    (tmp_path / "othd.tip_nodes.map").write_text("row,node,x,y,z\n0,18,1,0,0\n")
    (tmp_path / "riser.crd").write_text("1 0 0 0\n")          # big, deliberately excluded
    for name in ("binary", "othd_files"):
        d = tmp_path / name
        d.mkdir()
        (d / "riser.100.plt").write_text("data")
        (d / "nested.map").write_text("should not be matched")  # only the root counts
    return tmp_path


class TestParseFiles:
    """--files takes defaults on its own, or explicit comma-separated globs."""

    def test_absent_means_no_files(self, uploader):
        assert uploader.parse_files(None) == []
        assert uploader.parse_files(False) == []

    def test_bare_flag_takes_the_defaults(self, uploader):
        assert uploader.parse_files(True) == DEFAULT_UPLOAD_FILES
        assert "simflow.config" in DEFAULT_UPLOAD_FILES
        assert "*.map" in DEFAULT_UPLOAD_FILES

    def test_explicit_patterns_are_split(self, uploader):
        assert uploader.parse_files("*.map, riser.def") == ["*.map", "riser.def"]

    def test_empty_string_falls_back_to_the_defaults(self, uploader):
        assert uploader.parse_files("  ,  ") == DEFAULT_UPLOAD_FILES


class TestResolveFiles:
    """Patterns resolve against the case root only."""

    def test_defaults_pick_up_definitions_and_maps(self, uploader, case):
        assert uploader.resolve_files(str(case), DEFAULT_UPLOAD_FILES) == [
            "othd.cyl_nodes.map", "othd.tip_nodes.map",
            "riser.def", "riser.geo", "simflow.config",
        ]

    def test_the_mesh_file_is_not_swept_in(self, uploader, case):
        # riser.crd is the file othd maps exist to make unnecessary
        assert "riser.crd" not in uploader.resolve_files(str(case), DEFAULT_UPLOAD_FILES)

    def test_subdirectories_are_not_searched(self, uploader, case):
        # binary/nested.map matches *.map but lives below the root
        assert uploader.resolve_files(str(case), ["*.map"]) == [
            "othd.cyl_nodes.map", "othd.tip_nodes.map"]

    def test_a_pattern_matching_nothing_yields_nothing(self, uploader, case):
        assert uploader.resolve_files(str(case), ["*.nope"]) == []

    def test_overlapping_patterns_do_not_duplicate(self, uploader, case):
        assert uploader.resolve_files(str(case), ["*.map", "othd.*.map"]) == [
            "othd.cyl_nodes.map", "othd.tip_nodes.map"]


class TestFilesOnlySemantics:
    """--files without --dir means the files, not the default data directories."""

    @staticmethod
    def directories_for(uploader, files, dir_arg):
        patterns = uploader.parse_files(files)
        return [] if (patterns and not dir_arg) else uploader.parse_directories(dir_arg)

    def test_files_alone_skips_the_default_directories(self, uploader):
        assert self.directories_for(uploader, True, None) == []

    def test_no_flags_keeps_the_default_directories(self, uploader):
        assert self.directories_for(uploader, None, None) == [
            "othd_files", "oisd_files", "binary"]

    def test_both_flags_send_both(self, uploader):
        assert self.directories_for(uploader, True, "binary") == ["binary"]


class TestUploadFiles:
    """The transfer itself, against a stubbed SSH connection."""

    def test_uploads_every_matched_file_into_the_case_root(self, uploader, case):
        ssh = MagicMock()
        ssh.remote_path_exists.return_value = True
        assert uploader.upload_files(ssh, "/remote/BR0", str(case),
                                     DEFAULT_UPLOAD_FILES) is True
        sent = {call.args[1] for call in ssh.upload_file.call_args_list}
        assert sent == {
            "/remote/BR0/simflow.config", "/remote/BR0/riser.def",
            "/remote/BR0/riser.geo", "/remote/BR0/othd.cyl_nodes.map",
            "/remote/BR0/othd.tip_nodes.map",
        }

    def test_matching_nothing_is_not_a_failure(self, uploader, case):
        ssh = MagicMock()
        ssh.remote_path_exists.return_value = True
        assert uploader.upload_files(ssh, "/remote/BR0", str(case), ["*.nope"]) is True
        ssh.upload_file.assert_not_called()

    def test_missing_remote_directory_fails_without_force(self, uploader, case):
        ssh = MagicMock()
        ssh.remote_path_exists.return_value = False
        assert uploader.upload_files(ssh, "/remote/BR0", str(case),
                                     DEFAULT_UPLOAD_FILES) is False
        ssh.upload_file.assert_not_called()

    def test_force_creates_the_remote_directory(self, uploader, case):
        ssh = MagicMock()
        ssh.remote_path_exists.return_value = False
        ssh.make_remote_dir.return_value = True
        assert uploader.upload_files(ssh, "/remote/BR0", str(case),
                                     DEFAULT_UPLOAD_FILES, force=True) is True
        ssh.make_remote_dir.assert_called_once_with("/remote/BR0")
        assert ssh.upload_file.call_count == 5


class TestResumeState:
    """File patterns have to survive into the resumable state, or a resume drops them."""

    def test_patterns_are_recorded(self, uploader):
        state = uploader._build_transfer_state(
            "upload", "server", "/remote", "CS4", [{"name": "CS4", "path": "/l/CS4"}],
            ["binary"], False, False, ["*.map"])
        assert state["file_patterns"] == ["*.map"]

    def test_absent_patterns_record_as_empty(self, uploader):
        state = uploader._build_transfer_state(
            "upload", "server", "/remote", "CS4", [{"name": "CS4", "path": "/l/CS4"}],
            ["binary"], False, False)
        assert state["file_patterns"] == []

    def test_file_target_has_its_own_key(self, uploader):
        assert (uploader._target_key("/l/CS4", "__files__")
                != uploader._target_key("/l/CS4", "binary"))
