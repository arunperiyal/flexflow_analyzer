"""Help text and examples show the command as it is typed in the shell: no
`flexflow ` in front (`case show`, not `flexflow case show`)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ('case|data|plot|compare|run|auto|field|remote|template|def|check|docs|use|config|'
            'version|new')
PREFIXED = re.compile(r'\bflexflow (?:%s)\b' % COMMANDS)


def test_no_help_text_starts_a_command_with_flexflow():
    offenders = []
    for path in (ROOT / 'src' / 'commands').rglob('*.py'):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if PREFIXED.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not offenders, "\n".join(offenders[:20])


def test_the_create_examples_use_the_command_that_exists():
    text = (ROOT / 'src/commands/case/create_impl/help_messages.py').read_text()
    assert 'flexflow new' not in text
