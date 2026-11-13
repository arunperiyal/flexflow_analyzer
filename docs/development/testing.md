# Testing

Run the complete test suite from the repository root:

```bash
python3 -m pytest test_scripts -q
```

The tests use temporary directories for most cases. A few tests exercise real
field and web behaviour against the checked-in fixture
`examples/BR0SG0U1P0`. Keep that example case available when running the full
suite; tests that need its large PLT files skip themselves if the files are
absent.

For a focused run, pass a test file or expression:

```bash
python3 -m pytest test_scripts/test_auto_show.py -q
python3 -m pytest test_scripts -q -k "field_extract"
```

The `tools/make_dummy.py` fixture builder is used by the `auto` tests and
creates small cases, a fake SLURM installation and a local fake remote.
