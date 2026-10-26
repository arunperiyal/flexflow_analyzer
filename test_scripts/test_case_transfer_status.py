"""`case upload|download` carry .casestatus.md: copied when the other side
has none, merged when both do (the notes of the copy changed last, the log
of both), and only the destination is written."""

import io
import os
import time
from pathlib import Path

import pytest
from rich.console import Console

from src.core import case_status as cs
from src.commands.case.download_impl.command import CaseUploadCommand as Transfer


class FakeSFTP:
    def __init__(self, files):
        self.files = files                       # path -> [bytes, mtime]

    def open(self, path):
        return io.BytesIO(self.files[path][0])

    def stat(self, path):
        return type('St', (), {'st_mtime': self.files[path][1]})()


class FakeSSH:
    def __init__(self):
        self.files = {}
        self.sftp_client = FakeSFTP(self.files)

    def remote_path_exists(self, path):
        return path in self.files

    def upload_file(self, local, remote, callback=None):
        self.files[remote] = [Path(local).read_bytes(), time.time()]


NOTES_HERE = ('---\nstate: running\n---\n# C1\nlaptop notes\n\n## Log\n'
              '- 2026-10-01 10:00  created\n- 2026-10-21 08:00  laptop note\n')
NOTES_THERE = ('---\nstate: done\n---\n# C1\n\n## Log\n- 2026-10-01 10:00  created\n'
               '- 2026-10-20 14:02  main job 1 started\n- 2026-10-22 09:00  state: running -> done\n')


@pytest.fixture
def setup(tmp_path):
    t = Transfer()
    t.console = Console(file=io.StringIO(), width=120, color_system=None)
    case = tmp_path / 'C1'
    case.mkdir()
    return t, FakeSSH(), case


def said(t):
    return t.console.file.getvalue()


def test_copied_when_only_the_source_has_it(setup):
    t, ssh, case = setup
    (case / cs.FILENAME).write_text(NOTES_HERE)
    t.sync_case_status(ssh, '/r/C1', str(case), is_upload=True)
    assert ssh.files['/r/C1/' + cs.FILENAME][0].decode() == NOTES_HERE
    assert 'copied' in said(t)


def test_download_with_no_remote_copy_leaves_the_local_one(setup):
    t, ssh, case = setup
    (case / cs.FILENAME).write_text(NOTES_HERE)
    t.sync_case_status(ssh, '/r/C1', str(case), is_upload=False)
    assert (case / cs.FILENAME).read_text() == NOTES_HERE and not ssh.files


def test_download_merges_the_cluster_log_into_the_local_notes(setup):
    t, ssh, case = setup
    (case / cs.FILENAME).write_text(NOTES_HERE)
    ssh.files['/r/C1/' + cs.FILENAME] = [NOTES_THERE.encode(), 0]      # older than local
    t.sync_case_status(ssh, '/r/C1', str(case), is_upload=False)
    meta, body = cs.read(case)
    assert meta['state'] == 'running' and 'laptop notes' in body        # local is newer
    assert [e.split('  ', 1)[1] for e in cs.log_entries(body)] == [
        'created', 'main job 1 started', 'laptop note', 'state: running -> done']
    assert 'merged (notes from here, 2 log line(s) added)' in said(t)
    assert ssh.files['/r/C1/' + cs.FILENAME][0] == NOTES_THERE.encode()  # source untouched


def test_upload_keeps_the_newer_remote_notes(setup):
    t, ssh, case = setup
    (case / cs.FILENAME).write_text(NOTES_HERE)
    os.utime(case / cs.FILENAME, (1000, 1000))
    ssh.files['/r/C1/' + cs.FILENAME] = [NOTES_THERE.encode(), 2000]   # job wrote it later
    t.sync_case_status(ssh, '/r/C1', str(case), is_upload=True)
    meta, body = cs.split(ssh.files['/r/C1/' + cs.FILENAME][0].decode())
    assert meta['state'] == 'done'                  # not overwritten by the stale laptop copy
    assert 'laptop note' in body and 'main job 1 started' in body
    assert 'notes from the remote, 1 log line(s) added' in said(t)


def test_same_on_both_sides(setup):
    t, ssh, case = setup
    (case / cs.FILENAME).write_text(NOTES_HERE)
    ssh.files['/r/C1/' + cs.FILENAME] = [NOTES_HERE.encode(), 0]
    t.sync_case_status(ssh, '/r/C1', str(case), is_upload=True)
    assert 'already up to date' in said(t)


def test_a_failure_does_not_fail_the_transfer(setup):
    t, ssh, case = setup
    (case / cs.FILENAME).write_text(NOTES_HERE)
    def boom(*a, **k):
        raise IOError('disk full')
    ssh.upload_file = boom
    t.sync_case_status(ssh, '/r/C1', str(case), is_upload=True)
    assert 'not carried: disk full' in said(t)


def test_merge_keeps_untimed_entries_in_place():
    newer = '# X\n\n## Log\n- 2026-01-02 00:00  b\n'
    older = '# X\n\n## Log\n- 2026-01-01 00:00  a\n- hand-written, no time\n- 2026-01-03 00:00  c\n'
    assert cs.log_entries(cs.merge(newer, older)) == [
        '- 2026-01-01 00:00  a', '- hand-written, no time', '- 2026-01-02 00:00  b',
        '- 2026-01-03 00:00  c']
    assert cs.merge(newer, newer) == newer
