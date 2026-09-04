"""services/jobs.py — background jobs with a status endpoint.

Writing maps reads the coordinates file once -- 137 MB for the riser example,
and the plan's own reason the map exists at all. That is too slow to hold a
request thread open for, so it runs on a thread and the browser polls
/api/jobs/<id> instead (§Phase 3 of the plan: "Background load with a
job-status endpoint").
"""

import threading
import uuid
from typing import Callable, Optional


class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.status = 'running'   # running | done | error
        self.result = None
        self.error: Optional[str] = None


class JobRegistry:
    def __init__(self):
        self._jobs: dict = {}
        self._lock = threading.Lock()

    def start(self, fn: Callable) -> str:
        job = Job(uuid.uuid4().hex)
        with self._lock:
            self._jobs[job.id] = job

        def run():
            try:
                job.result = fn()
                job.status = 'done'
            except Exception as exc:
                job.error = str(exc)
                job.status = 'error'

        threading.Thread(target=run, daemon=True).start()
        return job.id

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)


jobs = JobRegistry()
