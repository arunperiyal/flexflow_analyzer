"""Tests for run sq --sort behavior."""

from pathlib import Path

from rich.console import Group

from src.commands.run.sq_impl import command as sq_cmd


def test_parse_queue_output_keeps_raw_fields():
    output = "12|jobA|RUNNING|01:02:03|2|shared|16|2048|2025-01-02T03:04:05|None|afterok:1234"
    jobs = sq_cmd.parse_queue_output(output)

    assert len(jobs) == 1
    job = jobs[0]
    assert job["memory_raw"] == "2048"
    assert job["submit_raw"] == "2025-01-02T03:04:05"
    assert job["memory"] == "2G"
    assert job["dependency"] == "1234"


def test_sort_jobs_by_jobid_is_numeric():
    jobs = [
        {"jobid": "100"},
        {"jobid": "2"},
        {"jobid": "15"},
    ]

    sorted_jobs = sq_cmd.sort_jobs(jobs, "jobid")
    assert [job["jobid"] for job in sorted_jobs] == ["2", "15", "100"]


def test_sort_jobs_by_submitted_alias_uses_raw_timestamp():
    jobs = [
        {"jobid": "1", "submit": "10:10", "submit_raw": "2026-05-01T10:10:00"},
        {"jobid": "2", "submit": "08:00", "submit_raw": "2026-04-30T08:00:00"},
        {"jobid": "3", "submit": "11:15", "submit_raw": "2026-05-02T11:15:00"},
    ]

    sorted_jobs = sq_cmd.sort_jobs(jobs, "submitted")
    assert [job["jobid"] for job in sorted_jobs] == ["2", "1", "3"]


def test_sort_jobs_by_memory_handles_units():
    jobs = [
        {"jobid": "A", "memory_raw": "2G", "memory": "2G"},
        {"jobid": "B", "memory_raw": "512M", "memory": "512M"},
        {"jobid": "C", "memory_raw": "1024", "memory": "1G"},
    ]

    sorted_jobs = sq_cmd.sort_jobs(jobs, "memory")
    assert [job["jobid"] for job in sorted_jobs] == ["B", "C", "A"]


def test_sort_jobs_by_time_parses_slurm_elapsed():
    jobs = [
        {"jobid": "A", "time": "1-00:00:00"},
        {"jobid": "B", "time": "2:00"},
        {"jobid": "C", "time": "01:00:00"},
    ]

    sorted_jobs = sq_cmd.sort_jobs(jobs, "time")
    assert [job["jobid"] for job in sorted_jobs] == ["B", "C", "A"]


def test_grouped_watch_renderable_uses_group():
    jobs = [
        {
            "jobid": "1",
            "name": "mainCase001",
            "state": "PENDING",
            "time": "0:00",
            "nodes": "3",
            "partition": "medium",
            "cpus": "120",
            "memory": "4300M",
            "submit": "05-06 14:48",
            "reason": "(Priority)",
            "dependency": "—",
            "workdir": "/scratch/project/a/Case001",
        },
        {
            "jobid": "2",
            "name": "mainCase002",
            "state": "PENDING",
            "time": "0:00",
            "nodes": "3",
            "partition": "medium",
            "cpus": "120",
            "memory": "4300M",
            "submit": "05-06 16:32",
            "reason": "(Priority)",
            "dependency": "—",
            "workdir": "/scratch/project/b/Case002",
        },
    ]

    renderable = sq_cmd.create_grouped_queue_renderable(jobs)
    assert isinstance(renderable, Group)
    assert len(renderable.renderables) == 2


def test_resolve_stdout_path_joins_relative_with_workdir():
    resolved = sq_cmd._resolve_stdout_path("slurm-123.out", "/scratch/demo/run")
    assert resolved == Path("/scratch/demo/run/slurm-123.out")


