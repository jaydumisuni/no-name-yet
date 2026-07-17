from __future__ import annotations

from pathlib import Path

from main_review.static_job_recovery_review import run_static_job_recovery_review


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_stale_started_job_reclaim_without_attempt_accounting_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        '''
def acquire_job_lock(self, cr):
    query = """
        SELECT j.id FROM queue_job j
        WHERE j.state = 'pending'
           OR (j.state = 'started' AND j.heartbeat < NOW() - INTERVAL '60 seconds')
        FOR UPDATE SKIP LOCKED
    """
    cr.execute(query)
    res = cr.fetchone()
    if res:
        job_id = res[0]
        cr.execute(
            "UPDATE queue_job SET state = 'started', heartbeat = NOW(), worker_id = %s, started_at = NOW() WHERE id = %s",
            (self.worker_uuid, job_id),
        )
        return job_id
    return None
''',
        encoding="utf-8",
    )
    result = run_static_job_recovery_review(tmp_path, [source.name])
    assert "stale-reclaim-budget-not-advanced" in _roots(result)


def test_reclaim_that_advances_attempts_and_enforces_limit_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        '''
def acquire_job_lock(self, cr):
    query = """
        SELECT j.id, j.state, j.attempts, j.max_retries FROM queue_job j
        WHERE j.state = 'pending'
           OR (j.state = 'started' AND j.heartbeat < NOW() - INTERVAL '60 seconds')
        FOR UPDATE SKIP LOCKED
    """
    cr.execute(query)
    res = cr.fetchone()
    if not res:
        return None
    job_id, selected_state, attempts, max_retries = res
    if selected_state == 'started':
        attempts = attempts + 1
        if max_retries and attempts > max_retries:
            cr.execute("UPDATE queue_job SET state = 'failed', attempts = %s WHERE id = %s", (attempts, job_id))
            return None
    cr.execute(
        "UPDATE queue_job SET state = 'started', attempts = %s, heartbeat = NOW(), worker_id = %s, started_at = NOW() WHERE id = %s",
        (attempts, self.worker_uuid, job_id),
    )
    return job_id
''',
        encoding="utf-8",
    )
    result = run_static_job_recovery_review(tmp_path, [source.name])
    assert "stale-reclaim-budget-not-advanced" not in _roots(result)


def test_pending_only_queue_acquisition_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        '''
def acquire_job_lock(self, cr):
    cr.execute("SELECT id FROM queue_job WHERE state = 'pending' FOR UPDATE SKIP LOCKED")
    return cr.fetchone()
''',
        encoding="utf-8",
    )
    assert "stale-reclaim-budget-not-advanced" not in _roots(
        run_static_job_recovery_review(tmp_path, [source.name])
    )
