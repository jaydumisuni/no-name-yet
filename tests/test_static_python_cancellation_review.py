from __future__ import annotations

from pathlib import Path

from main_review.static_python_cancellation_review import run_static_python_cancellation_review


ROOT = "grouped-cancellation-not-caught-by-ordinary-except"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_taskgroup_shutdown_with_ordinary_cancelled_error_except_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        """
import asyncio

async def execute_batch():
    async with asyncio.TaskGroup() as group:
        group.create_task(run_one())

class Worker:
    async def stop(self):
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = {}
        """,
        encoding="utf-8",
    )
    result = run_static_python_cancellation_review(tmp_path, ["worker.py"])
    assert ROOT in _roots(result)


def test_cross_file_taskgroup_evidence_is_used_for_changed_shutdown_loop(tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(
        """
import asyncio

class Worker:
    async def stop(self):
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = {}
        """,
        encoding="utf-8",
    )
    jobs = tmp_path / "jobs.py"
    jobs.write_text(
        """
import asyncio

async def execute_batch():
    async with asyncio.TaskGroup() as group:
        group.create_task(run_one())
        """,
        encoding="utf-8",
    )

    result = run_static_python_cancellation_review(tmp_path, ["worker.py"])

    assert ROOT in _roots(result)
    assert result["taskgroup_evidence_path"] == "jobs.py"


def test_heterogeneous_shutdown_batch_with_ordinary_except_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        """
import asyncio

class Worker:
    async def stop(self):
        tasks = [task for board_tasks in self._tasks.values() for task in board_tasks]
        for attr in ("_poll_task", "_audit_task"):
            task = getattr(self, attr)
            if task is not None:
                tasks.append(task)
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        """,
        encoding="utf-8",
    )

    result = run_static_python_cancellation_review(tmp_path, ["worker.py"])

    assert ROOT in _roots(result)
    assert result["taskgroup_evidence_path"] is None


def test_taskgroup_shutdown_with_except_star_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        """
import asyncio

async def execute_batch():
    async with asyncio.TaskGroup() as group:
        group.create_task(run_one())

class Worker:
    async def stop(self):
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except* asyncio.CancelledError:
                pass
        """,
        encoding="utf-8",
    )
    result = run_static_python_cancellation_review(tmp_path, ["worker.py"])
    assert ROOT not in _roots(result)


def test_plain_task_cancellation_without_taskgroup_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        """
import asyncio

async def stop(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
        """,
        encoding="utf-8",
    )
    result = run_static_python_cancellation_review(tmp_path, ["worker.py"])
    assert ROOT not in _roots(result)


def test_simple_homogeneous_task_list_without_taskgroup_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        """
import asyncio

async def stop(tasks):
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
        """,
        encoding="utf-8",
    )
    result = run_static_python_cancellation_review(tmp_path, ["worker.py"])
    assert ROOT not in _roots(result)


def test_explicit_exception_group_handling_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "worker.py"
    source.write_text(
        """
import asyncio

async def execute_batch():
    async with asyncio.TaskGroup() as group:
        group.create_task(run_one())

async def stop(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except BaseExceptionGroup as group:
        remaining = group.subgroup(lambda error: not isinstance(error, asyncio.CancelledError))
        if remaining is not None:
            raise remaining
        """,
        encoding="utf-8",
    )
    result = run_static_python_cancellation_review(tmp_path, ["worker.py"])
    assert ROOT not in _roots(result)
