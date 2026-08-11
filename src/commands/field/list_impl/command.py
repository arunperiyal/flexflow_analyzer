"""
Field list command -- what you are allowed to name in a config or on a flag.

The colour presets and the derived variables are both things you have to know
the name of before you can use them, and neither is discoverable from the data:
a colormap lives in matplotlib and a derived variable lives in this codebase.
"""

import sys

from ....utils.logger import Logger


# matplotlib groups its colormaps, but not in a way that says which suit a
# field. These are the ones worth reaching for, and why.
GROUPS = [
    ("DIVERGING", "a signed field with a meaningful zero -- velocity, "
                  "vorticity, lambda2. Pair with a symmetric --color-range.",
     ["coolwarm", "RdBu", "RdBu_r", "bwr", "seismic", "PiYG", "PRGn",
      "BrBG", "PuOr", "RdYlBu", "Spectral"]),
    ("SEQUENTIAL", "a magnitude, or anything one-signed -- speed, pressure "
                   "magnitude, Q-criterion above zero.",
     ["viridis", "plasma", "inferno", "magma", "cividis", "turbo",
      "Blues", "Reds", "Greys", "YlGnBu", "YlOrRd", "hot", "jet"]),
    ("CYCLIC", "a phase or angle, where the ends must meet.",
     ["twilight", "twilight_shifted", "hsv"]),
]

AVOID = ("tab10", "tab20", "Set1", "Set2", "Set3", "Accent", "Paired", "Dark2")


def _print_colors(logger, verbose=False):
    from ....plt.render import PRESET_CMAP
    from ....utils.colors import Colors

    try:
        import matplotlib.pyplot as plt
        known = set(plt.colormaps())
    except ImportError:
        known = None

    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Colormaps for color.preset "
          f"(field render iso / slice){Colors.RESET}")
    print()
    for name, why, maps in GROUPS:
        shown = [m for m in maps if known is None or m in known]
        print(f"  {Colors.BOLD}{name}{Colors.RESET} -- {why}")
        print(f"    {Colors.YELLOW}{'  '.join(shown)}{Colors.RESET}")
        print()

    print(f"  {Colors.BOLD}AVOID for field data{Colors.RESET} -- these are "
          f"qualitative: their colours are")
    print(f"  unordered categories, so a continuous field reads as banding.")
    print(f"    {Colors.DIM}{'  '.join(AVOID)}{Colors.RESET}")
    print()
    print(f"  {Colors.BOLD}PARAVIEW PRESET NAMES{Colors.RESET} -- accepted and "
          f"translated, so a colormap")
    print(f"  chosen in ParaView can be named as ParaView spells it:")
    for pv_name, mpl in sorted(PRESET_CMAP.items()):
        print(f"    {Colors.YELLOW}{pv_name:<26}{Colors.RESET} -> {mpl}")
    print()
    print(f"  {Colors.DIM}Any matplotlib colormap works, not only those above; "
          f"append _r to reverse\n  one (coolwarm_r). "
          + (f"{len(known)} are installed." if known else
             "matplotlib is not installed, so this list is unverified.")
          + f"{Colors.RESET}")
    print()

    if verbose and known:
        print(f"  {Colors.BOLD}ALL INSTALLED{Colors.RESET}")
        every = sorted(m for m in known if not m.endswith("_r"))
        for i in range(0, len(every), 6):
            print("    " + "  ".join(f"{m:<16}" for m in every[i:i + 6]).rstrip())
        print()


def _print_variables(logger):
    from ....plt import derive
    from ....utils.colors import Colors

    print()
    print(f"{Colors.BOLD}{Colors.CYAN}Variables FlexFlow can compute{Colors.RESET}")
    print()
    print(f"  {Colors.DIM}Name one as contour.variable or color.variable and it "
          f"is worked out from\n  the file's own data when the solver did not "
          f"write it.{Colors.RESET}")
    print()
    for name, needs, what in derive.describe():
        print(f"    {Colors.YELLOW}{name:<12}{Colors.RESET} from {needs:<8} {what}")
    print()
    print(f"  {Colors.DIM}For what a particular case carries already, use "
          f"`field info <case> --variables`.{Colors.RESET}")
    print()


def execute_list(args):
    from .help_messages import print_list_help

    if getattr(args, "help", False):
        print_list_help(); return

    logger = Logger(verbose=getattr(args, "verbose", False))
    wanted = [k for k in ("color", "variables") if getattr(args, k, False)]

    if not wanted:
        # Nothing named: this is someone finding out what there is to list.
        print_list_help()
        sys.exit(0)

    if "color" in wanted:
        _print_colors(logger, verbose=getattr(args, "verbose", False))
    if "variables" in wanted:
        _print_variables(logger)
