"""App factory, route registration, and the loopback safety check.

No authentication (§10 of docs/WEBAPP_PLAN.md) — binding to 127.0.0.1 and
reaching it over `ssh -L` is the whole defence, so refusing a non-loopback
host is the one check this module exists to make.
"""

import os
from pathlib import Path
from typing import Optional

from flask import Flask, render_template

from .api.cases import bp as cases_bp
from .api.export import bp as export_bp
from .api.history import bp as history_bp
from .api.jobs import bp as jobs_bp
from .api.maps import bp as maps_bp
from .api.settings import bp as settings_bp
from .api.spatial import bp as spatial_bp

_LOOPBACK_HOSTS = {'127.0.0.1', 'localhost', '::1'}


def create_app(root: Path) -> Flask:
    app = Flask(__name__)
    app.config['WORKSPACE_ROOT'] = root

    app.register_blueprint(cases_bp)
    app.register_blueprint(maps_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(spatial_bp)
    app.register_blueprint(settings_bp)

    @app.get('/')
    def index():
        return render_template('index.html', root=str(root))

    return app


def run(root: Optional[str] = None, host: str = '127.0.0.1', port: int = 8080) -> None:
    if host not in _LOOPBACK_HOSTS and not os.environ.get('FLEXFLOW_WEB_ALLOW_PUBLIC'):
        raise SystemExit(
            f"Refusing to bind {host}: not a loopback address.\n"
            f"This app has no authentication — reach it over `ssh -L {port}:localhost:{port} <host>` "
            f"instead, or set FLEXFLOW_WEB_ALLOW_PUBLIC=1 if you understand the risk."
        )

    workspace_root = Path(root or os.getcwd()).expanduser().resolve()
    if not workspace_root.is_dir():
        raise SystemExit(f"Not a directory: {workspace_root}")

    app = create_app(workspace_root)
    print(f"FlexFlow web UI — workspace root: {workspace_root}")
    print(f"Serving on http://{host}:{port}  (Ctrl+C to stop)")
    app.run(host=host, port=port)
