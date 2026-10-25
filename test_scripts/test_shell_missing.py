"""`missing [DIR] [PATTERN]`: the numbers of a series like slice_xVor_{}.png with
no file; with no pattern, every numbered series in DIR. t1/t2 default to the files found, freq to the gcd of their gaps; zero
padding follows the files. It exits 1 when something is missing."""

import io

import pytest
from rich.console import Console

from shellkit import Runtime


@pytest.fixture
def rt(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    work = tmp_path / 'work'
    post = work / 'post'
    post.mkdir(parents=True)
    for n in range(3000, 5001, 50):
        if n not in (3350, 4100):
            (post / f'slice_xVor_{n}.png').write_text('x')
    (post / 'slice_xVor_4500.png').write_text('')            # empty
    (post / 'slice_xVor_3025.png').write_text('x')           # off the grid
    (post / 'slice_yVor_3350.png').write_text('x')           # another series
    for n in (10, 20, 40):
        (work / f'img_{n:04d}.jpg').write_text('x')
    monkeypatch.chdir(work)
    from src.cli.app import create_app
    return Runtime(create_app(),
                   console=Console(file=io.StringIO(), width=200, color_system=None),
                   err_console=Console(file=io.StringIO(), width=200, color_system=None))


def shown(rt):
    return rt.console.file.getvalue()


def test_lists_the_missing_with_a_summary(rt):
    assert rt.execute_line("missing 'post/slice_xVor_{}.png' --t1 3000 --t2 5000 --freq 50") == 1
    lines = [l.split() for l in shown(rt).splitlines() if l.split()]
    assert lines[:2] == [['missing', 'post/slice_xVor_3350.png'],
                         ['missing', 'post/slice_xVor_4100.png']]
    assert '2 of 41 missing · 3000..5000 every 50' in shown(rt)
    assert 'inferred' not in shown(rt)


def test_infers_the_range_and_freq(rt):
    rt.execute_line("cd post")
    assert rt.execute_line("missing slice_xVor_{}.png") == 1
    # 3025 is a file too, so the inferred step is 25
    assert '3000..5000 every 25 (inferred)' in shown(rt)


def test_directory_before_the_pattern(rt):
    assert rt.execute_line("missing post 'slice_xVor_{}.png' --freq 50") == 1
    assert rt.run_captured("missing post/ slice_xVor_{}.png --freq 50").split() == \
        ['post/slice_xVor_3350.png', 'post/slice_xVor_4100.png']
    assert rt.execute_line("missing --freq 50 nope slice_xVor_{}.png") == 1
    assert 'not a directory' in rt.err_console.file.getvalue()


def test_a_directory_alone_checks_every_series(rt, tmp_path):
    post = tmp_path / 'work' / 'post'
    for step in (100, 200, 400):
        for k in (0, 1):
            if (step, k) != (200, 1):
                (post / f'riser.{step}_{k}.out').write_text('x')
    (post / 'notes_1.txt').write_text('x')                   # a single file is no series
    assert rt.execute_line("missing post --freq 50") == 1
    text = shown(rt)
    summaries = [l for l in text.splitlines() if l.startswith(('✓', '✗'))]
    assert [l.split()[1] for l in summaries] == [
        'post/riser.{}_0.out', 'post/riser.{}_1.out', 'post/slice_xVor_{}.png']
    assert 'post/riser.{}_0.out  4 of 7 missing · 100..400 every 50' in text
    assert 'post/riser.{}_1.out  5 of 7 missing' in text
    assert 'post/riser.200_1.out' in text
    assert 'notes' not in text and 'yVor' not in text      # one file each


def test_no_arguments_is_here(rt):
    rt.execute_line("cd post")
    assert rt.run_captured("missing --freq 50 -q").splitlines() == [
        '✗ slice_xVor_{}.png  2 of 41 missing · 3000..5000 every 50']
    assert rt.run_captured("missing . --freq 50").split() == \
        ['slice_xVor_3350.png', 'slice_xVor_4100.png']


def test_empty_and_extra(rt):
    assert rt.execute_line("missing post/slice_xVor_{}.png --freq 50 --empty --extra") == 1
    rows = [l.split()[:2] for l in shown(rt).splitlines() if 'post/' in l]
    assert rows == [['extra', 'post/slice_xVor_3025.png'], ['missing', 'post/slice_xVor_3350.png'],
                    ['missing', 'post/slice_xVor_4100.png'], ['empty', 'post/slice_xVor_4500.png']]
    assert '2 of 41 missing, 1 empty, 1 extra' in shown(rt)


def test_in_a_pipe_just_the_names(rt):
    text = rt.run_captured("missing post/slice_xVor_{}.png --freq 50")
    assert text.split() == ['post/slice_xVor_3350.png', 'post/slice_xVor_4100.png']
    assert rt.run_captured("missing post/slice_xVor_{}.png --freq 50 -q").strip() \
        == '✗ 2 of 41 missing · 3000..5000 every 50'


def test_zero_padding_and_all_present(rt):
    assert rt.execute_line("missing img_{}.jpg --freq 10") == 1
    assert 'img_0030.jpg' in shown(rt)
    assert rt.execute_line("missing img_{}.jpg --t2 20 --freq=10") == 0
    assert '✓ all 2 present' in shown(rt)


def test_no_files_but_a_given_range(rt):
    assert rt.run_captured("missing nope_{}.png --t1 1 --t2 3").split() == \
        ['nope_1.png', 'nope_2.png', 'nope_3.png']
    assert rt.execute_line("missing nope_{}.png") == 1


@pytest.mark.parametrize('line, message', [
    ("missing img.jpg", 'needs one {}'),
    ("missing img_{}.jpg --freq 0", '--freq must be 1 or more'),
    ("missing img_{}.jpg --t1 x", 'needs a whole number'),
    ("missing img_{}.jpg --t1 50 --t2 10", 'is after'),
    ("missing img_{}.jpg --bogus", 'unknown option --bogus'),
    ("missing post a_{}.png b_{}.png", 'usage: missing'),
])
def test_errors(rt, line, message):
    assert rt.execute_line(line) == 2
    assert message in rt.err_console.file.getvalue()
