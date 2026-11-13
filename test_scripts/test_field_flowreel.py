import yaml

from src.commands.field.flowreel_impl.command import execute_flowreel


def test_flowreel_writes_bodies_and_preserves_project_keys(tmp_path):
    (tmp_path / "domain.yml").write_text(
        "version: 1\n"
        "bodies:\n"
        "  - name: cyl\n"
        "    type: beam\n"
        "    plttag: cyl\n"
        "    geometry:\n"
        "      axis: +x\n"
        "      length: 10\n"
        "      radius: 0.5\n"
    )
    target = tmp_path / "flowreel.yml"
    target.write_text("frame_rate: 30\n")

    class Args:
        case = str(tmp_path)
        output = str(target)
        body = None
        stdout = False
        verbose = False

    execute_flowreel(Args())
    project = yaml.safe_load(target.read_text())
    assert project["frame_rate"] == 30
    assert project["bodies"]["cyl"] == {
        "zone": "cyl",
        "axis": "x",
        "diameter": 1.0,
    }
