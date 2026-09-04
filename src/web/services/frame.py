"""services/frame.py — domain.yml → the body behind a probe set.

`bodies[].outputs[].block` is the outputTimeHistory block name, and
`othd.<block>.map` is built on that same name — so a probe set resolves to
its body with a dictionary lookup, no convention re-derived.
"""

from typing import Optional

from src.core.domain import DomainConfig


def resolve_body(domain: DomainConfig, block_name: str) -> Optional[dict]:
    """The body whose outputs[] names `block_name`, or None (no domain.yml,
    or no body claims this block)."""
    if not domain.exists:
        return None
    for body in domain.bodies:
        for out in body.get('outputs') or []:
            if out.get('block') == block_name:
                return body
    return None


def resolve_output(domain: DomainConfig, block_name: str) -> Optional[dict]:
    """The outputs[] entry itself — carries `nodes`, the node-file cross-check."""
    if not domain.exists:
        return None
    for body in domain.bodies:
        for out in body.get('outputs') or []:
            if out.get('block') == block_name:
                return out
    return None
