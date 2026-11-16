"""The delete stage's executor (auto.md 13.13): every file is checked again right before it
goes, and nothing the plan did not list is touched."""

import os
from pathlib import Path
from types import SimpleNamespace

from src.core import case_status
from src.core.transfer.cloud import LocalCloud
from src.core.auto.executor import do_delete
from src.core.transfer.ledger import Ledger
from plt_files import write_plt

T0 = 1_700_000_000


class Case:
    """case 'c1' with step 450: ASCII PLT, 2 .out parts, a binary PLT sent to a folder
    remote, and restart sets 100 and 500."""

    def __init__(self, tmp_path):
        self.root = tmp_path / 'cases'
        self.dir = self.root / 'c1'
        (self.dir / 'RUN_1').mkdir(parents=True)
        (self.dir / 'binary').mkdir()
        self.ascii, self.binary = 'RUN_1/riser.450.plt', 'binary/riser.450.plt'
        self.outs = ['RUN_1/riser.450_0.out', 'RUN_1/riser.450_1.out']
        self.rsts = ['RUN_1/riser.100_0.rst', 'RUN_1/riser.100_1.rst']
        for rel in (self.ascii, *self.outs, *self.rsts):
            (self.dir / rel).write_bytes(b'x' * 10)
            os.utime(self.dir / rel, (T0, T0))
        write_plt(self.dir / self.binary)
        os.utime(self.dir / self.binary, (T0 + 100, T0 + 100))
        (tmp_path / 'remote').mkdir()
        self.cloud = LocalCloud(tmp_path / 'remote')
        res = self.cloud.put(self.dir / self.binary, 'c1', self.binary)
        self.ledger = Ledger(self.root)
        self.ledger.record('local', 'c1', self.binary, res.size, res.md5, 'md5', T0 + 100)
        self.snap = SimpleNamespace(name='c1', dir=self.dir, problem='riser')
        self.conf = SimpleNamespace(remote='local', keep_rst=500)
        self.said = []

    def plan(self, **lists):
        size = lambda rels: {r: (self.dir / r).stat().st_size for r in rels if (self.dir / r).exists()}
        base = dict(ascii=size([self.ascii]), binary=size([self.binary]), out=size(self.outs),
                    rst=size(self.rsts))
        base.update(lists)
        return SimpleNamespace(ctx={'delete': base})

    def run(self, plan=None):
        return do_delete(self.snap, plan or self.plan(), self.conf, self.cloud, self.ledger,
                         self.said.append)

    def there(self, rel):
        return (self.dir / rel).exists()


def test_a_checked_copy_clears_the_files_of_the_step_and_the_ledger_remembers(tmp_path):
    c = Case(tmp_path)
    step = c.run()
    assert step.ok, step.detail
    assert not any(c.there(r) for r in (c.ascii, c.binary, *c.outs, *c.rsts))
    entry = Ledger(c.root).get('local', 'c1', c.binary)
    assert entry['deleted'] and entry['mtime'] == T0 + 100 and entry['verified'] == 'md5'
    assert (tmp_path / 'remote' / 'c1' / c.binary).exists()           # never touched there
    log = (c.dir / '.casestatus.md').read_text()
    assert 'auto deleted: 1 ASCII PLT, 1 binary PLT, 2 .out, 1 restart sets' in log


def test_a_copy_that_differs_keeps_every_file_of_the_step_and_marks_the_ledger(tmp_path):
    c = Case(tmp_path)
    remote = tmp_path / 'remote' / 'c1' / c.binary
    data = bytearray(remote.read_bytes())
    data[-1] ^= 0xFF                                                   # same size, other bytes
    remote.write_bytes(bytes(data))
    step = c.run(c.plan(rst={}))
    assert not step.ok and 'differs' in step.detail
    assert all(c.there(r) for r in (c.ascii, c.binary, *c.outs))
    assert Ledger(c.root).get('local', 'c1', c.binary)['mismatch']


def test_a_copy_of_another_size_is_left_without_an_md5(tmp_path):
    c = Case(tmp_path)
    (tmp_path / 'remote' / 'c1' / c.binary).write_bytes(b'short')
    step = c.run(c.plan(rst={}))
    assert step.ok and all(c.there(r) for r in (c.ascii, c.binary, *c.outs))
    assert any('is 5 bytes' in s for s in c.said)


