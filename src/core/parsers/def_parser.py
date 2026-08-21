"""
FlexFlow .def File Parser

This module provides utilities to parse FlexFlow .def configuration files.
"""

import os
import glob
import re


def find_def_file(case_directory, problem_name=None):
    """
    Find the .def file in a FlexFlow case directory.
    
    Parameters:
    -----------
    case_directory : str
        Path to FlexFlow case directory
    problem_name : str, optional
        Problem name from simflow.config. If provided, looks for <problem>.def
        
    Returns:
    --------
    str : Path to .def file, or None if not found
    """
    if problem_name:
        # Look for specific problem.def file
        def_file = os.path.join(case_directory, f'{problem_name}.def')
        if os.path.exists(def_file):
            return def_file
    
    # Fall back to finding any .def file
    def_files = glob.glob(os.path.join(case_directory, '*.def'))
    return def_files[0] if def_files else None


def parse_time_stepping_control(def_file_path):
    """
    Parse timeSteppingControl block from .def file.
    
    Parameters:
    -----------
    def_file_path : str
        Path to .def file
        
    Returns:
    --------
    dict : Dictionary with time stepping parameters
    """
    config = {}
    
    try:
        with open(def_file_path, 'r') as f:
            content = f.read()
            
        # Extract timeSteppingControl block
        match = re.search(r'timeSteppingControl\s*\{([^}]*)\}', content, re.DOTALL)
        if match:
            block = match.group(1)
            
            # Parse individual parameters
            params = {
                'initialTimeIncrement': r'initialTimeIncrement\s*=\s*([\d.eE+-]+)',
                'maxTimeSteps': r'maxTimeSteps\s*=\s*(\d+)',
                'order': r'order\s*=\s*(\w+)',
                'highFrequencyDampingFactor': r'highFrequencyDampingFactor\s*=\s*([\d.eE+-]+)'
            }
            
            for param_name, pattern in params.items():
                param_match = re.search(pattern, block)
                if param_match:
                    value = param_match.group(1)
                    # Convert to appropriate type
                    if param_name in ['initialTimeIncrement', 'highFrequencyDampingFactor']:
                        config[param_name] = float(value)
                    elif param_name == 'maxTimeSteps':
                        config[param_name] = int(value)
                    else:
                        config[param_name] = value
                        
    except Exception as e:
        print(f"Warning: Could not parse .def file: {e}")
    
    return config


def _strip_comments(content):
    """Drop '#' comments, so a commented-out setting is never read as live."""
    return re.sub(r'#[^\n]*', '', content)


def parse_node_coordinates(def_file_path):
    """File the mesh coordinates are read from, per nodeCoordinates{}, or None.

    Taken from the .def rather than assumed to be <problem>.crd, since the block
    names it explicitly.
    """
    try:
        with open(def_file_path, 'r') as f:
            content = _strip_comments(f.read())
    except OSError:
        return None
    block = re.search(r'nodeCoordinates\s*\{([^}]*)\}', content, re.DOTALL)
    if not block:
        return None
    named = re.search(r'coordinates\s*=\s*File\s*\(\s*"([^"]+)"\s*\)', block.group(1))
    return named.group(1) if named else None


def parse_output_time_history(def_file_path):
    """Every outputTimeHistory block in a .def, in file order.

    Returns a list of dicts with `name`, `type`, `nodes` / `coordinates` (whichever
    the block names) and `outputFrequency`. The solver writes one othd record per
    block; a `nodal` block's records are ordered by its node file, which is what
    makes that file the key to reading the othd back.
    """
    try:
        with open(def_file_path, 'r') as f:
            content = _strip_comments(f.read())
    except OSError:
        return []

    blocks = []
    for match in re.finditer(r'outputTimeHistory\s*\(\s*"([^"]+)"\s*\)\s*\{([^}]*)\}',
                             content, re.DOTALL):
        name, body = match.group(1), match.group(2)
        entry = {'name': name, 'type': None, 'nodes': None,
                 'coordinates': None, 'outputFrequency': None}
        kind = re.search(r'\btype\s*=\s*(\w+)', body)
        if kind:
            entry['type'] = kind.group(1)
        for key in ('nodes', 'coordinates'):
            named = re.search(rf'\b{key}\s*=\s*File\s*\(\s*"([^"]+)"\s*\)', body)
            if named:
                entry[key] = named.group(1)
        freq = re.search(r'\boutputFrequency\s*=\s*(\d+)', body)
        if freq:
            entry['outputFrequency'] = int(freq.group(1))
        blocks.append(entry)
    return blocks


