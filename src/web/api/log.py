"""/api/log -- the command window's lines, read only."""

from flask import Blueprint, jsonify, request

from ..services.logbuf import log

bp = Blueprint('log', __name__, url_prefix='/api/log')


@bp.get('')
def lines():
    last = request.args.get('since', 0, type=int)
    rows, newest = log.since(last)
    return jsonify({'lines': rows, 'next': newest})
