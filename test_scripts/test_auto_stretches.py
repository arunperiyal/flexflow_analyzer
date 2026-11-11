"""Output steps as stretches of constant spacing (src/core/auto/stretches.py)."""

from src.core.auto.stretches import Stretch, gaps, stretches, text

MIXED = list(range(50, 501, 50)) + list(range(505, 5001, 5))      # every 50, then every 5


def test_a_change_of_frequency_is_two_stretches():
    assert stretches(MIXED) == [Stretch(50, 500, 50, 10), Stretch(505, 5000, 5, 900)]
    assert text(MIXED) == '50–500 every 50 (10 steps), 505–5000 every 5 (900 steps)'


def test_a_change_of_frequency_is_not_a_gap():
    assert gaps(MIXED, lo=1, hi=5000, freq=5) == []
    assert gaps(MIXED, lo=1, hi=5000, freq=50) == []          # whatever outFreq says now


def test_a_missing_step_inside_a_stretch_is_a_gap():
    steps = [s for s in MIXED if s not in (150, 2000, 2005)]
    assert gaps(steps, lo=1, hi=5000, freq=5) == [150, 2000, 2005]
    # too few steps to claim a spacing: listed one by one, outFreq supplies the spacing
    assert text([50, 100, 200, 250]) == '50, 100, 200, 250'
    assert gaps([50, 100, 200, 250], 1, 250, 50) == [150]


def test_a_space_between_stretches_wider_than_either_is_a_gap_at_the_finer_spacing():
    steps = list(range(50, 501, 50)) + list(range(600, 700, 5))       # 505..595 never written
    assert gaps(steps, 1, 695, 5) == list(range(505, 600, 5))


def test_before_the_first_and_after_the_last_step():
    assert gaps([450, 500, 550, 600], lo=1, hi=600, freq=50) == list(range(50, 450, 50))
    assert gaps([50, 100, 150], lo=1, hi=300, freq=50) == [200, 250, 300]
    assert gaps([4955, 4960, 4965], lo=4951, hi=4965, freq=5) == []   # the window starts at 4951


def test_no_step_at_all_uses_the_configured_frequency():
    assert gaps([], lo=1, hi=200, freq=50) == [50, 100, 150, 200]
    assert gaps([], lo=10, hi=5, freq=50) == []


def test_a_lone_step_has_no_spacing_of_its_own():
    assert stretches([750]) == [Stretch(750, 750, None, 1)]
    assert text([750]) == '750'
    assert gaps([450], lo=1, hi=600, freq=50) == list(range(50, 450, 50)) + [500, 550, 600]


def test_long_lists_are_elided():
    many = [1, 3, 8, 12, 20, 21, 40, 41, 77, 90, 91, 140]
    assert text(many, limit=4) == '1, 3, … 8 more …, 91, 140'          # no two are 'a stretch'
    assert text([5, 10, 15, 20, 100, 105, 110], limit=4) == \
        '5–20 every 5 (4 steps), 100–110 every 5 (3 steps)'
