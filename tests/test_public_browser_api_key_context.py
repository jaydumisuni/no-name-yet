from __future__ import annotations

import json
from pathlib import Path

from main_review.evidence import SecretEvidenceProvider
from main_review.scanner import scan_repository


def _messages(tmp_path: Path) -> list[str]:
    insight = scan_repository(tmp_path)
    return [item.message for item in SecretEvidenceProvider().collect(tmp_path, insight)]


def _value() -> str:
    return "private-" + "service-key-1234567890"


def test_firebase_browser_client_api_key_is_not_treated_as_private_secret(tmp_path: Path) -> None:
    source = tmp_path / "app.js"
    public_identifier = "AIzaSy" + "PublicBrowserIdentifier123456"
    source.write_text(
        "\n".join(
            [
                "const firebaseConfig = {",
                "  apiKey: " + json.dumps(public_identifier) + ",",
                '  authDomain: "example.firebaseapp.com",',
                '  projectId: "example-project",',
                '  storageBucket: "example.appspot.com",',
                '  messagingSenderId: "123456789",',
                '  appId: "1:123456789:web:abcdef",',
                "};",
                "initializeApp(firebaseConfig);",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert not any("generic api key" in message.lower() for message in _messages(tmp_path))


def test_unrelated_javascript_api_key_remains_a_blocker(tmp_path: Path) -> None:
    source = tmp_path / "server.js"
    source.write_text(
        "const " + "api" + "Key = " + json.dumps(_value()) + ";\n",
        encoding="utf-8",
    )
    assert any("generic api key" in message.lower() for message in _messages(tmp_path))


def test_python_api_key_remains_a_blocker(tmp_path: Path) -> None:
    source = tmp_path / "settings.py"
    source.write_text(
        "api_" + "key = " + repr(_value()) + "\n",
        encoding="utf-8",
    )
    assert any("generic api key" in message.lower() for message in _messages(tmp_path))
