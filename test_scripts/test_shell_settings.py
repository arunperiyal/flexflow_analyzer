from unittest.mock import patch

from src.cli.interactive import InteractiveShell


class _MockConsole:
    def __init__(self):
        self.messages = []

    def print(self, *args, **kwargs):
        self.messages.append(" ".join(str(arg) for arg in args))


def _make_shell() -> InteractiveShell:
    shell = InteractiveShell.__new__(InteractiveShell)
    shell.console = _MockConsole()
    shell._settings = {}
    shell._save_settings = lambda: None
    shell._arm_session_timeout_alarm = lambda: None
    return shell


def test_set_timeout_updates_setting_and_deadline():
    shell = _make_shell()
    save_calls = []
    shell._save_settings = lambda: save_calls.append(True)

    with patch("src.cli.interactive.time.monotonic", return_value=100.0):
        shell._handle_set(["timeout", "20"])

    assert shell._settings["timeout_minutes"] == 20
    assert shell._session_timeout_minutes == 20
    assert shell._session_deadline_monotonic == 1300.0
    assert save_calls == [True]
    assert any("Session timeout set to" in msg for msg in shell.console.messages)


def test_set_timeout_without_value_shows_current():
    shell = _make_shell()
    shell._settings["timeout_minutes"] = 25

    shell._handle_set(["timeout"])

    assert any("session timeout:" in msg and "25" in msg for msg in shell.console.messages)


def test_set_timeout_rejects_non_positive_value():
    shell = _make_shell()

    shell._handle_set(["timeout", "0"])

    assert "timeout_minutes" not in shell._settings
    assert any("invalid timeout" in msg for msg in shell.console.messages)


def test_get_session_timeout_minutes_falls_back_to_default():
    shell = _make_shell()

    assert shell._get_session_timeout_minutes() == 15
    shell._settings["timeout_minutes"] = "bad"
    assert shell._get_session_timeout_minutes() == 15
    shell._settings["timeout_minutes"] = -5
    assert shell._get_session_timeout_minutes() == 15


def test_is_session_timeout_reached_checks_deadline():
    shell = _make_shell()
    shell._session_deadline_monotonic = 200.0

    with patch("src.cli.interactive.time.monotonic", return_value=199.9):
        assert shell._is_session_timeout_reached() is False

    with patch("src.cli.interactive.time.monotonic", return_value=200.1):
        assert shell._is_session_timeout_reached() is True
