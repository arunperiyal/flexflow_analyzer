"""`auto show` and `auto apply` read the same list: plan.steps. For every dummy
case, each step's command is an Action line of the report, the files `apply`
sends are the files the plan lists, and what `apply --dry-run` says it will do
is what the steps say."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.commands.auto.apply import KINDS, _intended
from src.commands.auto.show import gather, resolve_cases
from src.core.auto.decide import AUTO_ONLY, TARGETS
from src.core.auto.report import build, commands

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope='module')
def plans(tmp_path_factory):
    root = tmp_path_factory.mktemp('steps') / 'dummy'
    subprocess.run([sys.executable, str(REPO / 'tools' / 'make_dummy.py'), '--root', str(root)],
                   check=True, capture_output=True)
    old = dict(os.environ)
    os.environ['PATH'] = f"{root / 'bin'}{os.pathsep}{old['PATH']}"
    os.environ['FAKE_SLURM_DIR'] = str(root / 'slurm')
    try:
        results, confs, problems = gather(resolve_cases('*', root / 'bare'), 'local')
    finally:
        os.environ.clear()
        os.environ.update(old)
    assert results and not problems
    return [(snap, plan, build(snap, plan, confs[snap.dir.parent])) for snap, plan in results]


def test_the_dummy_cases_have_steps_of_every_kind(plans):
    kinds = {s.kind for _, plan, _ in plans for s in plan.steps}
    keys = {s.key for _, plan, _ in plans for s in plan.steps}
    assert kinds == set(KINDS) | {'check', 'delete'}       # apply carries out KINDS only, so far
    assert {'organise', 'upload-history', 'post', 'upload-plt', 'upload-inputs'} <= keys
    assert all(s.target in TARGETS for _, plan, _ in plans for s in plan.steps)


def test_every_step_is_an_action_line_of_the_report(plans):
    for snap, plan, sections in plans:
        actions = [a for sec in sections for a in sec.actions]
        for step in plan.steps:
            assert step.command in actions, (snap.name, step.command)
        # and a step that is a command the user can type is in `auto commands`
        typed = [s.command for s in plan.steps if not s.command.startswith(AUTO_ONLY)]
        assert set(typed) <= set(commands(sections)), snap.name


def test_no_executable_action_of_the_report_is_missing_from_the_steps(plans):
    # what apply does not carry out: deleting (a later stage), bringing history back
    # from the remote, and restarting a stopped run -- those are for the user
    for snap, plan, sections in plans:
        steps = {s.command for s in plan.steps}
        for line in commands(sections):
            if line in steps:
                continue
            assert line.startswith(('case download history', 'run main restart')), (snap.name, line)


def test_the_files_apply_sends_are_the_files_the_plan_lists(plans):
    for snap, plan, _ in plans:
        assert plan.to_send() == plan.uploads, snap.name
        # no file belongs to two steps
        listed = [rel for s in plan.steps for rel in s.files]
        assert len(listed) == len(set(listed)), snap.name


def test_what_apply_says_it_will_do_is_what_the_steps_say(plans):
    for snap, plan, _ in plans:
        said = {kind: text for kind, text in _intended(plan, set(KINDS)) if kind != 'detail'}
        assert ('history' in said) == bool(plan.due('history')), snap.name
        assert ('upload' in said) == bool(plan.to_send()), snap.name
        assert ('post' in said) == bool(plan.due('post')), snap.name
        if 'history' in said:
            assert plan.due('history')[0].command == f"case {said['history']}".replace(
                'organise history', f'organise history {snap.name}', 1)
        if 'upload' in said:
            assert said['upload'].startswith(f"{len(plan.to_send())} files")
        if 'post' in said:
            # the first post step, with the same mode and window
            first = plan.due('post')[0].command
            mode, t1, t2 = said['post'].split()[2], said['post'].split()[4], said['post'].split()[6]
            assert first.startswith(f"run post {mode} {snap.name} --t1 {t1} --t2 {t2}")
        # --only narrows it to the kinds named
        assert [k for k, _ in _intended(plan, {'post'}) if k != 'detail'] == \
            (['post'] if plan.due('post') else [])
