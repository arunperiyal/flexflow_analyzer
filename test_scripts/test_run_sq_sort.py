"""Tests for run sq --sort behavior."""

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
