"""Black-box end-to-end tests against the running platform.

Start the stack first (insurance-agentic-platform):
    docker compose up --build -d
Then run:
    uv run pytest -m e2e -rs -v

The Data Analyst Agent API is called over HTTP (default http://127.0.0.1:8003,
override with E2E_API_URL) with the real PostgreSQL data and the configured
router. Assertions target stable invariants: shapes, contracts, and
cross-endpoint consistency, never exact figures or LLM wording.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest

pytestmark = pytest.mark.e2e

API_URL = os.environ.get("E2E_API_URL", "http://127.0.0.1:8003")

TYPED_ENDPOINTS = {
    "/v1/loss-ratio": ("get_loss_ratio_by_segment", "underwriting_years"),
    "/v1/claim-frequency": ("get_claim_frequency_trend", "years"),
    "/v1/severity": ("get_claim_severity", "underwriting_years"),
    "/v1/exposure-summary": ("get_exposure_summary", "underwriting_years"),
    "/v1/portfolio-quality-metrics": (
        "get_portfolio_quality_metrics",
        "underwriting_years",
    ),
}


@pytest.fixture(scope="module", autouse=True)
def platform_is_up() -> None:
    try:
        urllib.request.urlopen(f"{API_URL}/health", timeout=3).close()
    except OSError:
        pytest.skip(
            f"Data Analyst Agent not reachable at {API_URL}; start the platform "
            "with 'docker compose up --build -d' in insurance-agentic-platform."
        )


def _post(
    path: str,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, dict(response.headers), json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), json.loads(error.read())


def _arguments(field: str, **extra: Any) -> dict[str, Any]:
    years = [2024, 2025]
    return {"arguments": {field: years, **extra}}


def test_health_reports_the_agent_version() -> None:
    with urllib.request.urlopen(f"{API_URL}/health", timeout=5) as response:
        payload = json.loads(response.read())

    assert payload["agent_version"]


@pytest.mark.parametrize("path", list(TYPED_ENDPOINTS))
def test_typed_endpoints_return_the_v1_envelope(path: str) -> None:
    tool_name, field = TYPED_ENDPOINTS[path]

    status, headers, payload = _post(
        path,
        _arguments(field),
        headers={"X-Correlation-ID": "e2e-typed-0001"},
    )

    assert status == 200
    assert headers["X-Correlation-ID"] == "e2e-typed-0001"
    assert payload["api_version"] == "v1"
    assert payload["status"] == "success"
    assert payload["correlation_id"] == "e2e-typed-0001"
    assert payload["routing_provider"] == "direct"
    assert payload["data"]["tool_calls"][0]["tool_name"] == tool_name
    assert payload["data"]["raw_results"]
    assert payload["data"]["audit"]["dataset_version"]
    assert "postgresql" in payload["data"]["audit"]["database_path"]


def test_filters_restrict_the_result_set() -> None:
    _, _, payload = _post(
        "/v1/severity",
        _arguments("underwriting_years", dimensions=["province"], provinces=["QC"]),
    )

    provinces = {row["province"] for row in payload["data"]["raw_results"]}
    assert provinces == {"QC"}


def test_portfolio_quality_matches_the_dedicated_tools() -> None:
    _, _, quality = _post(
        "/v1/portfolio-quality-metrics",
        _arguments("underwriting_years", dimensions=["province"]),
    )
    _, _, loss_ratio = _post(
        "/v1/loss-ratio",
        _arguments("underwriting_years", dimensions=["province"]),
    )

    quality_by_province = {
        row["province"]: row["loss_ratio"] for row in quality["data"]["raw_results"]
    }
    loss_ratio_by_province = {
        row["province"]: row["loss_ratio"] for row in loss_ratio["data"]["raw_results"]
    }

    assert quality_by_province == loss_ratio_by_province


def test_analyze_answers_a_natural_language_question() -> None:
    status, _, payload = _post(
        "/v1/analyze",
        {"question": "What is the loss ratio by province for 2025?"},
    )

    assert status == 200
    assert payload["status"] == "success"
    assert payload["routing_provider"]
    assert payload["data"]["tool_calls"]
    assert payload["data"]["answer"]


def test_chart_is_generated_on_request() -> None:
    status, _, payload = _post(
        "/v1/loss-ratio",
        {
            **_arguments(
                "underwriting_years",
                dimensions=["province", "line_of_business", "underwriting_year"],
            ),
            "include_chart": True,
        },
    )

    assert status == 200
    assert payload["data"]["chart"]["output_path"].endswith(
        f"{payload['correlation_id']}.png"
    )


def test_unsupported_question_is_rejected_with_an_error_envelope() -> None:
    status, headers, payload = _post(
        "/v1/analyze", {"question": "What is the weather today?"}
    )

    assert status == 422
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "unsupported_question"
    assert payload["correlation_id"] == headers["X-Correlation-ID"]


def test_unknown_fields_are_rejected() -> None:
    status, _, payload = _post(
        "/v1/analyze",
        {"question": "Loss ratio for 2025", "sql": "DROP TABLE claims"},
    )

    assert status == 422
    assert payload["error"]["code"] == "validation_error"


def test_claim_frequency_requires_two_years() -> None:
    status, _, payload = _post("/v1/claim-frequency", {"arguments": {"years": [2025]}})

    assert status == 422
    assert payload["error"]["code"] == "validation_error"
