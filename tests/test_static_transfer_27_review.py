from __future__ import annotations

from pathlib import Path

from main_review.static_status_review import run_static_status_review
from main_review.static_transfer_27_review import run_static_transfer_27_review

CPP_ROOT = "reconstructed-binary-operation-forgets-original-operand-order"
JAVA_ROOT = "async-lock-ownership-not-reconciled-across-completion-paths"
PYTHON_ROOT = "fixed-duration-calendar-day-bypasses-tick-origin-and-bin-contract"


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_cpp_reconstruction_preserves_original_operand_order(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "transform.cpp",
        r'''
BinaryOperator *B0 = cast<BinaryOperator>(PHIUser);
unsigned opId = (B0->getOperand(0) == PN) ? 1 : 0;
Value *Op = ExtractElementInst::Create(B0->getOperand(opId), Elt);
Value *newPHIUser = BinaryOperator::CreateWithCopiedFlags(
    B0->getOpcode(), scalarPHI, Op, B0);
''',
    )

    result = run_static_transfer_27_review(tmp_path, ["transform.cpp"])

    assert CPP_ROOT in _roots(result)


def test_cpp_conditional_operand_reconstruction_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "transform.cpp",
        r'''
BinaryOperator *B0 = cast<BinaryOperator>(PHIUser);
unsigned opId = (B0->getOperand(0) == PN) ? 1 : 0;
Value *Op = ExtractElementInst::Create(B0->getOperand(opId), Elt);
Value *FirstOp = (B0->getOperand(0) == PN) ? scalarPHI : Op;
Value *SecondOp = (B0->getOperand(0) == PN) ? Op : scalarPHI;
Value *newPHIUser = BinaryOperator::CreateWithCopiedFlags(
    B0->getOpcode(), FirstOp, SecondOp, B0);
''',
    )

    result = run_static_transfer_27_review(tmp_path, ["transform.cpp"])

    assert CPP_ROOT not in _roots(result)


def test_cpp_commutative_only_reconstruction_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "transform.cpp",
        r'''
if (!isCommutative(B0))
  return nullptr;
unsigned opId = (B0->getOperand(0) == PN) ? 1 : 0;
Value *Op = ExtractElementInst::Create(B0->getOperand(opId), Elt);
Value *newPHIUser = BinaryOperator::CreateWithCopiedFlags(
    B0->getOpcode(), scalarPHI, Op, B0);
''',
    )

    result = run_static_transfer_27_review(tmp_path, ["transform.cpp"])

    assert CPP_ROOT not in _roots(result)


def test_java_released_subset_must_leave_aggregate_ownership(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "DelayedFetch.java",
        r'''
private LinkedHashMap<Partition, Long> partitionsAcquired = new LinkedHashMap<>();

private boolean maybeProcessRemoteFetch(Map<Partition, Result> remoteInfo) {
    Set<Partition> nonRemoteFetchPartitions = new LinkedHashSet<>();
    releasePartitionLocksAndAddToActionQueue(nonRemoteFetchPartitions, nonRemoteFetchPartitions);
    processRemoteFetchOrException(remoteInfo);
    return maybeCompletePendingRemoteFetch();
}

private void completeRemoteFetch() {
    releasePartitionLocksAndAddToActionQueue(partitionsAcquired.keySet(), Set.of());
}
''',
    )

    result = run_static_transfer_27_review(tmp_path, ["DelayedFetch.java"])

    assert JAVA_ROOT in _roots(result)


def test_java_released_subset_removed_from_aggregate_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "DelayedFetch.java",
        r'''
private LinkedHashMap<Partition, Long> partitionsAcquired = new LinkedHashMap<>();

private boolean maybeProcessRemoteFetch(Map<Partition, Result> remoteInfo) {
    Set<Partition> nonRemoteFetchPartitions = new LinkedHashSet<>();
    releasePartitionLocksAndAddToActionQueue(nonRemoteFetchPartitions, nonRemoteFetchPartitions);
    nonRemoteFetchPartitions.forEach(partitionsAcquired::remove);
    processRemoteFetchOrException(remoteInfo);
    return maybeCompletePendingRemoteFetch();
}

private void completeRemoteFetch() {
    releasePartitionLocksAndAddToActionQueue(partitionsAcquired.keySet(), Set.of());
}
''',
    )

    result = run_static_transfer_27_review(tmp_path, ["DelayedFetch.java"])

    assert JAVA_ROOT not in _roots(result)


def test_python_timezone_naive_day_must_share_fixed_tick_contract(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "resample.py",
        r'''
from pandas.tseries.offsets import Day, Tick

if not isinstance(freq, Tick):
    if offset is not None:
        warnings.warn("offset does not take effect")
    if origin != "start_day":
        warnings.warn("origin does not take effect")

def _get_timestamp_range_edges(first, last, freq, closed, origin, offset):
    if isinstance(freq, Tick):
        first, last = _adjust_dates_anchored(first, last, freq, closed, origin, offset)
    else:
        first = first.normalize()
        last = last.normalize()
    return first, last
''',
    )

    result = run_static_transfer_27_review(tmp_path, ["resample.py"])

    assert PYTHON_ROOT in _roots(result)


def test_python_day_equivalence_with_timezone_guard_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "resample.py",
        r'''
from pandas.tseries.offsets import Day, Hour, Tick

if not isinstance(freq, (Tick, Day)):
    if offset is not None:
        warnings.warn("offset does not take effect")

def _get_timestamp_range_edges(first, last, freq, closed, origin, offset):
    if isinstance(freq, Tick) or (isinstance(freq, Day) and first.tz is None):
        if isinstance(freq, Day):
            freq = Hour(24 * freq.n)
        first, last = _adjust_dates_anchored(first, last, freq, closed, origin, offset)
    else:
        first = first.normalize()
        last = last.normalize()
    return first, last
''',
    )

    result = run_static_transfer_27_review(tmp_path, ["resample.py"])

    assert PYTHON_ROOT not in _roots(result)


def test_normal_status_path_admits_transfer_27_roots(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "transform.cpp",
        r'''
BinaryOperator *B0 = cast<BinaryOperator>(PHIUser);
unsigned opId = (B0->getOperand(0) == PN) ? 1 : 0;
Value *Op = ExtractElementInst::Create(B0->getOperand(opId), Elt);
Value *newPHIUser = BinaryOperator::CreateWithCopiedFlags(B0->getOpcode(), scalarPHI, Op, B0);
''',
    )
    _write(
        tmp_path,
        "DelayedFetch.java",
        r'''
private Map<Partition, Long> partitionsAcquired = new LinkedHashMap<>();
void remote(Set<Partition> nonRemoteFetchPartitions) {
  releasePartitionLocks(nonRemoteFetchPartitions);
  processRemoteFetch();
}
void finish() { releasePartitionLocks(partitionsAcquired.keySet()); }
''',
    )
    _write(
        tmp_path,
        "resample.py",
        r'''
from pandas.tseries.offsets import Day, Tick
if not isinstance(freq, Tick):
    warnings.warn("origin ignored")
def edges(first, last, freq):
    if isinstance(freq, Tick):
        return anchored(first, last, freq)
    else:
        first = first.normalize()
        last = last.normalize()
        return first, last
''',
    )

    result = run_static_status_review(
        tmp_path,
        ["transform.cpp", "DelayedFetch.java", "resample.py"],
    )

    roots = _roots(result)
    assert CPP_ROOT in roots
    assert JAVA_ROOT in roots
    assert PYTHON_ROOT in roots
