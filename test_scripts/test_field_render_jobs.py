"""`field render --jobs N`: the first step alone (it fixes the colour scale),
the rest in N processes; a failing step in a worker is reported, not fatal."""

import argparse

import pytest

from src.commands.field.render_impl import command as render_cmd
from src.plt import render


def args(tmp_path, **over):
    base = dict(mode="slice", case=None, verbose=False, help=False, vtu=None,
                config=None, write_template=None, timestep=None, zone=None,
                nen=None, color=None, output=str(tmp_path / "out"), contour=None,
                values=None, normal=None, origin=None, slices=None, color_range=None,
                t1=None, t2=None, freq=None, camera=None, pick_camera=None,
                no_vtp=True, body=None, jobs=None)
    base.update(over)
    return argparse.Namespace(**base)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """Steps 100..500 and a renderer that records what it was asked."""
    calls = {"serial": [], "parallel": None}
    steps = [100, 200, 300, 400, 500]
    monkeypatch.setattr(render_cmd, "_resolve_steps",
                        lambda a, cfg, mode, log: (steps, tmp_path, "riser"))

    def step(a, cfg, mode, s, *rest):
        state = rest[-2]
        state["color_range"] = [-1.0, 1.0]
        calls["serial"].append((s, cfg["color"].get("range")))
        return [f"{s}.png"]

    def parallel(a, cfg, mode, rest_steps, *more):
        calls["parallel"] = (list(rest_steps), cfg["color"].get("range"), more[-2])
        return [f"{s}.png" for s in rest_steps]

    monkeypatch.setattr(render_cmd, "_render_step", step)
    monkeypatch.setattr(render_cmd, "_render_parallel", parallel)
    return calls


def test_default_is_serial(fake, tmp_path, capsys):
    render_cmd._render_one_case(args(tmp_path), "slice", render_cmd.Logger())
    assert [s for s, _ in fake["serial"]] == [100, 200, 300, 400, 500]
    assert fake["parallel"] is None


def test_jobs_first_step_alone_then_the_rest_on_its_scale(fake, tmp_path, capsys):
    render_cmd._render_one_case(args(tmp_path, jobs=3), "slice", render_cmd.Logger())
    assert fake["serial"] == [(100, None)]
    rest, scale, jobs = fake["parallel"]
    assert rest == [200, 300, 400, 500] and scale == [-1.0, 1.0] and jobs == 3
    assert "5 images over 5 steps" in capsys.readouterr().out


def test_jobs_capped_by_the_steps(fake, tmp_path, capsys):
    render_cmd._render_one_case(args(tmp_path, jobs=64), "slice", render_cmd.Logger())
    assert fake["parallel"][2] == 5


def test_worker_turns_exit_and_errors_into_a_result(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise RuntimeError("no surface")
    monkeypatch.setattr(render, "render_slice", boom)
    monkeypatch.setattr(render_cmd, "_vtu_for_step", lambda *a: "x.vtu")
    monkeypatch.setattr(render_cmd, "_body_vtu_for_step", lambda *a: None)
    monkeypatch.setattr(render_cmd, "_follow_body_for_step", lambda cfg, *a: cfg["domain"])
    cfg = render.default_config("slice")
    job = (200, args(tmp_path), cfg, "slice", tmp_path, "riser", tmp_path, "out", None, False)
    step, outs, error, steplog, seconds = render_cmd._step_worker(job)
    assert (step, outs, error) == (200, [], "see the error above")
    # the worker's messages come back to be printed with its line
    assert ("error", "rendering failed (timestep 200): no surface") in steplog.lines


def test_progress_says_a_warning_once_and_the_step_line(capsys):
    p = render_cmd._Progress(3, "iso", None, verbose=False)
    for n, (step, v) in enumerate([(100, 341.1), (200, 281.8)], 1):
        log = render_cmd._StepLog()
        log.warning(f"isosurface at its 99% percentile, {v}")
        log.notes.update(converted=4.2, points=6892, isovalues=[v])
        p.done(n, step, log, ["a.png", "b.png"], 5.0)
    out = capsys.readouterr().out
    assert out.count("percentile") == 1
    assert "converted 4.2 s" in out and "6,892 points" in out and "iso 281.8" in out
    assert "2 images" in out


def test_progress_header_covers_a_warning(capsys):
    p = render_cmd._Progress(2, "iso", None, verbose=False)
    p.covered.append("no isosurface value given")
    p.warn("no isosurface value given: contouring at 341")
    assert capsys.readouterr().out == ""


def test_steps_text():
    assert render_cmd._steps_text([None]) == "latest step"
    assert render_cmd._steps_text([500]) == "step 500"
    assert render_cmd._steps_text([100, 200, 300]) == "3 steps, 100–300 every 100"
    assert render_cmd._steps_text([100, 200, 400]) == "3 steps, 100–400"
