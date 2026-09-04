"""/api/log — the command window's read-only feed."""

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint('log', __name__, url_prefix='/api/log')


@bp.get('')
def get_log():
    since = request.args.get('since', 0, type=int)
    lb = current_app.logbuf
    return jsonify({'seq': lb.seq, 'lines': lb.since(since)})
