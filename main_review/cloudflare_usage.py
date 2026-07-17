"""Persistent, credential-safe usage governance for Cloudflare Workers AI.

The governor protects Cpl from spending an account's daily allocation blindly. It
uses conservative reservations because Cloudflare response usage telemetry is not
available on every route. A reservation is made before each inference request,
and an observed daily-allocation error opens a circuit until the next UTC day.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .cloudflare_models import MODEL_PROFILES

USAGE_SCHEMA = "sergeant.cloudflare-usage.v1"
_DEFAULT_DAILY_LIMIT = 10_000
_DEFAULT_SAFETY_RESERVE = 1_000
_DEFAULT_UNKNOWN_MODEL_RESERVATION = 2_500
_DEFAULT_CHARS_PER_TOKEN = 3
_DEFAULT_LOCK_TIMEOUT_SECONDS = 10
_DEFAULT_STALE_LOCK_SECONDS = 120
_STATE_LOCK = threading.Lock()


class CloudflareUsageError(RuntimeError):
    """Base class for local Workers AI usage-governor failures."""


class CloudflareBudgetExceeded(CloudflareUsageError):
    """Raised before inference when a request would exceed the local budget."""


class CloudflareQuotaBlocked(CloudflareUsageError):
    """Raised when a previous provider allocation error opened the daily circuit."""


class CloudflareUsageLockTimeout(CloudflareUsageError):
    """Raised when another process holds the usage-state lock too long."""


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(maximum, max(minimum, value))


def _enabled() -> bool:
    value = os.getenv("SERGEANT_CLOUDFLARE_USAGE_GOVERNOR", "true").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def _state_path() -> Path:
    explicit = os.getenv("SERGEANT_CLOUDFLARE_USAGE_STATE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / ".sergeant" / "cloudflare-usage.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_day(now: datetime) -> str:
    return now.astimezone(timezone.utc).date().isoformat()


def _next_reset(now: datetime) -> datetime:
    current = now.astimezone(timezone.utc)
    return datetime.combine(
        current.date() + timedelta(days=1),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )


def _lock_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.lock")


@contextmanager
def _interprocess_lock(path: Path) -> Iterator[None]:
    """Serialize state changes with a portable atomic lock file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(path)
    timeout = _bounded_int(
        "SERGEANT_CLOUDFLARE_LOCK_TIMEOUT_SECONDS",
        _DEFAULT_LOCK_TIMEOUT_SECONDS,
        1,
        300,
    )
    stale_after = _bounded_int(
        "SERGEANT_CLOUDFLARE_STALE_LOCK_SECONDS",
        _DEFAULT_STALE_LOCK_SECONDS,
        timeout + 1,
        3600,
    )
    deadline = time.monotonic() + timeout
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(
                descriptor,
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "created_at": _utc_now().isoformat(),
                    },
                    sort_keys=True,
                ).encode("utf-8"),
            )
            os.fsync(descriptor)
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > stale_after:
                    lock_path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise CloudflareUsageLockTimeout(
                    f"Cloudflare usage state is locked by another process: {lock_path}"
                ) from None
            time.sleep(0.05)
    try:
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _state_transaction(path: Path) -> Iterator[None]:
    with _STATE_LOCK:
        with _interprocess_lock(path):
            yield


@dataclass
class CloudflareUsageState:
    schema_version: str = USAGE_SCHEMA
    day: str = ""
    reserved_neurons: int = 0
    request_count: int = 0
    quota_blocked: bool = False
    quota_blocked_at: str = ""
    reset_at: str = ""
    reservations: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def fresh(cls, now: datetime) -> "CloudflareUsageState":
        return cls(
            day=_utc_day(now),
            reset_at=_next_reset(now).isoformat(),
        )

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reservations"] = list(self.reservations[-20:])
        return payload


def _load_state(path: Path, now: datetime) -> CloudflareUsageState:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CloudflareUsageState.fresh(now)
    if not isinstance(raw, dict) or raw.get("schema_version") != USAGE_SCHEMA:
        return CloudflareUsageState.fresh(now)
    try:
        state = CloudflareUsageState(
            schema_version=USAGE_SCHEMA,
            day=str(raw.get("day") or ""),
            reserved_neurons=max(0, int(raw.get("reserved_neurons", 0))),
            request_count=max(0, int(raw.get("request_count", 0))),
            quota_blocked=raw.get("quota_blocked") is True,
            quota_blocked_at=str(raw.get("quota_blocked_at") or ""),
            reset_at=str(raw.get("reset_at") or ""),
            reservations=[item for item in raw.get("reservations", []) if isinstance(item, dict)][-100:],
        )
    except (TypeError, ValueError):
        return CloudflareUsageState.fresh(now)
    if state.day != _utc_day(now):
        return CloudflareUsageState.fresh(now)
    return state


