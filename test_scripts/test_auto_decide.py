"""src/core/auto/decide.py: the plan for one case, from a made-up snapshot."""

from pathlib import Path

import pytest

from src.core.auto.conf import AutoConf
from src.core.auto.decide import decide
from src.core.auto.observe import CaseSnapshot, History
from src.core.plt_valid import PltCheck
from src.core.slurm import Job

CONF = AutoConf(source=Path('.auto.conf'), remote='local', path='/cloud', keep_rst=200)


def job(name, state, workdir='/c/case', jobid='1'):
    return Job(jobid, name, state, 'medium', workdir)


def snap(**kw):
    """case 'case': outFreq 50, nsg 4, 1000 steps, archive part 1 over 1..600,
    .out 450..600 settled, nothing on the cloud."""
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


def cloud_with(*steps):
    return {f"binary/riser.{t}.plt": 424 for t in steps}


def kinds(plan, kind):
    return [i.text for i in plan.items if i.kind == kind]


def test_none_on_cloud_posts_the_whole_run():
    plan = decide(snap(cloud=cloud_with()), CONF, True, True)
    assert plan.post is None and 'Steps 50–400 (8 steps) have no PLT on the remote and no .out here' in kinds(plan, 'needs')[0]


def test_unbroken_prefix_posts_the_rest():
    plan = decide(snap(cloud=cloud_with(*range(50, 401, 50))), CONF, True, True)
    assert plan.post == (450, 600, 'full')
    assert not plan.needs_you


def test_all_on_cloud_posts_nothing():
    plan = decide(snap(cloud=cloud_with(*range(50, 601, 50))), CONF, True, True)
    assert plan.post is None and not plan.needs_you


def test_whole_local_plt_counts_as_converted():
    binary = {t: PltCheck(Path(f'b/{t}'), True, '', 424, 424) for t in (450, 500)}
    plan = decide(snap(cloud=cloud_with(*range(50, 401, 50)), binary=binary), CONF, True, True)
    assert plan.post == (550, 600, 'full')
    assert 'binary/riser.450.plt' in plan.uploads


def test_holes_need_you():
    plan = decide(snap(cloud=cloud_with(*range(50, 401, 50), 500)), CONF, True, True)
    assert plan.post is None
    assert kinds(plan, 'needs')[0].startswith('Holes on the remote: steps 450, 550–600 (2 steps) of 50–600 have no PLT')


def test_running_stops_at_the_last_settled_step():
    s = snap(live=(401, 652), settled=[450, 500, 550], jobs=[job('maincase', 'RUNNING')],
             cloud=cloud_with(*range(50, 401, 50)))
    plan = decide(s, CONF, True, True)
    assert plan.post == (450, 550, 'full') and plan.state == 'running'
    assert not kinds(plan, 'history')                     # history stays in RUN_1


def test_queued_restart_cuts_the_window():
    s = snap(live=(501, 760), restart_tsid=700, archive_range=(1, 520),
             settled=list(range(550, 751, 50)), out={t: [] for t in range(550, 751, 50)},
             jobs=[job('maincase', 'PENDING')], cloud=cloud_with(*range(50, 501, 50)),
             binary={750: PltCheck(Path('b/750'), True, '', 424, 424)})
    plan = decide(s, CONF, True, True)
    assert plan.post == (550, 700, 'full') and plan.state == 'queued'
    assert 'binary/riser.750.plt' not in plan.uploads     # provisional
    assert 'Step 750 is left alone: the queued job restarts from 700 and computes it again.' in kinds(plan, 'note')


def test_ended_run_still_in_run_dir_is_organised_and_posted():
    s = snap(live=(601, 820), archive_range=(1, 600), settled=list(range(650, 801, 50)),
             out={t: [] for t in range(650, 801, 50)}, cloud=cloud_with(*range(50, 601, 50)),
             ended=[job('maincase', 'TIMEOUT')])
    plan = decide(s, CONF, True, True)
    assert kinds(plan, 'history')[0].startswith('Move RUN_1/riser.othd and .oisd into archive/ as run 2')
    assert plan.post == (650, 800, 'full')


def test_active_post_job_waits():
    plan = decide(snap(jobs=[job('postcase', 'RUNNING')]), CONF, True, True)
    assert plan.post is None and kinds(plan, 'wait') and not plan.uploads


