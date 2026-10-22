from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from insurance_data_analyst_agent.api.app import create_app
from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.llm.base import LLMClientError
from insurance_data_analyst_agent.llm.fake import FakeLLMClient
from insurance_data_analyst_agent.llm.fallback import FallbackLLMClient
from insurance_data_analyst_agent.services.llm_router import LLMRouter
from insurance_data_analyst_agent.services.router import route_question
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)

QUESTION = "What is the loss ratio for QC commercial property in 2025?"

LLM_SELECTION = {
    "tool_name": "get_loss_ratio_by_segment",
    "arguments": {
        "underwriting_years": [2025],
        "dimensions": ["province", "line_of_business", "underwriting_year"],
        "provinces": None,
        "lines_of_business": None,
    },
}


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "portfolio.db"
    create_synthetic_database(path, policies_per_segment_year=2)
    return path


def make_client(
    tmp_path: Path,
    database_path: Path,
    router=route_question,
) -> TestClient:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_path=database_path,
        audit_directory=tmp_path / "audits",
        chart_directory=tmp_path / "charts",
    )
    app = create_app(settings=settings, router=router)
    return TestClient(app, raise_server_exceptions=False)


def llm_router(client: FakeLLMClient) -> LLMRouter:
    return LLMRouter(client=FallbackLLMClient([("gemini", client)]))


def test_health(tmp_path: Path, database_path: Path) -> None:
    response = make_client(tmp_path, database_path).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["api_version"] == "v1"


