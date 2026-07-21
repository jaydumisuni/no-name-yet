from __future__ import annotations

from scripts.select_opaque_transfer_candidates_v8 import _qualifies_v8


def _rows() -> list[dict]:
    return [
        {
            "filename": "src/runtime.py",
            "status": "modified",
            "patch": "@@\n-old_value = legacy()\n-old_result = consume(old_value)\n-old_state = finalize(old_result)\n+new_value = replacement()\n+new_result = consume(new_value)\n+new_state = finalize(new_result)\n",
        },
        {
            "filename": "tests/test_runtime.py",
            "status": "modified",
            "patch": "@@\n-assert old_result\n+assert new_result\n",
        },
    ]


def test_capability_addition_without_prior_defect_is_rejected() -> None:
    pr = {
        "title": "Add Closeable and AutoCloseable support",
        "body": "Fixes #1988. This enables support for two new reify interfaces.",
    }

    assert not _qualifies_v8(pr, _rows(), ["src/runtime.py"])


def test_feature_request_without_behavior_failure_is_rejected() -> None:
    pr = {
        "title": "Feature: allow users to provide custom adapters",
        "body": "Feature request that introduces support for a new adapter type.",
    }

    assert not _qualifies_v8(pr, _rows(), ["src/runtime.py"])


def test_capability_wording_with_concrete_existing_crash_can_qualify() -> None:
    pr = {
        "title": "Add guard for Closeable support crash",
        "body": "Existing reified resources crash when close is called twice; this fixes the broken lifecycle.",
    }

    assert _qualifies_v8(pr, _rows(), ["src/runtime.py"])


def test_plain_behavioral_regression_can_qualify() -> None:
    pr = {
        "title": "Fix stale result after retry",
        "body": "A regression returns the wrong cached value after the request is retried.",
    }

    assert _qualifies_v8(pr, _rows(), ["src/runtime.py"])


def test_canonical_perl_t_file_satisfies_changed_test_gate_without_mutating_rows() -> None:
    rows = [
        {
            "filename": "lib/Example.pm",
            "status": "modified",
            "patch": "@@\n-my $value = legacy();\n-my $result = consume($value);\n-my $state = finalize($result);\n+my $value = replacement();\n+my $result = consume($value);\n+my $state = finalize($result);\n",
        },
        {
            "filename": "t/example.t",
            "status": "modified",
            "patch": "@@\n-is $old, 1;\n+is $new, 1;\n",
        },
    ]
    pr = {
        "title": "Fix stale cache after retry",
        "body": "A regression returns the wrong cached value after a failed request is retried.",
    }

    assert _qualifies_v8(pr, rows, ["lib/Example.pm"])
    assert rows[1]["filename"] == "t/example.t"
