"""The steps a post job was given, read from its slurm output when .casestatus.md has no
"started: steps" line (found 2026-11-28: a job asked for 6130..6460 was blamed for the
.out of 6465..6485 that were written while it ran)."""

import time as _time
from pathlib import Path

from src.core.auto.conf import AutoConf
from src.core.auto.decide import decide
from src.core.auto.observe import CaseSnapshot, History, post_window_from_log
from src.core.slurm import Job

CONF = AutoConf(source=Path('.auto.conf'), remote='local', path='/cloud', keep_rst=200)

HEAD = """SLURM_JOB_ID = 7
==========================================
FlexFlow Postprocessing Job
==========================================
Problem:      riser
Run Dir:      ./RUN_1
Frequency:    5
Start Time:   6130 (0 = beginning)
End Time:     6460
Processes:    36
"""


def test_the_window_is_read_from_the_header(tmp_path):
    f = tmp_path / 'slurm-7.out'
    f.write_text(HEAD + 'Command: simPlt2Bin ...\n')
    assert post_window_from_log(f) == (6130, 6460)


def test_other_slurm_outputs_and_missing_files_give_none(tmp_path):
    main = tmp_path / 'slurm-8.out'
    main.write_text('Start Time:   1\nEnd Time:     2\n')            # not a post job's
    cut = tmp_path / 'slurm-9.out'
    cut.write_text(HEAD.split('End Time')[0])
    assert post_window_from_log(main) is None
    assert post_window_from_log(cut) is None
    assert post_window_from_log(tmp_path / 'slurm-10.out') is None


def snap(**kw):
    base = dict(name='case', dir=Path('/c/case'), problem='riser', nsg=4, out_freq=50,
                max_steps=1000, run_rel='RUN_1',
                history={'othd': History(archive={1: Path('a/riser1.othd')},
                                         cleaned={1: Path('c/riser1.othd')}),
                         'oisd': History(archive={1: Path('a/riser1.oisd')},
                                         cleaned={1: Path('c/riser1.oisd')})},
                archive_range=(1, 600), settled=[450, 500, 550, 600],
                out={t: [] for t in (450, 500, 550, 600)}, cloud={})
    base.update(kw)
    return CaseSnapshot(**base)


def test_a_job_that_was_not_given_the_steps_is_not_blamed():
    ended = _time.mktime(_time.strptime('2026-11-11 19:58:00', '%Y-%m-%d %H:%M:%S'))
    done = Job('7', 'postcase', 'COMPLETED', '', '/c/case', '2026-11-11T19:58:00',
               '2026-11-11T19:50:00')
    cloud = {f"binary/riser.{t}.plt": 424 for t in range(50, 401, 50)}
    out_time = {450: ended - 120, 500: ended - 120}
    blamed = decide(snap(ended=[done], cloud=cloud, out_time=out_time), CONF, True, True)
    assert any('yet they have no whole PLT' in i.text for i in blamed.items)
    cleared = decide(snap(ended=[done], cloud=cloud, out_time=out_time,
                          post_windows={'7': (50, 400)}), CONF, True, True)
    assert not cleared.needs_you
    assert cleared.post and cleared.post[0] == 450
