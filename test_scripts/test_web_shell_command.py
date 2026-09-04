"""Tests for `web start` / `web stop` in the interactive shell (Phase 3).

FlexFlowApp.run() ignores argv and always starts the shell, so these live in
InteractiveShell.handle_shell_command() rather than as an argparse command
(see src/cli/interactive.py:_handle_web_command).
"""

import time
import urllib.error
import urllib.request

import pytest

from src.cli.interactive import InteractiveShell

PORT = 18099


class _MockConsole:
    def __init__(self):
        self.messages = []

    def print(self, *args, **kwargs):
        self.messages.append(" ".join(str(a) for a in args))


def _make_shell(tmp_path):
    shell = InteractiveShell.__new__(InteractiveShell)
    shell.console = _MockConsole()
    shell._current_dir = tmp_path
    shell._web_server = None
    shell._web_server_thread = None
    shell._web_server_url = None
    return shell


def _get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=2) as resp:
        return resp.status


@pytest.fixture
def shell(tmp_path):
    s = _make_shell(tmp_path)
    yield s
    if s._web_server is not None:
        s._web_server.shutdown()
        s._web_server_thread.join(timeout=5)


def test_web_start_serves_and_web_stop_shuts_it_down(shell):
    handled = shell.handle_shell_command(f"web start --port {PORT}")
    assert handled is True
    assert any("running at" in m for m in shell.console.messages)

    time.sleep(0.2)
    assert _get('/api/cases') == 200

    handled = shell.handle_shell_command("web stop")
    assert handled is True
    assert any("stopped" in m.lower() for m in shell.console.messages)

    time.sleep(0.2)
    with pytest.raises(urllib.error.URLError):
        _get('/api/cases')


def test_web_start_twice_reports_already_running(shell):
    shell.handle_shell_command(f"web start --port {PORT}")
    time.sleep(0.2)
    before = len(shell.console.messages)
    shell.handle_shell_command(f"web start --port {PORT}")
    assert any("already running" in m for m in shell.console.messages[before:])


def test_web_stop_when_not_running_says_so(shell):
    handled = shell.handle_shell_command("web stop")
    assert handled is True
    assert any("not running" in m.lower() for m in shell.console.messages)


def test_web_start_rejects_a_missing_root(shell):
    handled = shell.handle_shell_command(f"web start --root /no/such/dir --port {PORT}")
    assert handled is True
    assert shell._web_server is None
    assert any("Not a directory" in m for m in shell.console.messages)


def test_web_with_no_args_shows_usage(shell):
    handled = shell.handle_shell_command("web")
    assert handled is True
    assert any("Usage" in m for m in shell.console.messages)


def test_web_unknown_subcommand(shell):
    handled = shell.handle_shell_command("web frobnicate")
    assert handled is True
    assert any("Unknown web subcommand" in m for m in shell.console.messages)
