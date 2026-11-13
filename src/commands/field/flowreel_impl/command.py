"""Export the body metadata FlowReel cannot read from PLT files."""

from pathlib import Path

import yaml

from ....core.domain import DomainConfig
from ....core.parsers.def_parser import as_file, as_list, parse_blocks
from ....utils.logger import Logger


def _support_ends(case_dir, body):
    """Return known support metadata for a beam, or an empty list."""
    def_file = next(iter(sorted(Path(case_dir).glob("*.def"))), None)
    if not def_file or body.get("type") != "beam":
        return []

    geotag = body.get("geotag")
    for beam in parse_blocks(def_file, kind="beamSolid"):
        surfaces = as_list(beam["values"].get("surfaceOutputs")) or []
        for surface_name in surfaces:
            surface = next(
                (item for item in parse_blocks(def_file, kind="outputSurface")
                 if item["name"] == surface_name),
                None,
            )
            if not surface:
                continue
            if geotag and geotag not in str(as_file(surface["values"].get("surfaces"))):
                continue
            bc_type = str(beam["values"].get("bcType", "")).strip()
            geometry = body.get("geometry") or {}
            axis = geometry.get("axis")
            length = geometry.get("length")
            if bc_type == "fixFix" and length is not None:
                return [
                    {"at": 0.0, "support": "clamped"},
                    {"at": length, "support": "clamped"},
                ]
            if bc_type.lower().replace("_", "-") in {"pin-roll", "pinroll"} and length is not None:
                end_axis = axis.lstrip("+-") if isinstance(axis, str) else axis
                return [
                    {"at": 0.0, "support": "pinned"},
                    {"at": length, "support": "roller", "free_along": end_axis},
                ]
    return []


def _body_entry(case_dir, body):
    geometry = body.get("geometry") or {}
    entry = {"zone": body.get("plttag") or body.get("name")}
    axis = geometry.get("axis")
    if axis:
        entry["axis"] = axis.lstrip("+-") if isinstance(axis, str) else axis
    radius = geometry.get("radius")
    if radius is not None:
        entry["diameter"] = 2 * radius
    ends = _support_ends(case_dir, body)
    if ends:
        entry["ends"] = ends
    return entry


def execute_flowreel(args):
    logger = Logger(verbose=getattr(args, "verbose", False))
    case_dir = Path(args.case).expanduser().resolve()
    domain = DomainConfig.find(case_dir)
    if not domain.exists:
        logger.error(f"No domain.yml found in {case_dir}")
        return

    selected = getattr(args, "body", None)
    bodies = domain.bodies
    if selected:
        wanted = {value.lower() for value in selected}
        bodies = [
            body for body in bodies
            if any(str(body.get(key) or "").lower() in wanted
                   for key in ("name", "geotag", "plttag"))
        ]
    block = {"bodies": {
        body.get("name") or body.get("plttag"): _body_entry(case_dir, body)
        for body in bodies
    }}
    text = yaml.safe_dump(block, sort_keys=False, default_flow_style=False)
    if getattr(args, "stdout", False):
        print(text, end="")
        return

    output = Path(args.output).expanduser() if getattr(args, "output", None) else case_dir / "flowreel.yml"
    if not output.is_absolute():
        output = case_dir / output
    existing = {}
    if output.exists():
        existing = yaml.safe_load(output.read_text()) or {}
        if not isinstance(existing, dict):
            logger.error(f"{output} must contain a YAML mapping")
            return
    existing["bodies"] = block["bodies"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(existing, sort_keys=False, default_flow_style=False))
    logger.success(f"Wrote FlowReel bodies to {output}")
