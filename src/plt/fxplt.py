"""
fxplt.py  --  Reader for FlexFlow Tecplot binary (.plt, "#!TDV112") output.

FlexFlow's Tecplot binary writer is *mostly* standard TDV112 but trips up
ParaView/Tecplot's own readers (they fall back to the surface zone with no
data arrays). This module parses the file directly with numpy, exposes the
zone/variable layout, loads a chosen zone's nodal data + connectivity, and
*detects/recovers truncated files* (a run killed mid-write leaves a partial
connectivity block).

Layout assumptions (verified against the cylinder_12 cases):
  - All nodal variables, block (var-major) ordering, float32.
  - Element connectivity is 0-based int32, nodes-per-element from zone type.

Typical use:
    from src.plt.fxplt import PltFile
    p = PltFile("riser.5000.plt")
    print(p.summary())
    zi = p.first_volume_zone()
    pts, conn, pdata, info = p.load_zone(zi)   # info['truncated'], etc.
"""
import struct
import numpy as np

EOH_MARKER = 357.0
ZONE_MARKER = 299.0
FMT_SIZE = {1: 4, 2: 8, 3: 4, 4: 2, 5: 1, 6: 1}      # Tecplot data-format codes
FMT_NP = {1: "<f4", 2: "<f8", 3: "<i4", 4: "<i2", 5: "<i1"}
# nodes-per-element by Tecplot zone-type code:
#   1=FELINESEG(2) 2=FETRIANGLE(3) 3=FEQUADRILATERAL(4)
#   4=FETETRAHEDRON(4) 5=FEBRICK(8)
# WARNING: the zone type cannot always be trusted -- e.g. an 8-node hex mesh
# written with simflow.config nen=4 comes out labelled ztype 4 (tet) carrying
# only 4 of 8 nodes. Use load_zone(zi, nen=...) to force the true
# nodes-per-element when the header is wrong.
NPE = {1: 2, 2: 3, 3: 4, 4: 4, 5: 8}
ZTYPE_VTK = {2: "triangle", 3: "quad", 4: "tetra", 5: "hexahedron"}
VOLUME_ZTYPES = (4, 5)