def _save_state(path: Path, state: CloudflareUsageState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(json.dumps(state.public_dict(), indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def estimate_input_tokens(character_count: int) -> int:
    """Return a conservative token estimate without requiring a tokenizer."""

    ratio = _bounded_int(
        "SERGEANT_CLOUDFLARE_CHARS_PER_TOKEN",
        _DEFAULT_CHARS_PER_TOKEN,
        1,
        8,
    )
    return max(1, math.ceil(max(0, character_count) / ratio))


def estimate_neurons(model: str, *, input_chars: int, max_output_tokens: int) -> int:
    """Estimate a safe reservation from the public model neuron rates."""

    profile = MODEL_PROFILES.get(model)
    if (
        profile is None
        or profile.input_neurons_per_million is None
        or profile.output_neurons_per_million is None
    ):
        return _bounded_int(
            "SERGEANT_CLOUDFLARE_UNKNOWN_MODEL_RESERVATION_NEURONS",
            _DEFAULT_UNKNOWN_MODEL_RESERVATION,
            1,
            100_000,
        )
    input_tokens = estimate_input_tokens(input_chars)
    input_neurons = input_tokens * profile.input_neurons_per_million / 1_000_000
    output_neurons = max(1, max_output_tokens) * profile.output_neurons_per_million / 1_000_000
    return max(1, math.ceil(input_neurons + output_neurons))


class CloudflareUsageGovernor:
    """Reserve daily capacity and persist a quota circuit across Cpl calls."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _state_path()

    @property
    def daily_limit(self) -> int:
        return _bounded_int(
            "SERGEANT_CLOUDFLARE_DAILY_BUDGET_NEURONS",
            _DEFAULT_DAILY_LIMIT,
            0,
            10_000_000,
        )

    @property
    def safety_reserve(self) -> int:
        return _bounded_int(
            "SERGEANT_CLOUDFLARE_SAFETY_RESERVE_NEURONS",
            _DEFAULT_SAFETY_RESERVE,
            0,
            10_000_000,
        )

    @property
    def usable_limit(self) -> int:
        if self.daily_limit == 0:
            return 0
        return max(0, self.daily_limit - self.safety_reserve)

    def status(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or _utc_now()
        with _state_transaction(self.path):
            state = _load_state(self.path, current)
            payload = state.public_dict()
        payload.update(
            {
                "enabled": _enabled(),
                "daily_limit_neurons": self.daily_limit,
                "safety_reserve_neurons": self.safety_reserve,
                "usable_limit_neurons": self.usable_limit,
                "remaining_reserved_capacity_neurons": (
                    None
                    if self.daily_limit == 0
                    else max(0, self.usable_limit - state.reserved_neurons)
                ),
            }
        )
        return payload

    def reserve(
        self,
        *,
        model: str,
        input_chars: int,
        max_output_tokens: int,
        stage: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = now or _utc_now()
        if not _enabled():
            return {
                "enabled": False,
                "model": model,
                "stage": stage,
                "estimated_neurons": 0,
            }
        estimate = estimate_neurons(
            model,
            input_chars=input_chars,
            max_output_tokens=max_output_tokens,
        )
        with _state_transaction(self.path):
            state = _load_state(self.path, current)
            if state.quota_blocked:
                raise CloudflareQuotaBlocked(
                    "Cloudflare quota circuit is open until "
                    f"{state.reset_at or _next_reset(current).isoformat()}."
                )
            if self.daily_limit and state.reserved_neurons + estimate > self.usable_limit:
                remaining = max(0, self.usable_limit - state.reserved_neurons)
                raise CloudflareBudgetExceeded(
                    "Cloudflare request blocked before inference: estimated "
                    f"{estimate} neurons exceeds the remaining local daily budget of {remaining}."
                )
            reservation = {
                "at": current.isoformat(),
                "model": model,
                "stage": stage,
                "estimated_neurons": estimate,
                "max_output_tokens": max_output_tokens,
            }
            state.reserved_neurons += estimate
            state.request_count += 1
            state.reservations.append(reservation)
            state.reservations = state.reservations[-100:]
            _save_state(self.path, state)
        return {
            **reservation,
            "enabled": True,
            "reserved_neurons_total": state.reserved_neurons,
            "request_count": state.request_count,
            "reset_at": state.reset_at,
        }

    def mark_quota_blocked(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or _utc_now()
        with _state_transaction(self.path):
            state = _load_state(self.path, current)
            state.quota_blocked = True
            state.quota_blocked_at = current.isoformat()
            state.reset_at = _next_reset(current).isoformat()
            _save_state(self.path, state)
            return state.public_dict()


def reserve_cloudflare_request(
    *,
    model: str,
    input_chars: int,
    max_output_tokens: int,
    stage: str,
) -> dict[str, Any]:
    return CloudflareUsageGovernor().reserve(
        model=model,
        input_chars=input_chars,
        max_output_tokens=max_output_tokens,
        stage=stage,
    )


def mark_cloudflare_quota_blocked() -> dict[str, Any]:
    return CloudflareUsageGovernor().mark_quota_blocked()


def cloudflare_usage_status() -> dict[str, Any]:
    return CloudflareUsageGovernor().status()