def test_resolve_stdout_path_keeps_absolute():
    resolved = sq_cmd._resolve_stdout_path("/scratch/demo/slurm-123.out", "/scratch/demo/run")
    assert resolved == Path("/scratch/demo/slurm-123.out")


def test_tail_file_lines_reads_last_n(tmp_path):
    out_file = tmp_path / "slurm.out"
    out_file.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")
    tail_lines = sq_cmd._tail_file_lines(out_file, 2)
    assert tail_lines == ["line3\n", "line4\n"]


def _queue_job(jobid, name, workdir=None):
    return {"jobid": jobid, "name": name, "state": "RUNNING", "workdir": workdir}


def test_filter_jobs_matches_name_case_insensitively(monkeypatch):
    monkeypatch.setattr(sq_cmd, "get_job_workdir", lambda job_id: None)
    jobs = [
        _queue_job("1", "mainCS4SG3U3P0"),
        _queue_job("2", "postCS4SG3U3P0"),
        _queue_job("3", "mainCS4SG1U1P0"),
    ]

    matched = sq_cmd.filter_jobs(jobs, "cs4sg3u3p0")
    assert [job["jobid"] for job in matched] == ["1", "2"]


def test_filter_jobs_falls_back_to_workdir(monkeypatch):
    workdirs = {"1": "/scratch/a/CS4SG3U3P0", "2": "/scratch/a/Other"}
    looked_up = []

    def fake_workdir(job_id):
        looked_up.append(job_id)
        return workdirs.get(job_id)

    monkeypatch.setattr(sq_cmd, "get_job_workdir", fake_workdir)
    jobs = [
        _queue_job("1", "job1"),
        _queue_job("2", "job2"),
        _queue_job("3", "mainCS4SG3U3P0"),
    ]

    matched = sq_cmd.filter_jobs(jobs, "CS4SG3U3P0")
    assert [job["jobid"] for job in matched] == ["1", "3"]
    # A job whose name already matches needs no scontrol call
    assert looked_up == ["1", "2"]


def _sq_args(**kw):
    from types import SimpleNamespace
    base = dict(help=False, target=None, value=None, all=False, by_dir=False,
                sort=None, out=False, n=20)
    base.update(kw)
    return SimpleNamespace(**base)


def test_execute_sq_routes_watch_and_find(monkeypatch):
    calls = []
    monkeypatch.setattr(sq_cmd, "check_slurm_available", lambda: True)
    monkeypatch.setattr(sq_cmd, "watch_queue", lambda args, interval: calls.append(("watch", interval)))
    monkeypatch.setattr(sq_cmd, "find_jobs", lambda args, key: calls.append(("find", key)))
    monkeypatch.setattr(sq_cmd, "show_job_detail", lambda job_id, **kw: calls.append(("detail", job_id)))

    sq_cmd.execute_sq(_sq_args(target="watch"))
    sq_cmd.execute_sq(_sq_args(target="watch", value="2.5"))
    sq_cmd.execute_sq(_sq_args(target="find", value="CS4SG3U3P0"))
    sq_cmd.execute_sq(_sq_args(target="1258586"))
    assert calls == [("watch", 10.0), ("watch", 2.5), ("find", "CS4SG3U3P0"), ("detail", "1258586")]


def test_execute_sq_rejects_bad_watch_and_missing_find_key(monkeypatch, capsys):
    monkeypatch.setattr(sq_cmd, "check_slurm_available", lambda: True)
    monkeypatch.setattr(sq_cmd, "watch_queue", lambda *a: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(sq_cmd, "find_jobs", lambda *a: (_ for _ in ()).throw(AssertionError))

    sq_cmd.execute_sq(_sq_args(target="watch", value="soon"))
    sq_cmd.execute_sq(_sq_args(target="watch", value="0"))
    sq_cmd.execute_sq(_sq_args(target="find"))
    out = capsys.readouterr().out
    assert "must be a number" in out
    assert "positive" in out
    assert "requires a search key" in out