def parse_def_file(case_directory, problem_name=None):
    """
    Parse FlexFlow .def file and extract all relevant configuration.
    
    Parameters:
    -----------
    case_directory : str
        Path to FlexFlow case directory
    problem_name : str, optional
        Problem name from simflow.config
        
    Returns:
    --------
    dict : Dictionary with parsed parameters
    """
    def_file = find_def_file(case_directory, problem_name)
    
    if not def_file:
        return {}
    
    config = parse_time_stepping_control(def_file)
    config['def_file'] = def_file
    
    return config


# ---------------------------------------------------------------------------
# Generic block reading
#
# The functions above each know one block by name. Anything that wants to read a
# block the .def happens to carry -- beamSolid, elementGroup, densityModel --
# needs the general form, and it cannot be had with `\{([^}]*)\}`: a beamSolid
# body contains `pnt1 = {0, 0, 0}`, so the first `}` that regex finds closes a
# vector, not the block, and the parse ends four lines in with rhoA and nothing
# else. Braces are matched by depth here instead.
# ---------------------------------------------------------------------------

_BLOCK_OPEN = re.compile(r'(?<![\w.])([A-Za-z]\w*)\s*(?:\(\s*"([^"]*)"\s*\)\s*)?\{')


def _strip_all_comments(content):
    """Drop both '#' and '//' comment styles; .def files use each in places."""
    return re.sub(r'(#|//)[^\n]*', '', content)


def _match_brace(content, open_index):
    """Index of the '}' closing the '{' at `open_index`, or None if unbalanced."""
    depth = 0
    for i in range(open_index, len(content)):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    return None


def _split_assignments(body):
    """`key = value` pairs from a block body, in file order.

    Values are kept as written -- `File( "x" )`, `{0, 1, 1}`, `MASSPERL`, `5e-4`
    -- because what a value means depends on the key, and turning them all into
    one type here would only have to be undone. `as_file`, `as_list` and
    `as_string` read the forms that need reading.

    A value whose braces do not close on its own line is continued onto the next,
    so a vector split across lines still arrives whole.
    """
    values = {}
    key = None
    pending = ''
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if pending:
            pending += ' ' + line
        elif '=' in line:
            raw_key, _, raw_val = line.partition('=')
            key = raw_key.strip()
            pending = raw_val.strip()
            if not key:
                key, pending = None, ''
                continue
        else:
            continue
        if pending.count('{') > pending.count('}'):
            continue          # a vector broken over lines; keep reading
        values[key] = pending
        key, pending = None, ''
    if key and pending:
        values[key] = pending
    return values


def parse_blocks(def_file_path, kind=None):
    """Every top-level block in a .def, in file order.

    Returns a list of dicts with `kind` (the keyword: beamSolid, elementGroup,
    ...), `name` (the quoted label, or None for an unlabelled block such as
    `nodeCoordinates {`) and `values` (its `key = value` pairs as written).
    Pass `kind` to keep only blocks of that keyword.

    Only top-level blocks are returned: a nested `{...}` is part of its parent's
    body, not a block of its own.
    """
    try:
        with open(def_file_path, 'r') as f:
            content = _strip_all_comments(f.read())
    except OSError:
        return []

    blocks = []
    position = 0
    while True:
        match = _BLOCK_OPEN.search(content, position)
        if not match:
            break
        open_index = match.end() - 1
        close_index = _match_brace(content, open_index)
        if close_index is None:
            break                      # unbalanced from here on; nothing to gain
        if kind is None or match.group(1) == kind:
            blocks.append({
                'kind': match.group(1),
                'name': match.group(2),
                'values': _split_assignments(content[open_index + 1:close_index]),
            })
        position = close_index + 1     # skip the body, so nested braces are not blocks
    return blocks


def as_file(raw):
    """The filename in a `File( "name" )` value, or None if it is not one."""
    if not raw:
        return None
    match = re.match(r'^File\s*\(\s*"([^"]*)"\s*\)$', raw.strip())
    return match.group(1) if match else None


def as_list(raw):
    """The items of a `{a, b, c}` value, or None if it is not one.

    Items are returned as written and unquoted, so `{ "cylinder_body" }` gives
    ['cylinder_body'] and `{0, 1, 1}` gives ['0', '1', '1'].
    """
    if not raw:
        return None
    text = raw.strip()
    if not (text.startswith('{') and text.endswith('}')):
        return None
    inner = text[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip('"').strip() for item in inner.split(',')]


def as_string(raw):
    """A value with any surrounding quotes removed."""
    return raw.strip().strip('"').strip() if raw else raw
