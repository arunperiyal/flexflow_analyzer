"""Tests for the help `remote` shows when a subcommand is given nothing to do.

A bare `remote add` used to answer "Error: remote name is required", which says
what is missing but not what the command wants -- and `remote add -h` showed the
group help, so there was nowhere to read the flags. These check that each
subcommand now answers with its own help, and that an incomplete command still
names what is missing before printing it.
"""

import argparse

import pytest

from src.commands.remote.remote_impl import command as remote_cmd


def run(capsys, **fields):
    """Execute a remote command, returning (stdout, exit code or None)."""
    args = argparse.Namespace(help=False, **fields)
    code = None
    try:
        remote_cmd.execute_remote(args)
    except SystemExit as exc:
        code = exc.code
    return capsys.readouterr().out, code


class TestBareSubcommand:
    """A subcommand with no arguments is a request for help, not a mistake."""

    @pytest.mark.parametrize("subcommand, heading", [
        ('add',      'remote add'),
        ('modify',   'remote modify'),
        ('delete',   'remote delete'),
        ('set-path', 'remote set-path'),
    ])
    def test_prints_its_own_help(self, capsys, subcommand, heading):
        out, code = run(capsys, remote_subcommand=subcommand, name=None,
                        user=None, ip=None, password=None, port=None, path=None)
        assert heading in out
        assert code == 1                      # incomplete, so not a success

    def test_no_error_line_when_nothing_was_given(self, capsys):
        """Nothing was asked for, so there is nothing to complain about."""
        out, _ = run(capsys, remote_subcommand='add', name=None, user=None,
                     ip=None, password=None, port=None, path=None)
        assert 'Error' not in out


class TestHelpFlag:
    """-h on a subcommand shows that subcommand, not the group."""

    @pytest.mark.parametrize("subcommand, heading", [
        ('add',      'remote add — Add a remote machine'),
        ('modify',   'remote modify — Update'),
        ('delete',   'remote delete — Delete'),
        ('list',     'remote list — Show'),
        ('set-path', 'remote set-path — Set'),
    ])
    def test_shows_the_subcommand_help(self, capsys, subcommand, heading):
        args = argparse.Namespace(remote_subcommand=subcommand, help=True)
        remote_cmd.execute_remote(args)
        assert heading in capsys.readouterr().out

    def test_group_help_without_a_subcommand(self, capsys):
        args = argparse.Namespace(remote_subcommand=None, help=True)
        remote_cmd.execute_remote(args)
        out = capsys.readouterr().out
        assert 'remote — Manage remote machines' in out
        assert 'set-path' in out              # the subcommands are listed


class TestIncompleteCommand:
    """Something was asked for, so say what is missing before the help."""

    def test_add_names_every_missing_flag(self, capsys):
        out, code = run(capsys, remote_subcommand='add', name='hpc1', user=None,
                        ip=None, password=None, port=22, path=None)
        assert '--user, --ip, --password are required' in out
        assert 'remote add' in out            # the help follows the error
        assert code == 1

    def test_add_names_only_what_is_missing(self, capsys):
        out, _ = run(capsys, remote_subcommand='add', name='hpc1', user='john',
                     ip='192.168.1.100', password=None, port=22, path=None)
        assert '--password is required' in out
        assert '--user' not in out.split('Error')[1].split('\n')[0]

    def test_add_without_a_name_says_so(self, capsys):
        out, code = run(capsys, remote_subcommand='add', name=None, user='john',
                        ip='192.168.1.100', password='secret', port=22, path=None)
        assert 'remote name is required' in out
        assert code == 1

    def test_modify_with_a_name_but_no_fields(self, capsys, monkeypatch):
        """The remote exists; there is just nothing to change on it."""
        config = argparse.Namespace(
            get_remote=lambda name: {'user': 'john', 'ip': '10.0.0.7',
                                     'port': 22, 'path': '/cases'})
        monkeypatch.setattr(remote_cmd, 'get_remote_config', lambda: config)

        out, code = run(capsys, remote_subcommand='modify', name='hpc1',
                        user=None, ip=None, password=None, port=None)
        assert 'at least one field' in out
        assert 'remote modify' in out
        assert code == 1

    def test_set_path_without_the_path(self, capsys):
        out, code = run(capsys, remote_subcommand='set-path', name='hpc1',
                        path=None)
        assert '--path is required' in out
        assert code == 1
