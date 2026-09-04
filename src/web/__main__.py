"""python -m src.web --root . --port 8080"""

import argparse
import sys

from .server import run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='python -m src.web',
                                      description='FlexFlow web UI')
    parser.add_argument('--root', default=None,
                         help='Workspace directory holding .cases (default: cwd)')
    parser.add_argument('--host', default='127.0.0.1',
                         help='Bind address (default: 127.0.0.1 — loopback only)')
    parser.add_argument('--port', type=int, default=8080,
                         help='Port to serve on (default: 8080)')
    args = parser.parse_args(argv)

    run(root=args.root, host=args.host, port=args.port)
    return 0


if __name__ == '__main__':
    sys.exit(main())
