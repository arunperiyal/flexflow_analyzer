"""`def freq [out|rst] [value]`: outFreq of outputSimulation{} and outputRestart{}."""

import argparse
import shutil
from pathlib import Path

import pytest

from src.commands.def_impl.command import execute_freq
from src.core.def_config import DefConfig

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'standard' / 'riser.def'


@pytest.fixture
def case(tmp_path):
    shutil.copy(EXAMPLE, tmp_path / 'riser.def')
    return tmp_path


def run(case, kind=None, value=None):
    return execute_freq(argparse.Namespace(case=str(case), kind=kind, value=value, help=False))


def text(capsys):
    return ' '.join(capsys.readouterr().out.split())


def test_reads_both_frequencies(case):
    cfg = DefConfig(case / 'riser.def')
    assert (cfg.output_frequency, cfg.restart_frequency) == (100, 100)


def test_show_both_with_files_over_max_time_steps(case, capsys):
    assert run(case) == 0
    out = text(capsys)
    assert 'outputSimulation{} 100 50' in out and 'outputRestart{} 100 50' in out


def test_show_one(case, capsys):
    assert run(case, 'rst') == 0
    assert 'outputRestart.outFreq = 100' in text(capsys)


def test_set_restart_leaves_output_and_the_rest_alone(case, capsys):
    before = (case / 'riser.def').read_text()
    assert run(case, 'rst', '500') == 0
    assert '100 → 500' in text(capsys)
    cfg = DefConfig(case / 'riser.def')
    assert (cfg.output_frequency, cfg.restart_frequency) == (100, 500)
    after = (case / 'riser.def').read_text()
    assert after.replace('outFreq\t\t\t= 500', 'outFreq\t\t\t= 100') == before


def test_set_output(case):
    assert run(case, 'out', '50') == 0
    assert DefConfig(case / 'riser.def').output_frequency == 50


def test_not_a_multiple_is_noted(case, capsys):
    assert run(case, 'out', '300') == 0
    assert 'not a multiple of 300' in text(capsys)


@pytest.mark.parametrize('value', ['0', '-5', '2.5', 'often'])
def test_rejects_a_bad_frequency(case, capsys, value):
    assert run(case, 'out', value) == 1
    assert 'positive whole number' in text(capsys)
    assert DefConfig(case / 'riser.def').output_frequency == 100


def test_rejects_an_unknown_kind(case, capsys):
    assert run(case, 'restart') == 1
    assert "Expected 'out' or 'rst'" in text(capsys)


def test_missing_block(tmp_path, capsys):
    (tmp_path / 'riser.def').write_text('outputSimulation{\n    outFreq = 10\n}\n')
    assert run(tmp_path, 'rst', '20') == 1
    assert 'not found in outputRestart{}' in text(capsys)
    assert run(tmp_path) == 0
    assert '(not set)' in text(capsys)


def test_an_expression_is_shown_as_written(tmp_path, capsys):
    (tmp_path / 'riser.def').write_text(
        'define{\n    variable = F\n    value = 25\n}\n'
        'timeSteppingControl{\n    maxTimeSteps = 100\n}\n'
        'outputSimulation{\n    outFreq = 2*F\n}\n')
    cfg = DefConfig(tmp_path / 'riser.def')
    assert cfg.output_frequency == '2*F'
    assert run(tmp_path) == 0
    assert '2*F 2' in text(capsys)


def test_time_stepping_edit_still_works(case):
    cfg = DefConfig(case / 'riser.def')
    assert cfg.set_time_stepping_control('maxTimeSteps', 7000)
    assert cfg.max_time_steps == 7000
    assert DefConfig(case / 'riser.def').restart_frequency == 100
