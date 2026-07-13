from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from main_review.llm_provider import LLMSettings, discover_route
from main_review.llm_review import run_cpl_review


class _CplGatewayHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {"id": "gateway/kimi-k2.5"},
                        {"id": "gateway/qwen3-coder-next"},
                        {"id": "gateway/glm-5.2"},
                    ],
                },
            )
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).requests.append({"path": self.path, "payload": payload})
        if self.path != "/v1/responses":
            self._json(404, {"error": "not found"})
            return

        review = {
            "verdict": "NEEDS WORK",
            "confidence": 0.94,
            "summary": "The divisor needs an explicit zero-count contract.",
            "findings": [
                {
                    "severity": "major",
                    "category": "correctness",
                    "path": "src/math.py",
                    "line_start": 2,
                    "line_end": 2,
                    "message": "A zero count raises an unhandled division error.",
                    "evidence": "return total / count",
                    "why_it_matters": "The review target can fail for an ordinary boundary value.",
                    "safer_alternative": "Validate count or define and test zero-count behavior.",
                }
            ],
            "unanswered_questions": [],
            "coverage": {"files_reviewed": ["src/math.py"], "areas": ["correctness"]},
        }
        self._json(
            200,
            {
                "id": "resp_test",
                "object": "response",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": json.dumps(review)}],
                    }
                ],
            },
        )


def test_cpl_responses_route_discovers_best_model_and_runs_specialist_reasoning(tmp_path: Path, monkeypatch) -> None:
    _CplGatewayHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CplGatewayHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}/v1"
        settings = LLMSettings(
            enabled=True,
            policy="required",
            provider="cpl",
            base_url=base_url,
            model="",
            protocol="responses",
            api_key="",
            timeout_seconds=5.0,
            max_output_tokens=2000,
        )
        route = discover_route(settings)

        assert route is not None
        assert route.provider == "cpl"
        assert route.model == "gateway/glm-5.2"
        assert route.protocol == "responses"

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "math.py").write_text(
            "def average(total, count):\n    return total / count\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("SERGEANT_CPL_DEPTH", "adaptive")
        monkeypatch.setenv("SERGEANT_CPL_MAX_PASSES", "2")
        result = run_cpl_review(
            tmp_path,
            ["src/math.py"],
            {"repository_review": {"verdict": "PASS"}},
            settings=settings,
            route=route,
        )

        assert result["officer"] == "Cpl"
        assert result["status"] == "completed"
        assert result["verdict"] == "NEEDS WORK"
        assert result["findings"][0]["evidence_verified"] is True
        assert result["route"]["model"] == "gateway/glm-5.2"
        assert [request["payload"]["model"] for request in _CplGatewayHandler.requests] == [
            "gateway/glm-5.2",
            "gateway/qwen3-coder-next",
        ]
        assert len(result["passes"]) == 2
        assert result["passes"][1]["specialist"] == "tests_contracts"
        for request in _CplGatewayHandler.requests:
            assert request["path"] == "/v1/responses"
            assert request["payload"]["input"][0]["role"] == "system"
            assert request["payload"]["input"][1]["role"] == "user"
            assert "src/math.py" in request["payload"]["input"][1]["content"][0]["text"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
