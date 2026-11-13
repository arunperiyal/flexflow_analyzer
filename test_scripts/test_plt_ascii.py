"""check_ascii_plt: an ASCII PLT is whole when each zone holds the data lines
its header counts. What cannot be counted is never called whole."""

from src.core.plt_ascii import check_ascii_plt
from test_scripts.plt_files import write_ascii_plt, write_plt


def test_a_whole_file(tmp_path):
    check = check_ascii_plt(write_ascii_plt(tmp_path / 'a.plt', nodes=6, elements=2))
    assert check.ok and check.zones == 1 and check.reason == ''


def test_two_zones_and_a_header_on_several_lines(tmp_path):
    p = tmp_path / 'a.plt'
    p.write_text('TITLE = "riser"\nVARIABLES = "X"\n"Y"\n'
                 'ZONE T="fluid"\n N=3, E=1,\n DATAPACKING=POINT, ZONETYPE=FETRIANGLE\n'
                 '0 0\n1 0\n0 1\n1 2 3\n'
                 'ZONE T="wall", NODES=2, ELEMENTS=1, ZONETYPE=FELINESEG\n'
                 '0.0E+00 1.5e-3\n-1 .5\n1 2\n')
    check = check_ascii_plt(p)
    assert check.ok and check.zones == 2


def test_cut_short_in_the_data(tmp_path):
    p = write_ascii_plt(tmp_path / 'a.plt', nodes=6, elements=2)
    lines = p.read_text().splitlines(keepends=True)
    p.write_text(''.join(lines[:-1]))
    check = check_ascii_plt(p)
    assert not check.ok and check.reason == 'cut short: zone 1 has 7 of 8 data lines'


def test_cut_short_in_the_last_line(tmp_path):
    p = write_ascii_plt(tmp_path / 'a.plt', nodes=6, elements=2)
    p.write_text(p.read_text()[:-3])
    assert check_ascii_plt(p).reason == 'cut short: the last line is not ended'


def test_cut_short_in_the_header_or_empty(tmp_path):
    p = tmp_path / 'a.plt'
    p.write_text('TITLE = "riser"\nVARIABLES = "X" "Y"\n')
    assert 'no ZONE' in check_ascii_plt(p).reason
    p.write_text('')
    assert check_ascii_plt(p).reason == 'empty'
    assert 'cannot read' in check_ascii_plt(tmp_path / 'none.plt').reason


def test_what_cannot_be_counted_is_not_whole(tmp_path):
    p = tmp_path / 'a.plt'
    p.write_text('VARIABLES = "X"\nZONE N=2, E=1, DATAPACKING=BLOCK, ZONETYPE=FELINESEG\n0 1\n1 2\n')
    assert 'BLOCK packing' in check_ascii_plt(p).reason
    p.write_text('VARIABLES = "X"\nZONE T="a"\n0\n1\n')
    assert 'no node count' in check_ascii_plt(p).reason
    p.write_text('VARIABLES = "X"\nZONE N=2, ET=BRICK\n0\n1\n')
    assert 'no element count' in check_ascii_plt(p).reason


def test_an_ordered_zone_counts_i_j_k(tmp_path):
    p = tmp_path / 'a.plt'
    p.write_text('VARIABLES = "X"\nZONE I=2, J=3\n' + '1\n' * 6)
    assert check_ascii_plt(p).ok
    p.write_text('VARIABLES = "X"\nZONE I=2, J=3\n' + '1\n' * 5)
    assert not check_ascii_plt(p).ok


def test_a_binary_plt_is_not_an_ascii_one(tmp_path):
    assert 'binary PLT' in check_ascii_plt(write_plt(tmp_path / 'b.plt')).reason


SIMPLT = ('TITLE = "Tecplot output" \n'
          'VARIABLES = "X","Y", "Z","U","V", "W","Pressure","dispX","dispY","dispZ","eddy",'
          '"xVor","yVor","zVor","QCriterion", "orderPar"\n'
          'ZONE T=FIELD, STRANDID=1, SOLUTIONTIME=287.500000, NODES = {n}, ELEMENTS={e}, '
          'DATAPACKING=POINT, ZONETYPE=FEBRICK \n')
NODE = ('2.164890e-17 3.535534e-01 3.535534e-01 0.000000e+00 0.000000e+00 0.000000e+00 '
        '-9.842554e+02 0.000000e+00 0.000000e+00 0.000000e+00  0.000000e+00 3.363114e+01 '
        '8.754331e-02 -8.280915e-01 -9.984108e-02 0.000000e+00\n')
ELEMENT = '1 2 3 4 5 6 7 8\n'


def simplt(path, n=5, e=3, nodes=None, elements=None):
    path.write_text(SIMPLT.format(n=n, e=e) + NODE * (n if nodes is None else nodes)
                    + ELEMENT * (e if elements is None else elements))
    return path


def test_the_header_simplt_writes(tmp_path):
    assert check_ascii_plt(simplt(tmp_path / 'riser.5750.plt')).ok
    check = check_ascii_plt(simplt(tmp_path / 'b.plt', elements=2))
    assert check.reason == 'cut short: zone 1 has 7 of 8 data lines'
    p = simplt(tmp_path / 'c.plt')
    p.write_text(p.read_text()[:-4])                            # stops inside the last line
    assert check_ascii_plt(p).reason == 'cut short: the last line is not ended'
    p = simplt(tmp_path / 'd.plt', nodes=0, elements=0)         # the header alone
    assert 'zone 1 has 0 of 8' in check_ascii_plt(p).reason


def test_a_nan_in_the_data_is_not_whole(tmp_path):
    p = simplt(tmp_path / 'a.plt')
    p.write_text(p.read_text().replace('3.363114e+01', 'nan', 1))
    assert check_ascii_plt(p).ok                                # a NaN among numbers is still a line
    p.write_text(SIMPLT.format(n=2, e=1) + NODE + 'nan nan\n' + ELEMENT)
    assert not check_ascii_plt(p).ok


def test_blocks_and_lines_count_the_same(tmp_path, monkeypatch):
    from src.core import plt_ascii
    p = simplt(tmp_path / 'a.plt', n=4000, e=3000)
    monkeypatch.setattr(plt_ascii, '_BLOCK', 1000)              # many blocks
    assert check_ascii_plt(p).ok
    assert not check_ascii_plt(simplt(tmp_path / 'b.plt', n=4000, e=3000, elements=2999)).ok
    monkeypatch.setattr(plt_ascii, '_fast_lines', lambda f: None)   # line by line
    assert check_ascii_plt(p).ok
