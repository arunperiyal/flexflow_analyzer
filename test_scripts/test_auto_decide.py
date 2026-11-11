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
    # nothing posted for 50-400 (no .out, no PLT anywhere): flagged; 450-600 can still be posted
    assert plan.post == (450, 600, 'full')
    assert kinds(plan, 'needs')[0].startswith(
        'Steps 50–400 every 50 (8 steps) have no PLT and no .out anywhere (local or here)')


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
    assert kinds(plan, 'needs')[0] == ('Holes on the remote: steps 450, 550, 600 have no PLT, '
                                       'while later steps have one. Find out why before posting.')


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
    assert deletes[-1].startswith('Steps 250, 300: not a multiple of 200.')


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
    assert steps_phrase([450, 500, 550, 700], 50) == 'Steps 450–550 every 50 (3 steps), 700'
    assert steps_text([5, 10, 15], 5) == '5–15 every 5 (3 steps)'
    assert steps_text([450, 500]) == '450, 500'


def test_post_says_which_run_and_where_the_plts_are():
    binary = {t: PltCheck(Path(f'b/{t}'), True, '', 424, 424) for t in (550, 600)}
    plan = decide(snap(cloud=cloud_with(*range(50, 501, 50)), binary=binary), CONF, True, True)
    notes = kinds(plan, 'note')
    assert notes[0] == ('The newest run is archive/riser1.othd (steps 1–600). Its output steps: '
                        '50–600 every 50 (12 steps).')
    assert notes[1].startswith('No post job needed: all 12 output steps have a PLT '
                               '(10 on local, 2 only in binary/ (not uploaded yet)).')
    s = snap(cloud=cloud_with(*range(50, 401, 50)))
    assert kinds(decide(s, CONF, True, True), 'post') == [
        'Submit `run post full --t1 450 --t2 600`: 4 output steps with no PLT yet; '
        'the 8 before 450 have one (8 on local)']


# --- a run that changed its output frequency --------------------------------------

def mixed_remote():
    """Every 50 steps up to 500, then every 5 up to 4000, all on the remote."""
    return cloud_with(*range(50, 501, 50), *range(505, 4001, 5))


def test_a_change_of_frequency_is_neither_a_hole_nor_missing():
    s = snap(out_freq=5, max_steps=5000, archive_range=(1, 4000), cloud=mixed_remote(),
             settled=[], out={})
    plan = decide(s, CONF, True, True)
    assert not plan.needs_you and plan.post is None
    assert plan.ctx['lost'] == [] and plan.ctx['missing'] == []
    assert kinds(plan, 'note')[0] == ('The newest run is archive/riser1.othd (steps 1–4000). Its '
                                      'output steps: 50–500 every 50 (10 steps), 505–4000 every 5 '
                                      '(700 steps).')


def test_the_new_steps_are_posted_at_their_own_frequency():
    steps = list(range(4005, 4101, 5))
    s = snap(out_freq=5, max_steps=5000, archive_range=(1, 4100), cloud=mixed_remote(),
             settled=steps, out={t: [] for t in steps})
    plan = decide(s, CONF, True, True)
    assert plan.post_jobs == [(4005, 4100, 5, 'full')] and not plan.needs_you
    assert kinds(plan, 'post')[-1] == ('Submit `run post full --t1 4005 --t2 4100`: 20 output '
                                       'steps with no PLT yet; the 710 before 4005 have one '
                                       '(710 on local)')


def test_two_schedules_need_two_post_jobs_each_with_its_freq():
    steps = list(range(50, 501, 50)) + list(range(505, 526, 5))
    s = snap(out_freq=5, archive_range=(1, 525), cloud={}, settled=steps,
             out={t: [] for t in steps})
    plan = decide(s, CONF, True, True)
    assert plan.post_jobs == [(50, 500, 50, 'full'), (505, 525, 5, 'full')]
    assert plan.post == (50, 525, 'full') and not plan.needs_you
    posts = kinds(plan, 'post')
    assert posts[0].startswith('Submit `run post full --t1 50 --t2 500 --freq 50`: 10 output steps')
    assert posts[1].startswith('Submit `run post full --t1 505 --t2 525 --freq 5`: 5 output steps')
    assert any('takes 2 post jobs' in n for n in kinds(plan, 'note'))


def test_a_step_missing_inside_a_stretch_is_flagged_but_the_rest_is_posted():
    have = [t for t in range(50, 401, 50) if t != 300]
    s = snap(cloud=cloud_with(*have))
    plan = decide(s, CONF, True, True)
    assert plan.ctx['lost'] == [300] and plan.post == (450, 600, 'full')
    assert kinds(plan, 'needs')[0].startswith('Step 300 has no PLT and no .out anywhere')


def test_steps_off_the_grid_of_their_spacing_cannot_be_posted():
    steps = [55, 105, 155, 205]                    # every 50, but not on a multiple of 50
    s = snap(archive_range=(1, 205), cloud={}, settled=steps, out={t: [] for t in steps})
    plan = decide(s, CONF, True, True)
    assert plan.post_jobs == [] and plan.post is None
    assert 'not on a multiple of the spacing around them' in kinds(plan, 'needs')[-1]


