"""Tests for src/web/services/frame.py: resolving a map's block to its domain.yml body."""

from src.core.domain import DomainConfig
from src.web.services.frame import resolve_body, resolve_output


def _domain(tmp_path, text):
    path = tmp_path / 'domain.yml'
    path.write_text(text)
    return DomainConfig(path)


def test_resolve_body_finds_the_body_naming_this_block(tmp_path):
    domain = _domain(tmp_path, """
bodies:
  - name: cyl
    type: beam
    geometry:
      origin: [0, 0, 0]
      axis: '+z'
      length: 50.0
    outputs:
      - block: riser_probe
        nodes: riser.cyl_nodes.nbc
""")
    body = resolve_body(domain, 'riser_probe')
    assert body is not None
    assert body['name'] == 'cyl'

    output = resolve_output(domain, 'riser_probe')
    assert output['nodes'] == 'riser.cyl_nodes.nbc'


def test_resolve_body_returns_none_for_an_unclaimed_block(tmp_path):
    domain = _domain(tmp_path, """
bodies:
  - name: cyl
    type: beam
    outputs:
      - block: riser_probe
""")
    assert resolve_body(domain, 'other_block') is None
    assert resolve_output(domain, 'other_block') is None


def test_resolve_body_with_no_domain_yml_returns_none(tmp_path):
    domain = DomainConfig(tmp_path / 'domain.yml')
    assert domain.exists is False
    assert resolve_body(domain, 'riser_probe') is None