def test_post_that_ended_badly_needs_you():
    s = snap(cloud=cloud_with(*range(50, 401, 50)), ended=[job('postcase', 'TIMEOUT', jobid='9')],
             binary={550: PltCheck(Path('b/550'), False, 'cut short', 200)})
    plan = decide(s, CONF, True, True)
    assert plan.post is None
    assert kinds(plan, 'needs')[0].startswith('Post job 9 ended TIMEOUT: steps')


def test_archive_pruned_breaks_the_rule():
    s = snap(history={'othd': History(cleaned={1: Path('c/riser1.othd')}),
                      'oisd': History(cleaned={1: Path('c/riser1.oisd')})}, archive_range=None)
    plan = decide(s, CONF, True, True)
    assert plan.post is None and 'archive/ is pruned or missing' in kinds(plan, 'needs')[0]


def test_convert_when_every_step_has_ascii():
    s = snap(cloud=cloud_with(*range(50, 401, 50)), settled=[], ascii={450, 500, 550, 600})
    assert decide(s, CONF, True, True).post == (450, 600, 'convert')


def test_no_cloud_or_no_sacct_decides_no_post():
    assert decide(snap(cloud=None), CONF, False, True).post is None
    plan = decide(snap(cloud=cloud_with(*range(50, 401, 50))), CONF, True, False)
    assert plan.post is None and any('sacct' in n for n in kinds(plan, 'note'))


def test_job_and_script_named_for_another_case_are_flagged():
    s = snap(jobs=[job('maincase1', 'RUNNING')], live=(401, 652), settled=[],
             script_names={'postFlex.sh': 'postcase6'})
    flags = kinds(decide(s, CONF, True, True), 'flag')
    assert any('is named maincase1; for this case it should be maincase.' in f for f in flags)
    assert any('postFlex.sh names its jobs postcase6' in f for f in flags)


def test_failed_main_and_skipped_config_need_you():
    assert decide(snap(error='simflow.config has no `problem`'), CONF, True, True).state == 'skipped'
    s = snap(history={'othd': History(), 'oisd': History()}, archive_range=None,
             ended=[job('maincase', 'FAILED', jobid='5')])
    assert kinds(decide(s, CONF, True, True), 'needs') == [
        'Main job 5 FAILED. Find the cause first (run list log, case check run).']


def test_rst_thinning_keeps_restart_point_and_newest():
    s = snap(cloud=cloud_with(*range(50, 601, 50)), restart_tsid=350,
             rst={t: 4 for t in (200, 250, 300, 350, 400, 450)})
    deletes = kinds(decide(s, CONF, True, True), 'delete')
    assert deletes[-1].startswith('Steps 250–300 (2 steps): not a multiple of 200.')


def test_stopped_short_is_asked():
    s = snap(cloud=cloud_with(*range(50, 601, 50)), ended=[job('maincase', 'TIMEOUT')])
    assert kinds(decide(s, CONF, True, True), 'needs')[-1].startswith('Stopped at step 600 of 1000 with nothing queued')


def test_completed_post_that_left_steps_unconverted_needs_you():
    done = Job('7', 'postcase', 'COMPLETED', '', '/c/case', '2026-11-08T10:00:00')
    s = snap(cloud=cloud_with(*range(50, 401, 50)), ended=[done],
             out_time={t: 1_000.0 for t in (450, 500, 550, 600)})
    plan = decide(s, CONF, True, True)
    assert plan.post is None and kinds(plan, 'needs')[0].startswith('Post job 7 ended COMPLETED')
    # .out written after that post job: posting them is right
    s.out_time = {t: 4e9 for t in (450, 500, 550, 600)}
    assert decide(s, CONF, True, True).post == (450, 600, 'full')


def test_completed_post_is_only_held_to_the_steps_it_was_given():
    done = Job('7', 'postcase', 'COMPLETED', '', '/c/case', '2026-11-08T10:00:00')
    s = snap(cloud=cloud_with(*range(50, 451, 50)), ended=[done],
             out_time={t: 1_000.0 for t in (450, 500, 550, 600)},
             post_windows={'7': (400, 450)})
    # it was given 400..450 only (and made them); 500-600 are new work
    assert decide(s, CONF, True, True).post == (500, 600, 'full')


def test_steps_read_as_a_phrase():
    from src.core.auto.decide import steps_phrase, steps_text
    assert steps_phrase([750], 50) == 'Step 750'
    assert steps_phrase([450, 500, 550, 700], 50) == 'Steps 450–550 (3 steps), 700'
    assert steps_text([5, 10, 15], 5) == '5–15 (3 steps)'
