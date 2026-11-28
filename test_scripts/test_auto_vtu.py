"""auto and the .vtu caches `field render` leaves in binary/: leftovers of a killed render
go once a day old, caches with a PLT only with auto.vtu_cache: delete, those without a PLT
never."""

import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.auto import conf as conf_mod
from src.core.auto.conf import AutoConf, AutoConfError
from src.core.auto.decide import decide
from src.core.auto.observe import VtuFile
from test_auto_decide import snap
from test_auto_show import dummy  # noqa: F401  (the fixture)

DAY = 24 * 3600


def vtu(name, size=100, age=0, plt=True):
    step = int(name.split('.')[1])
    return VtuFile(f"binary/{name}", step, size, age, name.endswith(('.partial.vtu', '.deriving.vtu')),
                   plt)


def plan_for(vtus, cache='keep'):
    conf = AutoConf(source=Path('.auto.conf'), remote='local', path='/cloud', keep_rst=200,
                    vtu_cache=cache)
    return decide(snap(vtu=vtus), conf, cloud_ok=True, sacct_ok=True)


def texts(plan, kind):
    return [i.text for i in plan.items if i.kind == kind and i.text.startswith('.vtu')]


def test_no_vtu_no_step():
    plan = plan_for([])
    assert not plan.steps_of('delete-vtu') and 'vtu' not in plan.ctx


def test_an_old_leftover_goes_a_young_one_stays():
    plan = plan_for([vtu('riser.100.partial.vtu', age=2 * DAY), vtu('riser.200.deriving.vtu', age=60)])
    assert list(plan.ctx['vtu_go']) == ['binary/riser.100.partial.vtu']
    assert 'killed render' in texts(plan, 'delete')[0]
    assert 'younger than a day' in texts(plan, 'note')[0]
    step, = plan.steps_of('delete-vtu')
    assert step.command == 'case organise vtu --case case --leftovers --age-hours 24'


def test_a_cache_with_its_plt_is_kept_unless_the_config_says_delete():
    caches = [vtu('riser.100.vtu', plt=True), vtu('riser.100.z1.vtu', plt=True)]
    keep = plan_for(caches)
    assert not keep.ctx.get('vtu_go')
    assert 'kept' in texts(keep, 'note')[0] and 'vtu_cache: delete' in texts(keep, 'note')[0]
    gone = plan_for(caches, cache='delete')
    assert sorted(gone.ctx['vtu_go']) == ['binary/riser.100.vtu', 'binary/riser.100.z1.vtu']
    assert gone.steps_of('delete-vtu')[0].command == 'case organise vtu --case case --age-hours 24'


def test_a_cache_without_its_plt_is_reported_never_deleted():
    for cache in ('keep', 'delete'):
        plan = plan_for([vtu('riser.100.vtu', plt=False)], cache=cache)
        assert not plan.ctx.get('vtu_go')
        assert 'cannot be rebuilt' in texts(plan, 'note')[0]


def test_vtu_cache_setting_is_checked():
    assert conf_mod.check_vtu_cache(None) == 'keep'
    assert conf_mod.check_vtu_cache('DELETE') == 'delete'
    with pytest.raises(AutoConfError):
        conf_mod.check_vtu_cache('always')


def test_a_dummy_case_with_vtu_files(dummy):
    from test_auto_show import plans
    case = dummy / 'bare' / 'case3'
    plt = next((case / 'binary').glob('riser.*.plt'))
    step = plt.name.split('.')[1]
    binary = case / 'binary'
    made = {f'riser.{step}.vtu': 0, f'riser.{step}.z1.vtu': 0, 'riser.9999.vtu': 0,
            'riser.9998.partial.vtu': 3 * DAY, 'riser.9997.deriving.vtu': 60,
            'mine.vtu': 0}
    for name, age in made.items():
        (binary / name).write_bytes(b'x' * 7)
        if age:
            old = time.time() - age
            os.utime(binary / name, (old, old))
    plan = plans(dummy, 'case3')[0]['case3']
    assert sorted(plan.ctx['vtu_go']) == ['binary/riser.9998.partial.vtu']
    info = plan.ctx['vtu']
    assert len(info['caches']) == 2 and [v.step for v in info['orphans']] == [9999]
    assert [v.step for v in info['fresh']] == [9997]
    from test_auto_show import report_of
    rows = dict(report_of(dummy, 'case3')['plt'].rows)
    assert rows['VTU'].startswith('2 cache') and 'Delete VTU' in rows


def test_vtu_cache_survives_a_round_trip_through_cases_yml(tmp_path):
    from src.core.auto.conf import read, set_up
    set_up(tmp_path, remote='local', path='/x', vtu_cache='delete')
    assert read(tmp_path, 'local').vtu_cache == 'delete'
