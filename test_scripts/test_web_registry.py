"""Tests for src/web/services/registry.py: the .cases registry (list, scan,
add, delete).

Case detection only needs a simflow.config file in each candidate directory
(see scan_for_cases in src/commands/case/add_impl/command.py) -- no real
simulation data required here.
"""

import shutil
from pathlib import Path

from src.web.services import registry


def _make_case(parent: Path, name: str) -> Path:
    case_dir = parent / name
    case_dir.mkdir(parents=True)
    (case_dir / 'simflow.config').write_text('')
    return case_dir


def test_add_cases_merges_with_an_existing_registration_from_another_directory(tmp_path):
    # root/.cases is shared across every scan, but the cases themselves can
    # live in entirely separate directories -- this is exactly the reported
    # bug: adding a case scanned from directory B must not drop one already
    # registered from directory A.
    root = tmp_path / 'root'
    root.mkdir()
    dir_a = tmp_path / 'dir_a'
    dir_a.mkdir()
    dir_b = tmp_path / 'dir_b'
    dir_b.mkdir()
    _make_case(dir_a, 'CaseA')
    _make_case(dir_b, 'CaseB')

    registry.add_cases(root, dir_a, exclude=set())
    result = registry.add_cases(root, dir_b, exclude=set())

    assert {c['name'] for c in result} == {'CaseA', 'CaseB'}


def test_add_cases_refreshes_the_path_on_a_name_collision(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    dir_a = tmp_path / 'dir_a'
    dir_a.mkdir()
    dir_b = tmp_path / 'dir_b'
    dir_b.mkdir()
    _make_case(dir_a, 'Case')
    new_case = _make_case(dir_b, 'Case')

    registry.add_cases(root, dir_a, exclude=set())
    result = registry.add_cases(root, dir_b, exclude=set())

    assert len(result) == 1
    assert Path(result[0]['path']) == new_case


def test_add_cases_respects_exclusions(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    scan_dir = tmp_path / 'scan'
    scan_dir.mkdir()
    _make_case(scan_dir, 'Keep')
    _make_case(scan_dir, 'Drop')

    result = registry.add_cases(root, scan_dir, exclude={'Drop'})

    assert {c['name'] for c in result} == {'Keep'}


def test_delete_case_leaves_other_directories_registrations_intact(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    dir_a = tmp_path / 'dir_a'
    dir_a.mkdir()
    dir_b = tmp_path / 'dir_b'
    dir_b.mkdir()
    _make_case(dir_a, 'CaseA')
    _make_case(dir_b, 'CaseB')
    registry.add_cases(root, dir_a, exclude=set())
    registry.add_cases(root, dir_b, exclude=set())

    result = registry.delete_case(root, 'CaseA')

    assert {c['name'] for c in result} == {'CaseB'}


def test_list_cases_flags_a_case_whose_directory_no_longer_exists(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    scan_dir = tmp_path / 'scan'
    scan_dir.mkdir()
    case_dir = _make_case(scan_dir, 'Case')
    registry.add_cases(root, scan_dir, exclude=set())

    shutil.rmtree(case_dir)
    result = registry.list_cases(root)

    assert result[0]['exists'] is False


def test_case_path_resolves_a_registered_name(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    scan_dir = tmp_path / 'scan'
    scan_dir.mkdir()
    case_dir = _make_case(scan_dir, 'Case')
    registry.add_cases(root, scan_dir, exclude=set())

    assert registry.case_path(root, 'Case') == case_dir
    assert registry.case_path(root, 'NoSuchCase') is None
