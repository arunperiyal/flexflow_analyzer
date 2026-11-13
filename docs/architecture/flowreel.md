# Writing files for FlowReel

A note for whoever adds this to FlexFlow Analyzer. Nothing here is built yet.

[FlowReel](https://github.com/arunperiyal/FlowReel) makes films of flow simulations. It
does not import this program and this program does not import it. They meet through
plain files only, and this note lists the files FlowReel expects and what should be
added here to write them.

FlowReel's side of this is planned, not built (its `docs/PLAN.md`, Sections 5.4 to 5.6
and Phase 2B). **That plan is the reference**: check the key names there before
writing code here, because they may still change.

## What FlowReel reads

| From a case | How it reaches FlowReel | Written by |
|---|---|---|
| Flow fields and body surfaces | `binary/<problem>.<step>.plt`, read by FlowReel itself; or VTU files | the solver; or `field extract` |
| Bodies: zone, axis, diameter, supports (boundary conditions) | the `bodies:` block of the film project's `flowreel.yml` | **to add here** (section 1) |
| Time histories: probe displacements, surface forces, the pendulum | CSV files | `data table --output`, with **two additions** (sections 2 and 3) |

FlowReel does not read `domain.yml`, the `.def`, or the OTHD and OISD files of a case
with several bodies. This program already understands all of those, so it does the
translating.

## 1. A `flowreel.yml` writer in the `field` command

Add a subcommand that writes the `bodies:` block from what the case already says:

```text
flexflow field flowreel <case_dir> [--output flowreel.yml] [--body NAME ...] [--stdout]
```

| Flag | Meaning |
|---|---|
| `--output FILE` | where to write; default `<case_dir>/flowreel.yml`. If the file exists, replace only its `bodies:` block and leave every other key as it is |
| `--body NAME` | only these bodies (name, geotag or plttag, as `DomainConfig.body` resolves them); default all |
| `--stdout` | print the block and write nothing |

What to write, for each body in `domain.yml`:

```yaml
bodies:
  cyl:                               # the body's name in domain.yml
    zone: cyl                        # plttag
    axis: x                          # geometry.axis, without the sign
    diameter: 1.0                    # 2 * geometry.radius; leave the key out when radius is null
    ends:
      - {at: 0.0, support: pinned}                                   # at pnt1
      - {at: 500.0, support: roller, free_along: x, tension: true}   # at pnt2
```

- **`at`** is the end's coordinate along the body's axis, in the case's length unit:
  the component of `pnt1` and of `pnt2` along `geometry.axis`.
- **`support`** comes from the `beamSolid`'s `bcType` in the `.def`. The Analyzer does
  not read `bcType` today; `def_config.py` only notes that `fixFix` is not arithmetic.
  FlowReel's support names are `clamped`, `pinned`, `roller`, `spring`, `free` and
  `prescribed`.

  | `bcType` | at `pnt1` | at `pnt2` |
  |---|---|---|
  | `fixFix` | `clamped` | `clamped` |
  | pin-roll (spelling to be taken from the solver) | `pinned` | `roller`, with `free_along` the body's axis |
  | anything not in this table | leave `support` out and print a note, as `derive_from_def` does for what it cannot know |

- **`tension: true`** on the end that carries top tension, when the `.def` says so.
  Which key holds it is not known here yet.
- A body of type `rigid` or `fixed` gets `zone` and, when known, `diameter`, and no
  `ends`.
- Do not write keys FlowReel does not know: it treats unknown keys as errors.

The join from a `beamSolid` to its body is the one `_derive_beam` in
`src/core/domain.py` already makes (`surfaceOutputs`, then the `outputSurface`, then the
`.srf` file's tag), so the new code should reuse it.

## 2. All probes of a body in one CSV

`data table --output` writes one node per file (`--node N`). FlowReel draws a body's
whole centreline and maps of span against time, so it needs every node of an output
group in one file, in long form:

```text
flexflow data table <case> --var aleDisp --all-nodes --othid 1 --output riser_disp.csv
```

```csv
time,node,aleDisp_x,aleDisp_y,aleDisp_z
250.00,0,0.0,0.0000,0.0
250.00,1,0.0,0.0123,0.0
```

- **`--all-nodes`**: every node of the group, one row per time and node, with a `node`
  column counting from 0 in the order of the records.
- A `time` column in the solver's time, not only `tsId`.
- A second small file saying where each node is along the span, which FlowReel needs to
  place the probes. The `othd.<block>.map` already has the undeformed coordinates:

```text
flexflow data table <case> --othid 1 --stations --output riser_nodes.csv
```

```csv
node,station
0,0.0
1,0.25
```

  `station` is the node's coordinate along the body's axis.

The same for surface forces by `--osgid` (`totTrac`), which has one row per time and
needs no `node` column.

## 3. The pendulum as CSV

`plot --var pd` and `data show --pendulum` show `pendDisp`, `pendVel` and `pendAccel`;
there should be a CSV of them too:

```text
flexflow data table <case> --var pendDisp,pendVel,pendAccel --output pendulum.csv
```

```csv
time,pendDisp,pendVel,pendAccel
```

FlowReel draws the pendulum from these numbers and does not solve anything. What they
mean (an angle or a length, the pivot, the plane of swing, the pendulum's length) is
not in the OTHD file; if the `.def` says it, section 1's writer could add a virtual
body for it. That part of FlowReel's plan is the least settled, so leave it until the
plan there is firm.

## 4. VTU for FlowReel, with `field extract`

FlowReel reads `field extract`'s `.pvd` and `.vtu` output through its `vtk` adapter. For
that the extract must keep:

- **Cells**, not only points (the `.vtu` and `.pvd` outputs already do).
- **Velocity and pressure**: `U`, `V`, `W` and `Pressure`. FlowReel computes vorticity,
  Q and lambda2 itself from velocity and ignores the stored `xVor`, `yVor`, `zVor` and
  `QCriterion`, so they need not be extracted.
- **The deformed coordinates** of each step, as in the PLT.
- **The solver's time** of each step in the `.pvd` (`timestep="250.0"`), not the step
  number; otherwise the film's clock has to be told the time step by hand.
- **The body as its own file series**: a second extract with `--zone cyl`, so FlowReel
  can take the wall surface from it.
- **A box** to cut the volume by, for long cases where a whole step is too large:
  check whether `field extract` can already limit the region, and add `--box` if not.

For large cases FlowReel reads the PLT files directly and cuts its own window, so the
extract is for small regions made once, and for sharing data with someone who has no
PLT reader.
