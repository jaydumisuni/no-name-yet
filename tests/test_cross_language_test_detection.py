from __future__ import annotations

from main_review.languages import classify_role


def test_scripts_with_js_test_naming_are_tests_before_infrastructure() -> None:
    assert classify_role("scripts/smoke-test.js") == "test"
    assert classify_role("scripts/test-fireworks-live.js") == "test"
    assert classify_role("scripts/app.spec.ts") == "test"
    assert classify_role("scripts/app.test.jsx") == "test"


def test_non_test_scripts_remain_infrastructure() -> None:
    assert classify_role("scripts/deploy.js") == "infrastructure"


def test_language_native_test_names_are_detected() -> None:
    assert classify_role("src/UserServiceTest.java") == "test"
    assert classify_role("src/JobCounterTests.cs") == "test"
    assert classify_role("lib/report_spec.rb") == "test"
    assert classify_role("Sources/ClientTests.swift") == "test"


def test_words_ending_in_test_letters_are_not_misclassified() -> None:
    assert classify_role("src/Contest.java") == "source"
    assert classify_role("src/Latest.cs") == "source"


def test_dotnet_project_files_are_manifests() -> None:
    assert classify_role("Service.csproj") == "manifest"
    assert classify_role("Service.sln") == "manifest"