def test_a_run_that_stops_short_of_its_last_step_is_flagged_at_the_tail():
    s = snap(out_freq=5, max_steps=5000, archive_range=(1, 5000), cloud=mixed_remote(),
             settled=[], out={})                        # the run reached 5000, PLTs stop at 4000
    plan = decide(s, CONF, True, True)
    assert plan.ctx['lost'] == list(range(4005, 5001, 5))
    assert kinds(plan, 'needs')[0].startswith('Steps 4005–5000 every 5 (200 steps) have no PLT')


# --- restart sets: keep_rst here, upload_rst on the remote ------------------------------

CONF_RST = AutoConf(source=Path('.auto.conf'), remote='local', path='/cloud', keep_rst=500,
                    upload_rst=1000)


def rst_files(*steps, parts=4):
    return {t: {f"RUN_1/riser.{t}_{k}.rst": 10 for k in range(parts)} for t in steps}


def on_remote(*steps, parts=4):
    return {f"RUN_1/riser.{t}_{k}.rst": 10 for t in steps for k in range(parts)}


def rst_snap(local, remote=(), **kw):
    base = dict(max_steps=7000, archive_range=(1, 5759), settled=[], out={}, nsg=4,
                rst={t: 4 for t in local}, rst_files=rst_files(*local),
                cloud=on_remote(*remote))
    base.update(kw)
    return snap(**base)


def test_sets_on_the_upload_grid_are_due_not_the_newest():
    s = rst_snap([500, 1000, 1500, 2000, 4000, 5000, 5740],
                 remote=[500, 4000, 5000], restart_tsid=5740, jobs=[job('maincase', 'PENDING')])
    plan = decide(s, CONF_RST, True, True)
    assert plan.ctx['rst_due'] == [1000, 2000, 4000, 5000]
    assert sorted(plan.ctx['rst_todo']) == [1000, 2000]          # 4000 and 5000 are there
    assert kinds(plan, 'upload')[-1] == 'Restart sets, steps 1000, 2000: 8 files, 80 B'
    assert 'RUN_1/riser.5740_0.rst' not in plan.uploads          # the newest is not sent
    assert plan.ctx['rst_remote'] == {500: 4, 4000: 4, 5000: 4}


def test_a_finished_runs_final_set_is_sent_when_it_is_off_the_grid():
    s = rst_snap([1000, 7000, 7350], remote=[1000, 7000], archive_range=(1, 7350), max_steps=7350)
    plan = decide(s, CONF_RST, True, True)
    assert plan.state == 'done' and plan.ctx['rst_final'] == 7350
    assert sorted(plan.ctx['rst_todo']) == [7350]
    assert 'final set of the finished run' in kinds(plan, 'upload')[-1]
    # still running or stopped short: no final set, grid only
    running = rst_snap([1000, 2000], remote=[1000], archive_range=(1, 2100))
    assert decide(running, CONF_RST, True, True).ctx['rst_final'] is None


def test_without_upload_rst_no_restart_set_is_uploaded():
    conf = AutoConf(source=Path('.auto.conf'), remote='local', path='/cloud', keep_rst=500)
    plan = decide(rst_snap([1000, 5000], remote=[]), conf, True, True)
    assert not any(k.endswith('.rst') for k in plan.uploads)
    assert 'Restart sets are not uploaded: auto.upload_rst is not set' in kinds(plan, 'note')[-1]


def test_a_grid_set_a_queued_restart_will_compute_again_waits():
    s = rst_snap([1000, 4000, 5000], remote=[1000], restart_tsid=4500,
                 jobs=[job('maincase', 'PENDING')])
    plan = decide(s, CONF_RST, True, True)
    assert plan.ctx['rst_due'] == [1000, 4000] and sorted(plan.ctx['rst_todo']) == [4000]


def test_a_partial_set_on_the_remote_is_sent_again():
    s = rst_snap([1000], remote=[], cloud={**on_remote(1000, parts=2)})
    plan = decide(s, CONF_RST, True, True)
    assert sorted(plan.uploads) == ['RUN_1/riser.1000_2.rst', 'RUN_1/riser.1000_3.rst']
    assert plan.ctx['rst_remote'] == {1000: 2}


def test_a_grid_set_that_exists_nowhere_is_flagged():
    s = rst_snap([500, 1000, 2000, 4000], remote=[3500, 5000])
    # 3000 would be in line (every 500 here, and on the grid) but is neither here nor there
    s.rst = {t: 4 for t in (500, 1000, 1500, 2000, 2500, 3500, 4000, 4500)}
    s.rst_files = rst_files(*s.rst)
    s.cloud = on_remote(3500, 5000)
    plan = decide(s, CONF_RST, True, True)
    assert plan.ctx['rst_lost'] == [3000]
    assert ('Restart step 3000 is on the upload grid (every 1000) but exists neither here nor '
            'on local.') in kinds(plan, 'flag')
