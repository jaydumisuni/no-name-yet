from __future__ import annotations

from pathlib import Path

from main_review.evidence import collect_evidence


def _messages(payload: dict[str, object]) -> list[str]:
    return [finding["message"] for finding in payload["findings"]]  # type: ignore[index]


def test_evidence_detects_missing_tests_and_docs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    payload = collect_evidence(tmp_path)
    messages = _messages(payload)

    assert payload["finding_count"] == 2
    assert "Source files exist but no tests were detected." in messages
    assert "No documentation files were detected." in messages


def test_evidence_detects_secret_and_high_risk_path(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    secret_assignment = "API" + "_KEY='1234567890abcdef'\n"
    (tmp_path / "src" / "config.py").write_text(secret_assignment, encoding="utf-8")

    payload = collect_evidence(tmp_path)
    findings = payload["findings"]  # type: ignore[assignment]

    assert any(finding["severity"] == "blocker" and finding["category"] == "security" for finding in findings)  # type: ignore[index]
    assert any(finding["provider"] == "risk-path-checker" for finding in findings)  # type: ignore[index]


def test_clean_small_repository_has_no_major_findings(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    payload = collect_evidence(tmp_path)
    findings = payload["findings"]  # type: ignore[assignment]

    assert not [finding for finding in findings if finding["severity"] in {"blocker", "major"}]  # type: ignore[index]


def test_battle_aware_provider_detects_requests_file_wrapper_patterns(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "models.py").write_text(
        'elif isinstance(fp, _SupportsRead) or hasattr(fp, "read"):\n    fdata = fp.read()\n',
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_requests.py").write_text(
        'def test_post_named_tempfile():\n'
        '    with tempfile.NamedTemporaryFile(mode="w+") as f:\n'
        '        r = requests.post("/post", files={"file": f})\n',
        encoding="utf-8",
    )

    messages = _messages(collect_evidence(tmp_path))

    assert "Implementation is small and targeted." in messages
    assert "Regression test covers the file wrapper behavior." in messages


def test_battle_aware_provider_detects_flask_context_patterns(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_context.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (tmp_path / "src" / "ctx.py").write_text(
        "RequestContext is deprecated and request_ctx has merged with app_ctx. "
        "copy current context behavior now uses _cv_app proxy visibility.\n",
        encoding="utf-8",
    )

    messages = _messages(collect_evidence(tmp_path))

    assert "Architecture lifecycle risk should be reviewed." in messages
    assert "Migration and deprecation documentation is present but should be checked for accuracy." in messages
    assert "Proxy availability and context visibility should be verified." in messages
    assert "Copied context behavior should be checked for regression risk." in messages


def test_battle_aware_provider_detects_django_query_string_patterns(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "django" / "views" / "generic").mkdir(parents=True)
    (tmp_path / "tests" / "generic_views").mkdir(parents=True)
    (tmp_path / "django" / "views" / "generic" / "base.py").write_text(
        'url = "%s%s%s" % (url, "&" if "?" in url else "?", args)\n',
        encoding="utf-8",
    )
    (tmp_path / "tests" / "generic_views" / "test_base.py").write_text(
        'def test_redirect_with_query_string_in_destination_and_request():\n'
        '    response = RedirectView.as_view(url="/bar/?pork=spam", query_string=True)(self.rf.get("/foo/?utm_source=social"))\n'
        '    assert response.headers["Location"] == "/bar/?pork=spam&utm_source=social"\n',
        encoding="utf-8",
    )

    messages = _messages(collect_evidence(tmp_path))

    assert "Query-string merge logic should use explicit URL query detection instead of checking for a raw question mark." in messages
    assert "Regression tests cover existing destination query strings and incoming request query strings." in messages
