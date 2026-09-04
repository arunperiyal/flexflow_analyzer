"""Tests for OTHDReader's `othId` group handling.

docs/WEBAPP_PLAN.md §3 documented a real bug here: `othId` was not a
recognised line, so the restart/overwrite check (`current_time in
self.time_to_index`) re-fired for every group inside one timestep -- the
second group in a timestep looked like a restart of the first and clobbered
its rows. For a timestep carrying group 0 (49 rows) and group 1 (12 rows),
the result was a splice: rows 0-11 held group 1, rows 12-48 held group 0,
with `num_nodes` staying 49 throughout, no warning.

These tests reproduce that shape directly (two groups written under the
same timestep, one smaller than the other) and check the fix: each group's
displacements are kept apart by `othId`, `num_nodes`/`get_node_displacements`
read a selected group instead of whichever wrote first, and the ordinary
single-group case (the common one, and the pendulum format) is unaffected.
"""

import pytest

from src.core.readers.othd_reader import OTHDReader

# Two groups under each of two timesteps -- group 0 has 3 nodes, group 1 has
# 2. This is exactly the shape that spliced under the old code: group 1's
# smaller aleDisp block landed on group 0's first two node indices.
TWO_GROUP_OTHD = """tsId 1
time 0.05
othId 0
aleDisp 3 3
1.0 1.0 1.0
2.0 2.0 2.0
3.0 3.0 3.0
othId 1
aleDisp 3 2
9.0 9.0 9.0
8.0 8.0 8.0
tsId 2
time 0.10
othId 0
aleDisp 3 3
1.1 1.1 1.1
2.1 2.1 2.1
3.1 3.1 3.1
othId 1
aleDisp 3 2
9.1 9.1 9.1
8.1 8.1 8.1
"""

# A restart: file 2 rewrites time 0.05 (both groups) with different values.
TWO_GROUP_RESTART = """tsId 1
time 0.05
othId 0
aleDisp 3 3
101.0 101.0 101.0
102.0 102.0 102.0
103.0 103.0 103.0
othId 1
aleDisp 3 2
109.0 109.0 109.0
108.0 108.0 108.0
"""

SINGLE_GROUP_OTHD = """tsId 1
time 0.05
aleDisp 3 2
1.0 1.0 1.0
2.0 2.0 2.0
tsId 2
time 0.10
aleDisp 3 2
1.1 1.1 1.1
2.1 2.1 2.1
"""

SINGLE_GROUP_RESTART = """tsId 1
time 0.05
aleDisp 3 2
101.0 101.0 101.0
102.0 102.0 102.0
"""

PENDULUM_OTHD = """tsId 1
time 0.05
aleDisp 3 1
0.5 0.0 0.0
pendDisp 1
0.5
pendVel 1
1.2
tsId 2
time 0.10
aleDisp 3 1
0.6 0.0 0.0
pendDisp 1
0.6
pendVel 1
1.3
"""


@pytest.fixture
def two_group_file(tmp_path):
    p = tmp_path / "case.othd"
    p.write_text(TWO_GROUP_OTHD)
    return str(p)


def test_default_group_is_the_lowest_othid(two_group_file):
    reader = OTHDReader(two_group_file)
    assert reader.groups == [0, 1]
    assert reader.group == 0
    assert reader.num_nodes == 3


def test_group_0_is_not_spliced_with_group_1s_rows(two_group_file):
    reader = OTHDReader(two_group_file, group=0)
    node0 = reader.get_node_displacements(0)
    node1 = reader.get_node_displacements(1)
    node2 = reader.get_node_displacements(2)

    # Under the old bug, node 0 and node 1 at the first timestep would read
    # back as group 1's [9.0, 8.0] rather than group 0's own [1.0, 2.0].
    assert list(node0['dx']) == [1.0, 1.1]
    assert list(node1['dx']) == [2.0, 2.1]
    assert list(node2['dx']) == [3.0, 3.1]


def test_group_1_reads_its_own_rows_not_groups_0s(two_group_file):
    reader = OTHDReader(two_group_file, group=1)
    assert reader.num_nodes == 2
    node0 = reader.get_node_displacements(0)
    node1 = reader.get_node_displacements(1)
    assert list(node0['dx']) == [9.0, 9.1]
    assert list(node1['dx']) == [8.0, 8.1]


def test_unknown_group_raises(two_group_file):
    with pytest.raises(ValueError, match="othId 5 not present"):
        OTHDReader(two_group_file, group=5)


def test_restart_overwrites_both_groups_at_the_shared_index(tmp_path):
    f1 = tmp_path / "run1.othd"
    f1.write_text(TWO_GROUP_OTHD)
    f2 = tmp_path / "run2_restart.othd"
    f2.write_text(TWO_GROUP_RESTART)

    reader = OTHDReader([str(f1), str(f2)], group=0)
    assert len(reader.times) == 2   # still just two timesteps, not three
    node0 = reader.get_node_displacements(0)
    # time 0.05's group-0 values come from the restart file, not run1.
    assert node0['dx'][0] == 101.0
    assert node0['dx'][1] == 1.1   # time 0.10 untouched by the restart

    reader1 = OTHDReader([str(f1), str(f2)], group=1)
    node0_g1 = reader1.get_node_displacements(0)
    assert node0_g1['dx'][0] == 109.0
    assert node0_g1['dx'][1] == 9.1


# -- the ordinary, single-group case is unaffected -------------------------

@pytest.fixture
def single_group_file(tmp_path):
    p = tmp_path / "single.othd"
    p.write_text(SINGLE_GROUP_OTHD)
    return str(p)


def test_single_group_file_has_one_implicit_group(single_group_file):
    reader = OTHDReader(single_group_file)
    assert reader.groups == [0]
    assert reader.group == 0
    assert reader.num_nodes == 2


def test_single_group_displacements_are_unchanged(single_group_file):
    reader = OTHDReader(single_group_file)
    node0 = reader.get_node_displacements(0)
    node1 = reader.get_node_displacements(1)
    assert list(node0['dx']) == [1.0, 1.1]
    assert list(node1['dx']) == [2.0, 2.1]
    assert list(node0['times']) == [0.05, 0.10]


def test_single_group_restart_still_overwrites(tmp_path):
    f1 = tmp_path / "run1.othd"
    f1.write_text(SINGLE_GROUP_OTHD)
    f2 = tmp_path / "run2_restart.othd"
    f2.write_text(SINGLE_GROUP_RESTART)

    reader = OTHDReader([str(f1), str(f2)])
    assert len(reader.times) == 2
    node0 = reader.get_node_displacements(0)
    assert node0['dx'][0] == 101.0
    assert node0['dx'][1] == 1.1


def test_recalculate_times_still_works(single_group_file):
    reader = OTHDReader(single_group_file)
    reader.recalculate_times(0.05)
    assert reader.times == [0.05, 0.10]
    assert reader.time_increment == 0.05


# -- pendulum data is unaffected --------------------------------------------

def test_pendulum_data_survives_the_group_refactor(tmp_path):
    p = tmp_path / "pendulum.othd"
    p.write_text(PENDULUM_OTHD)
    reader = OTHDReader(str(p))

    pend = reader.get_pendulum_data()
    assert pend is not None
    assert list(pend['displacement']) == [0.5, 0.6]
    assert list(pend['velocity']) == [1.2, 1.3]

    node0 = reader.get_node_displacements(0)
    assert list(node0['dx']) == [0.5, 0.6]
