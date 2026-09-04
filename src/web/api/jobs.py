"""/api/jobs/<id> — poll a background job started by another endpoint."""

from flask import Blueprint, jsonify

from ..services.jobs import jobs

bp = Blueprint('jobs', __name__, url_prefix='/api/jobs')


@bp.get('/<job_id>')
def get_job(job_id):
    job = jobs.get(job_id)
    if job is None:
        return jsonify({'error': f'no such job: {job_id}'}), 404
    return jsonify({'id': job.id, 'status': job.status, 'result': job.result, 'error': job.error})
