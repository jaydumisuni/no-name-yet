from __future__ import annotations

from main_review.languages import classify_role


def test_scripts_with_js_test_naming_are_tests_before_infrastructure() -> None:
    assert classify_role("scripts/smoke-test.js") == "test"
    assert classify_role("scripts/test-fireworks-live.js") == "test"
    assert classify_role("scripts/app.spec.ts") == "test"
    assert classify_role("scripts/app.test.jsx") == "test"


def test_non_test_scripts_remain_infrastructure() -> None:
    assert classify_role("scripts/deploy.js") == "infrastructure"