def test_no_copy_on_the_remote_leaves_everything(tmp_path):
    c = Case(tmp_path)
    (tmp_path / 'remote' / 'c1' / c.binary).unlink()
    c.run(c.plan(rst={}))
    assert all(c.there(r) for r in (c.ascii, c.binary, *c.outs))


def test_an_out_written_after_the_plt_stays_a_restart_rewrote_it(tmp_path):
    c = Case(tmp_path)
    os.utime(c.dir / c.outs[1], (T0 + 500, T0 + 500))                  # newer than the PLT (T0+100)
    c.run(c.plan(rst={}))
    assert all(c.there(r) for r in c.outs)                             # all parts of the step stay
    assert not c.there(c.binary) and not c.there(c.ascii)              # the PLT itself has its copy


def test_an_ascii_plt_written_after_the_binary_stays(tmp_path):
    c = Case(tmp_path)
    os.utime(c.dir / c.ascii, (T0 + 500, T0 + 500))
    c.run(c.plan(rst={}))
    assert c.there(c.ascii) and not c.there(c.outs[0])


def test_a_binary_plt_gone_here_clears_the_rest_by_the_ledger_and_a_fresh_remote_md5(tmp_path):
    c = Case(tmp_path)
    (c.dir / c.binary).unlink()
    step = c.run(c.plan(binary={}, rst={}))
    assert step.ok and not c.there(c.ascii) and not any(c.there(r) for r in c.outs)


def test_a_binary_plt_gone_here_and_changed_there_clears_nothing(tmp_path):
    c = Case(tmp_path)
    (c.dir / c.binary).unlink()
    remote = tmp_path / 'remote' / 'c1' / c.binary
    data = bytearray(remote.read_bytes())
    data[-1] ^= 0xFF
    remote.write_bytes(bytes(data))
    step = c.run(c.plan(binary={}, rst={}))
    assert not step.ok and c.there(c.ascii) and all(c.there(r) for r in c.outs)


def test_a_ledger_entry_without_mtime_clears_nothing_when_the_plt_is_gone(tmp_path):
    c = Case(tmp_path)
    (c.dir / c.binary).unlink()
    del c.ledger.data['local']['c1'][c.binary]['mtime']
    c.run(c.plan(binary={}, rst={}))
    assert c.there(c.ascii) and all(c.there(r) for r in c.outs)


def test_a_cut_short_binary_plt_is_never_deleted(tmp_path):
    c = Case(tmp_path)
    write_plt(c.dir / c.binary, cut=100)
    c.run(c.plan(rst={}))
    assert c.there(c.binary) and c.there(c.ascii)


def test_a_file_not_in_the_plan_is_never_touched(tmp_path):
    c = Case(tmp_path)
    (c.dir / 'RUN_1' / 'riser.500_0.out').write_bytes(b'y')
    c.run()
    assert c.there('RUN_1/riser.500_0.out')


def test_restart_sets_go_without_a_copy_and_say_so(tmp_path):
    c = Case(tmp_path)
    c.run(c.plan(ascii={}, binary={}, out={}))
    assert not any(c.there(r) for r in c.rsts)
    assert any('no copy' in s for s in c.said)


def test_three_remote_failures_in_a_row_stop_the_stage(tmp_path):
    c = Case(tmp_path)
    c.cloud.remote_md5 = lambda case, rel: None                        # md5sum gone there
    steps = {}
    for t in (450, 500, 550, 600):
        a = f'RUN_1/riser.{t}.plt'
        (c.dir / a).write_bytes(b'z')
        (c.dir / f'binary/riser.{t}.plt').write_bytes((c.dir / c.binary).read_bytes())
        c.cloud.put(c.dir / f'binary/riser.{t}.plt', 'c1', f'binary/riser.{t}.plt')
        steps[a] = 1
    step = c.run(c.plan(ascii=steps, binary={}, out={}, rst={}))
    assert not step.ok and 'stopped' in step.detail
    assert all(c.there(r) for r in steps)
