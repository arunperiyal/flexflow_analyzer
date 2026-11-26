"""`auto` judges a finished case's history when auto.steady_var is set (auto.md 13.24):
steady is a note, anything else needs the user, with the commands to run longer."""

import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from src.commands.auto.show import gather, resolve_cases
from src.core.auto.conf import AutoConfError

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def dummy(tmp_path, monkeypatch):
    root = tmp_path / 'dummy'
    subprocess.run([sys.executable, str(REPO / 'tools' / 'make_dummy.py'), '--root', str(root)],
                   check=True, capture_output=True)
    monkeypatch.setenv('PATH', f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv('FAKE_SLURM_DIR', str(root / 'slurm'))
    return root


def set_auto(dummy, **settings):
    path = dummy / 'bare' / '.cases.yml'
    data = yaml.safe_load(path.read_text())
    data.setdefault('auto', {}).update(settings)
    path.write_text(yaml.safe_dump(data))


def history(dummy, shape, case='case1'):
    """Rewrite the y displacement of every .othd of the case: shape(t) over tsId * 0.05."""
    for f in (dummy / 'bare' / case).rglob('*.othd'):
        text = f.read_text()
        out, step = [], None
        for line in text.splitlines():
            m = re.match(r'tsId (\d+)', line)
            if m:
                step = int(m.group(1))
            if re.match(r'^[-\d.e+]+ [-\d.e+]+ [-\d.e+]+$', line) and step is not None:
                line = f"0.0 {shape(step * 0.05):.8e} 0.0"
            out.append(line)
        f.write_text('\n'.join(out) + '\n')


def plan_of(dummy, case='case1'):
    results, _, problems = gather(resolve_cases(case, dummy / 'bare'), 'local')
    assert problems == []
    return {snap.name: plan for snap, plan in results}[case]


def texts(plan, kind):
    return [i.text for i in plan.items if i.kind == kind]


def test_off_by_default(dummy):
    history(dummy, lambda t: np.sin(2 * np.pi * t))
    assert not any('steady' in t for t in texts(plan_of(dummy), 'note') + texts(plan_of(dummy), 'needs'))


def test_a_steady_case_is_a_note(dummy):
    set_auto(dummy, steady_var='aleDisp_y', steady_last=1000)
    history(dummy, lambda t: np.sin(2 * np.pi * t / 2.0))
    plan = plan_of(dummy)
    assert any(t.startswith('aleDisp_y is steady over the last 1000 steps') for t in texts(plan, 'note'))
    assert not plan.needs_you


def test_a_growing_case_needs_you_with_the_commands(dummy):
    set_auto(dummy, steady_var='aleDisp_y', steady_last=1000)
    history(dummy, lambda t: (t / 50) * np.sin(2 * np.pi * t / 2.0))
    plan = plan_of(dummy)
    [text] = [t for t in texts(plan, 'needs') if t.startswith('aleDisp_y is not steady')]
    assert 'def time maxTime --case case1 --value 2000' in text
    assert 'run main restart --case case1 --time ' in text


def test_a_case_still_running_is_not_judged(dummy):
    set_auto(dummy, steady_var='aleDisp_y')
    history(dummy, lambda t: (t / 50) * np.sin(2 * np.pi * t / 2.0), case='case2')
    plan = plan_of(dummy, 'case2')
    assert plan.state != 'done'
    assert not any('steady' in t for t in texts(plan, 'needs') + texts(plan, 'note'))


def test_a_variable_the_case_does_not_have_needs_you(dummy):
    set_auto(dummy, steady_var='nonesuch')
    plan = plan_of(dummy)
    assert any('steady check of nonesuch could not be made' in t for t in texts(plan, 'needs'))


def test_too_few_cycles_is_too_short(dummy):
    set_auto(dummy, steady_var='aleDisp_y', steady_last=1000)
    history(dummy, lambda t: np.sin(2 * np.pi * t / 20.0))       # 2.5 cycles in 50 time units
    [text] = [t for t in texts(plan_of(dummy), 'needs') if 'aleDisp_y is' in t]
    assert 'too short' in text


def test_the_settings_are_checked(dummy):
    from src.core.auto.conf import read
    set_auto(dummy, steady_var='aleDisp_y', steady_last=1)
    with pytest.raises(AutoConfError, match='steady_last'):
        read(dummy / 'bare', 'local')
    set_auto(dummy, steady_last=500, steady_tol='x')
    with pytest.raises(AutoConfError, match='steady_tol'):
        read(dummy / 'bare', 'local')
    set_auto(dummy, steady_tol=0.1, steady_var=' ')
    with pytest.raises(AutoConfError, match='steady_var'):
        read(dummy / 'bare', 'local')