class PltFile:
    def __init__(self, path):
        self.path = str(path)
        self.vars = []
        self.zones = []          # list of dicts: name, ztype, npts, nelem
        self._data_start = None  # byte offset of the data section (after EOH)
        self._parse_header()

    # ---- header / zone records -------------------------------------------
    def _parse_header(self):
        f = open(self.path, "rb")
        self._f = f

        def i32():
            return struct.unpack("<i", f.read(4))[0]

        def f32():
            return struct.unpack("<f", f.read(4))[0]

        def f64():
            return struct.unpack("<d", f.read(8))[0]

        def tstr():
            s = []
            while True:
                c = i32()
                if c == 0:
                    break
                s.append(chr(c))
            return "".join(s)

        magic = f.read(8)
        if magic != b"#!TDV112":
            raise ValueError("not a TDV112 Tecplot binary file: %r" % magic)
        assert i32() == 1, "byte-order check failed"
        self.filetype = i32()
        self.title = tstr()
        nvar = i32()
        self.vars = [tstr() for _ in range(nvar)]

        while True:
            m = f32()
            if abs(m - EOH_MARKER) < 1e-3:
                break
            assert abs(m - ZONE_MARKER) < 1e-3, ("bad zone marker", m)
            name = tstr()
            i32()                       # parent zone
            i32()                       # strand id
            f64()                       # solution time
            i32()                       # default zone color
            ztype = i32()
            if i32() == 1:              # var location specified
                for _ in range(nvar):
                    i32()
            i32()                       # raw face neighbours
            if i32() > 0:               # user-defined face neighbour conns
                i32()
            npts = i32()
            nelem = i32()
            i32(); i32(); i32()         # i/j/k cell dims (reserved)
            while i32() == 1:           # auxiliary name/value pairs
                tstr(); i32(); tstr()
            self.zones.append(dict(name=name, ztype=ztype, npts=npts, nelem=nelem))
        self._data_start = f.tell()

    # ---- helpers ----------------------------------------------------------
    def first_volume_zone(self):
        for i, z in enumerate(self.zones):
            if z["ztype"] in VOLUME_ZTYPES:
                return i
        return 0

    def summary(self):
        import os
        lines = ["file: %s (%d bytes)" % (self.path, os.path.getsize(self.path))]
        lines.append("vars (%d): %s" % (len(self.vars), ", ".join(self.vars)))
        for i, z in enumerate(self.zones):
            lines.append("  zone %d '%s'  ztype=%d  npts=%d  nelem=%d"
                         % (i, z["name"], z["ztype"], z["npts"], z["nelem"]))
        return "\n".join(lines)

    def _read_data_preamble(self, f, nvar):
        """Read one zone's data-section preamble; return (fmts, present_mask, shareconn)."""
        def i32():
            return struct.unpack("<i", f.read(4))[0]

        def f32():
            return struct.unpack("<f", f.read(4))[0]

        m = f32()
        assert abs(m - ZONE_MARKER) < 1e-3, ("bad data marker", m)
        fmts = [i32() for _ in range(nvar)]
        passive = [0] * nvar
        if i32() == 1:
            passive = [i32() for _ in range(nvar)]
        shared = [-1] * nvar
        if i32() == 1:
            shared = [i32() for _ in range(nvar)]
        shareconn = i32()
        present = [(passive[v] == 0 and shared[v] == -1) for v in range(nvar)]
        # min/max doubles for each present var
        for v in range(nvar):
            if present[v]:
                f.read(16)
        return fmts, present, shareconn

    def minmax(self, zi=0):
        """Return {var: (min, max) or None} for a zone, read from the header (no bulk load)."""
        nvar = len(self.vars)
        f = open(self.path, "rb")
        f.seek(self._data_start)

        # skip the data of any zones before the target
        for j in range(zi):
            zt = self.zones[j]
            fmts, present, shareconn = self._read_data_preamble(f, nvar)
            for v in range(nvar):
                if present[v]:
                    f.seek(zt["npts"] * FMT_SIZE[fmts[v]], 1)
            if shareconn == -1 and zt["ztype"] in NPE:
                f.seek(zt["nelem"] * NPE[zt["ztype"]] * 4, 1)

        # read the target zone's preamble manually, keeping the min/max doubles
        def i32():
            return struct.unpack("<i", f.read(4))[0]

        def f32():
            return struct.unpack("<f", f.read(4))[0]

        def f64():
            return struct.unpack("<d", f.read(8))[0]

        assert abs(f32() - ZONE_MARKER) < 1e-3, "bad data marker"
        fmts = [i32() for _ in range(nvar)]
        passive = [0] * nvar
        if i32() == 1:
            passive = [i32() for _ in range(nvar)]
        shared = [-1] * nvar
        if i32() == 1:
            shared = [i32() for _ in range(nvar)]
        i32()  # shareconn
        out = {}
        for v in range(nvar):
            if passive[v] == 0 and shared[v] == -1:
                out[self.vars[v]] = (f64(), f64())
            else:
                out[self.vars[v]] = None
        return out

    # ---- main loader ------------------------------------------------------
    def load_zone(self, zi, nen=None):
        """Load nodal data + connectivity for zone `zi`.

        nen : override nodes-per-element (default: from the zone type). Use this
              when the writer mislabels the zone (e.g. an 8-node hex mesh emitted
              as ztype 4 / 4-node because of simflow.config nen=4).

        Returns (points[N,3] f32, conn[M,npe] int64, point_data{name:array},
                 info{truncated, nhex_file, nhex_valid, ...}).
        Skips any preceding zones' data correctly. Detects truncation and
        clips connectivity to the leading all-valid prefix.
        """
        nvar = len(self.vars)
        f = open(self.path, "rb")
        f.seek(self._data_start)

        # advance through zones before the target
        for j in range(zi):
            zt = self.zones[j]
            fmts, present, shareconn = self._read_data_preamble(f, nvar)
            for v in range(nvar):
                if present[v]:
                    f.seek(zt["npts"] * FMT_SIZE[fmts[v]], 1)
            if shareconn == -1 and zt["ztype"] in NPE:
                f.seek(zt["nelem"] * NPE[zt["ztype"]] * 4, 1)

        z = self.zones[zi]
        npts, nelem, ztype = z["npts"], z["nelem"], z["ztype"]
        fmts, present, shareconn = self._read_data_preamble(f, nvar)

        cols = {}
        for v in range(nvar):
            if not present[v]:
                cols[self.vars[v]] = None
                continue
            arr = np.fromfile(f, dtype=FMT_NP[fmts[v]], count=npts)
            if arr.size < npts:
                raise IOError("truncated inside variable '%s' (%d/%d values)"
                              % (self.vars[v], arr.size, npts))
            cols[self.vars[v]] = arr.astype("<f4")

        npe = nen if nen is not None else NPE.get(ztype, 8)
        info = dict(zone=zi, npts=npts, nelem=nelem, ztype=ztype, npe=npe,
                    nen_declared=NPE.get(ztype), nen_override=nen,
                    truncated=False, nhex_file=nelem, nhex_valid=nelem)
        if shareconn == -1:
            raw = np.fromfile(f, dtype="<i4", count=nelem * npe)
            nhex_file = raw.size // npe
            conn = raw[:nhex_file * npe].reshape(nhex_file, npe)
            good = ((conn >= 0) & (conn < npts)).all(axis=1)
            nvalid = int(np.argmin(good)) if not good.all() else nhex_file
            if nhex_file < nelem or nvalid < nhex_file:
                info["truncated"] = True
            info["nhex_file"] = nhex_file
            info["nhex_valid"] = nvalid
            conn = conn[:nvalid].astype(np.int64)
        else:
            conn = None  # connectivity shared from another zone

        pts = np.ascontiguousarray(
            np.column_stack([cols[self.vars[0]], cols[self.vars[1]],
                             cols[self.vars[2]]]).astype("<f4"))
        pdata = {self.vars[v]: np.ascontiguousarray(cols[self.vars[v]])
                 for v in range(3, nvar) if cols[self.vars[v]] is not None}
        return pts, conn, pdata, info


if __name__ == "__main__":
    import sys
    p = PltFile(sys.argv[1])
    print(p.summary())