def test_analyze_deterministic(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/analyze", json={"question": QUESTION, "request_id": "client-1"}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["api_version"] == "v1"
    assert body["request_id"] == "client-1"
    assert body["routing_provider"] == "deterministic"
    assert body["data"]["tool_calls"][0]["tool_name"] == "get_loss_ratio_by_segment"
    assert len(list((tmp_path / "audits").glob("*.json"))) == 1


def test_correlation_id_is_propagated(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/analyze",
        json={"question": QUESTION},
        headers={"X-Correlation-ID": "client-corr-1"},
    )

    assert response.json()["correlation_id"] == "client-corr-1"
    assert response.headers["X-Correlation-ID"] == "client-corr-1"


def test_invalid_correlation_id_is_replaced(
    tmp_path: Path, database_path: Path
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.get("/health", headers={"X-Correlation-ID": "../bad id"})

    assert response.headers["X-Correlation-ID"] != "../bad id"
    assert len(response.headers["X-Correlation-ID"]) >= 32


def test_request_id_header_is_echoed(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/analyze",
        json={"question": QUESTION},
        headers={"X-Request-ID": "header-req-1"},
    )

    assert response.json()["request_id"] == "header-req-1"


def test_analyze_uses_llm_when_valid(tmp_path: Path, database_path: Path) -> None:
    fake = FakeLLMClient(response=LLM_SELECTION)
    client = make_client(tmp_path, database_path, llm_router(fake))

    response = client.post("/v1/analyze", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json()["routing_provider"] == "gemini"
    assert len(fake.calls) == 1


def test_analyze_falls_back_to_deterministic(
    tmp_path: Path, database_path: Path
) -> None:
    fake = FakeLLMClient(error=LLMClientError("down"))
    client = make_client(tmp_path, database_path, llm_router(fake))

    response = client.post("/v1/analyze", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json()["routing_provider"] == "deterministic"


def test_unsupported_question_is_audited(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/analyze", json={"question": "What is the weather today?"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_question"
    assert len(list((tmp_path / "audits").glob("*.json"))) == 1


def test_analyze_rejects_free_sql(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/analyze", json={"question": QUESTION, "sql": "DROP TABLE claims"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_missing_database_returns_503(tmp_path: Path) -> None:
    client = make_client(tmp_path, tmp_path / "missing.db")

    response = client.post("/v1/analyze", json={"question": QUESTION})

    assert response.status_code == 503
    assert "missing.db" not in response.text


def test_loss_ratio_direct_call(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/loss-ratio",
        json={
            "arguments": {"underwriting_years": [2025], "provinces": ["QC"]},
            "request_id": "r-1",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["routing_provider"] == "direct"
    assert body["request_id"] == "r-1"
    assert body["data"]["raw_results"]
    assert all(row["province"] == "QC" for row in body["data"]["raw_results"])


@pytest.mark.parametrize(
    "arguments",
    [
        {"underwriting_years": [1999]},
        {"underwriting_years": [2025], "provinces": ["XX"]},
        {"underwriting_years": []},
    ],
)
def test_loss_ratio_rejects_invalid_arguments(
    tmp_path: Path, database_path: Path, arguments: dict
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post("/v1/loss-ratio", json={"arguments": arguments})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


ALL_DIMENSIONS = ["province", "line_of_business", "underwriting_year"]


def test_include_chart_writes_png(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/loss-ratio",
        json={
            "arguments": {"underwriting_years": [2025], "dimensions": ALL_DIMENSIONS},
            "include_chart": True,
        },
        headers={"X-Correlation-ID": "chart-1"},
    )

    assert response.status_code == 200
    assert (tmp_path / "charts" / "chart-1.png").exists()


def test_include_chart_rejects_incompatible_dimensions(
    tmp_path: Path, database_path: Path
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/loss-ratio",
        json={"arguments": {"underwriting_years": [2025]}, "include_chart": True},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert not list((tmp_path / "audits").glob("*.json"))


def test_include_chart_with_empty_results_returns_no_chart(
    tmp_path: Path, database_path: Path
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/loss-ratio",
        json={
            "arguments": {"underwriting_years": [2099], "dimensions": ALL_DIMENSIONS},
            "include_chart": True,
        },
        headers={"X-Correlation-ID": "empty-1"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["data"]["raw_results"] == []
    assert body["data"]["answer"].startswith("No portfolio records matched")
    assert body["data"]["chart"]["output_path"] is None
    assert not (tmp_path / "charts" / "empty-1.png").exists()


FREQUENCY_QUESTION = "Show the claim frequency by province for 2024 and 2025."


def test_analyze_routes_claim_frequency_question(
    tmp_path: Path, database_path: Path
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post("/v1/analyze", json={"question": FREQUENCY_QUESTION})
    body = response.json()

    assert response.status_code == 200
    assert body["data"]["tool_calls"][0]["tool_name"] == "get_claim_frequency_trend"
    assert body["data"]["raw_results"]


def test_analyze_rejects_claim_frequency_threshold_question(
    tmp_path: Path, database_path: Path
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/analyze",
        json={"question": "Flag segments where claim frequency rose by more than 20%."},
    )

    assert response.status_code == 422
    assert not response.json().get("data")


def test_claim_frequency_direct_call(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/claim-frequency",
        json={
            "arguments": {
                "years": [2024, 2025],
                "dimensions": ["province"],
                "provinces": ["QC"],
            },
            "request_id": "f-1",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["routing_provider"] == "direct"
    assert body["request_id"] == "f-1"
    assert body["data"]["tool_calls"][0]["tool_name"] == "get_claim_frequency_trend"
    assert body["data"]["raw_results"]
    assert all(row["province"] == "QC" for row in body["data"]["raw_results"])


@pytest.mark.parametrize(
    "arguments",
    [
        {"years": [2025]},
        {"years": [1999, 2025]},
        {"years": [2024, 2025], "provinces": ["XX"]},
        {"years": [2024, 2025], "dimensions": ["underwriting_year"]},
        {"underwriting_years": [2024, 2025]},
    ],
)
def test_claim_frequency_rejects_invalid_arguments(
    tmp_path: Path, database_path: Path, arguments: dict
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post("/v1/claim-frequency", json={"arguments": arguments})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_claim_frequency_include_chart_writes_png(
    tmp_path: Path, database_path: Path
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/claim-frequency",
        json={"arguments": {"years": [2024, 2025]}, "include_chart": True},
        headers={"X-Correlation-ID": "freq-chart-1"},
    )

    assert response.status_code == 200
    assert (tmp_path / "charts" / "freq-chart-1.png").exists()


def test_claim_frequency_with_empty_results_returns_no_chart(
    tmp_path: Path, database_path: Path
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/claim-frequency",
        json={"arguments": {"years": [2098, 2099]}, "include_chart": True},
        headers={"X-Correlation-ID": "freq-empty-1"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["raw_results"] == []
    assert not (tmp_path / "charts" / "freq-empty-1.png").exists()


UNDERWRITING_YEAR_ENDPOINTS = [
    ("/v1/severity", "get_claim_severity", True),
    ("/v1/exposure-summary", "get_exposure_summary", True),
    ("/v1/portfolio-quality-metrics", "get_portfolio_quality_metrics", False),
]


@pytest.mark.parametrize(
    ("path", "tool_name", "has_chart"), UNDERWRITING_YEAR_ENDPOINTS
)
def test_underwriting_year_direct_calls(
    tmp_path: Path,
    database_path: Path,
    path: str,
    tool_name: str,
    has_chart: bool,
) -> None:
    client = make_client(tmp_path, database_path)
    payload: dict = {
        "arguments": {
            "underwriting_years": [2024, 2025],
            "dimensions": ["province", "underwriting_year"],
            "provinces": ["QC"],
        },
        "request_id": "u-1",
    }
    if has_chart:
        payload["include_chart"] = True

    response = client.post(
        path, json=payload, headers={"X-Correlation-ID": "uw-chart-1"}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["routing_provider"] == "direct"
    assert body["request_id"] == "u-1"
    assert body["data"]["tool_calls"][0]["tool_name"] == tool_name
    assert body["data"]["raw_results"]
    assert all(row["province"] == "QC" for row in body["data"]["raw_results"])
    assert (tmp_path / "charts" / "uw-chart-1.png").exists() is has_chart


@pytest.mark.parametrize(
    ("path", "tool_name", "has_chart"), UNDERWRITING_YEAR_ENDPOINTS
)
@pytest.mark.parametrize(
    "arguments",
    [
        {"underwriting_years": []},
        {"underwriting_years": [1999]},
        {"underwriting_years": [2025], "provinces": ["XX"]},
        {"underwriting_years": [2025], "dimensions": ["province", "province"]},
        {"years": [2024, 2025]},
    ],
)
def test_underwriting_year_direct_calls_reject_invalid_arguments(
    tmp_path: Path,
    database_path: Path,
    path: str,
    tool_name: str,
    has_chart: bool,
    arguments: dict,
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(path, json={"arguments": arguments})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_quality_endpoint_has_no_chart_option(
    tmp_path: Path, database_path: Path
) -> None:
    client = make_client(tmp_path, database_path)

    response = client.post(
        "/v1/portfolio-quality-metrics",
        json={"arguments": {"underwriting_years": [2025]}, "include_chart": True},
    )

    assert response.status_code == 422


def test_analyze_routes_new_tools(tmp_path: Path, database_path: Path) -> None:
    client = make_client(tmp_path, database_path)

    for question, tool_name in [
        ("What is the average claim severity by province?", "get_claim_severity"),
        ("Show the exposure summary for 2025.", "get_exposure_summary"),
        (
            "Show the portfolio quality metrics for 2025.",
            "get_portfolio_quality_metrics",
        ),
    ]:
        response = client.post("/v1/analyze", json={"question": question})

        assert response.status_code == 200, question
        assert response.json()["data"]["tool_calls"][0]["tool_name"] == tool_name
