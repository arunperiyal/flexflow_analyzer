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


# --- missing [case] --dir A,B: the case's render directories, view by view ----

@pytest.fixture
def case(rt, tmp_path):
    """work/C1/<name>/<view>/<name>_<step>.png, the way `field render` files them."""
    c1 = tmp_path / 'work' / 'C1'
    for name, views, gaps in (('slice_xVor', ('front', 'top'), {'front': (150,), 'top': ()}),
                              ('slice_zVor_yplane', ('view',), {'view': (100, 200)})):
        for view in views:
            d = c1 / name / view
            d.mkdir(parents=True)
            for t in range(50, 301, 50):
                if t not in gaps[view]:
                    (d / f'{name}_{t}.png').write_text('x')
    (c1 / 'slice_xVor' / 'slice_xVor_50.vtp').write_text('x')        # one file: no series
    return c1


def test_dir_uses_the_case_context(rt, case):
    assert rt.execute_line("use case:C1") == 0
    text = rt.run_captured("missing --dir slice_xVor,slice_zVor_yplane --freq 50")
    assert text.split() == ['C1/slice_xVor/front/slice_xVor_150.png',
                            'C1/slice_zVor_yplane/view/slice_zVor_yplane_100.png',
                            'C1/slice_zVor_yplane/view/slice_zVor_yplane_200.png']
    assert rt.execute_line("missing --dir slice_xVor,slice_zVor_yplane --freq 50") == 1


def test_dir_summaries_per_view(rt, case):
    assert rt.execute_line("missing C1 --dir slice_xVor -q") == 1
    lines = rt.run_captured("missing C1 --dir=slice_xVor -q").splitlines()
    assert lines == ['✗ C1/slice_xVor/front/slice_xVor_{}.png  1 of 6 missing · 50..300 every 50 (inferred)',
                     '✓ C1/slice_xVor/top/slice_xVor_{}.png  all 6 present · 50..300 every 50 (inferred)']


def test_dir_with_a_pattern(rt, case):
    text = rt.run_captured("missing C1 'slice_xVor_{}.png' --dir slice_xVor,slice_zVor_yplane --freq 50")
    assert text.split() == ['C1/slice_xVor/front/slice_xVor_150.png']
    assert 'no' in rt.err_console.file.getvalue() and 'slice_zVor_yplane/' in rt.err_console.file.getvalue()


def test_dir_without_a_case_is_here(rt, case):
    rt.execute_line("cd C1")
    assert rt.run_captured("missing --dir slice_zVor_yplane --freq 50").split() == [
        'slice_zVor_yplane/view/slice_zVor_yplane_100.png',
        'slice_zVor_yplane/view/slice_zVor_yplane_200.png']


@pytest.mark.parametrize('line, message, code', [
    ("missing C1 --dir nope", 'no nope/ in', 1),
    ("missing C1 --dir", '--dir needs a value', 2),
    ("missing C1 'a/b_{}.png' --dir slice_xVor", 'the pattern is a file name', 2),
    ("missing C1 C2 --dir slice_xVor", 'usage: missing', 2),
    ("missing nowhere --dir slice_xVor", 'not a directory', 1),
])
def test_dir_errors(rt, case, line, message, code):
    assert rt.execute_line(line) == code
    assert message in rt.err_console.file.getvalue()


@pytest.fixture
def registry(case, tmp_path):
    """.cases in work/ listing C1 (above), C2 (complete) and C3 (gone)."""
    import json
    c2 = tmp_path / 'work' / 'C2' / 'slice_xVor' / 'front'
    c2.mkdir(parents=True)
    for t in range(50, 301, 50):
        (c2 / f'slice_xVor_{t}.png').write_text('x')
    (tmp_path / 'work' / '.cases').write_text(json.dumps(
        [{'name': n, 'path': str(tmp_path / 'work' / n)} for n in ('C1', 'C2', 'C3')]))
    return tmp_path / 'work'


def test_dir_over_every_registered_case(rt, registry):
    assert rt.execute_line("use case:*") == 0
    assert rt.execute_line("missing --dir slice_xVor --freq 50") == 1
    text = rt.console.file.getvalue()
    assert [l for l in text.splitlines() if l in ('C1', 'C2', 'C3')] == ['C1', 'C2', 'C3']
    assert '✗ 2 of 3 cases with something missing: C1, C3' in text
    assert 'C3: not a directory' in rt.err_console.file.getvalue()
    # in a pipe: just the names, from every case
    assert rt.run_captured("missing --dir slice_xVor --freq 50").split() == [
        'C1/slice_xVor/front/slice_xVor_150.png']
    lines = rt.run_captured("missing '*' --dir slice_xVor --freq 50 -q").splitlines()
    assert lines[-1] == '✗ 2 of 3 cases with something missing: C1, C3'
    assert '✓ C2/slice_xVor/front/slice_xVor_{}.png  all 6 present · 50..300 every 50' in lines


def test_dir_star_without_a_registry(rt, case):
    assert rt.execute_line("missing '*' --dir slice_xVor") == 2
    assert 'no .cases' in rt.err_console.file.getvalue()
