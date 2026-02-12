"""
HPC partition definitions and SLURM directive management.

Encodes the cluster-specific partition constraints (cores, nodes, walltime)
and provides helpers for generating and validating #SBATCH directives.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PartitionConfig:
    """Constraints and recommended SBATCH settings for one partition."""
    name: str
    description: str
    max_cores: Optional[int]        # max total cores (None = no fixed limit)
    max_nodes: Optional[int]        # max nodes (None = no fixed limit)
    max_walltime_hours: int         # maximum walltime in hours
    ntasks_per_node_fixed: Optional[int] = None  # if not None, must not be changed
    node_sharing: bool = True       # whether nodes are shared between jobs

    @property
    def max_walltime_str(self) -> str:
        h = self.max_walltime_hours
        return f'{h:02d}:00:00'


# ---------------------------------------------------------------------------
# Known partitions (from hpc_partitions.md)
# ---------------------------------------------------------------------------

_PARTITIONS = {
    'shared': PartitionConfig(
        name='shared',
        description='Serial/OpenMP jobs, node sharing allowed. Max 36 cores.',
        max_cores=36,
        max_nodes=1,
        max_walltime_hours=72,
        ntasks_per_node_fixed=None,
        node_sharing=True,
    ),
    'medium': PartitionConfig(
        name='medium',
        description='Single/multi-node MPI jobs, exclusive nodes. ntasks-per-node=40 required.',
        max_cores=None,
        max_nodes=10,
        max_walltime_hours=72,
        ntasks_per_node_fixed=40,
        node_sharing=False,
    ),
    'large': PartitionConfig(
        name='large',
        description='Multi-node jobs needing >3 day walltime. Lower priority.',
        max_cores=None,
        max_nodes=10,
        max_walltime_hours=168,
        ntasks_per_node_fixed=40,
        node_sharing=False,
    ),
    'gpu': PartitionConfig(
        name='gpu',
        description='GPU partition.',
        max_cores=None,
        max_nodes=None,
        max_walltime_hours=72,
        ntasks_per_node_fixed=None,
        node_sharing=False,
    ),
}


class HpcPartition:
    """Query and apply HPC partition information."""

    KNOWN = list(_PARTITIONS.keys())

    @classmethod
    def get(cls, name: str) -> Optional[PartitionConfig]:
        """Return PartitionConfig for *name*, or None if unknown."""
        return _PARTITIONS.get(name)

    @classmethod
    def is_known(cls, name: str) -> bool:
        return name in _PARTITIONS

    @classmethod
    def sbatch_directives(cls, name: str) -> dict:
        """
        Return a dict of #SBATCH flag → value for the given partition.
        Only includes directives that *must* be set for this partition.
        """
        cfg = _PARTITIONS.get(name)
        if cfg is None:
            return {'-p': name}

        directives: dict = {'-p': name}
        if cfg.ntasks_per_node_fixed is not None:
            directives['--ntasks-per-node'] = str(cfg.ntasks_per_node_fixed)
        return directives

    @classmethod
    def summary_lines(cls) -> list:
        """Return a list of (name, description, max_walltime) tuples for display."""
        return [
            (p.name, p.description, p.max_walltime_str)
            for p in _PARTITIONS.values()
        ]
