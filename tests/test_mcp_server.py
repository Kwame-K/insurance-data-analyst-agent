from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.exc import OperationalError

from insurance_data_analyst_agent.config import Settings
from insurance_data_analyst_agent.mcp_server import server
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)

EXPECTED_TOOLS = {
    "get_loss_ratio_by_segment",
    "get_claim_frequency_trend",
    "get_claim_severity",
    "get_exposure_summary",
    "get_portfolio_quality_metrics",
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        audit_directory=tmp_path / "audits",
        chart_directory=tmp_path / "charts",
    )


@pytest.fixture(autouse=True)
def configured_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, settings: Settings
) -> None:
    database_path = tmp_path / "synthetic.db"
    create_synthetic_database(database_path, seed=42, policies_per_segment_year=10)
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    monkeypatch.setattr(server, "get_data_source", lambda: database_path)


CALLS: list[tuple[str, Callable[[], dict[str, Any]]]] = [
    (
        "get_loss_ratio_by_segment",
        lambda: server.get_loss_ratio_by_segment(underwriting_years=[2024, 2025]),
    ),
    (
        "get_claim_frequency_trend",
        lambda: server.get_claim_frequency_trend(years=[2024, 2025]),
    ),
    (
        "get_claim_severity",
        lambda: server.get_claim_severity(underwriting_years=[2025]),
    ),
    (
        "get_exposure_summary",
        lambda: server.get_exposure_summary(underwriting_years=[2025]),
    ),
    (
        "get_portfolio_quality_metrics",
        lambda: server.get_portfolio_quality_metrics(underwriting_years=[2025]),
    ),
]


@pytest.mark.parametrize(("tool_name", "call"), CALLS, ids=[c[0] for c in CALLS])
def test_tools_return_the_v1_envelope(
    tool_name: str, call: Callable[[], dict[str, Any]], settings: Settings
) -> None:
    output = call()

    assert output["api_version"] == "v1"
    assert output["status"] == "success"
    assert output["routing_provider"] == "direct"
    assert output["correlation_id"]
    assert output["data"]["tool_calls"][0]["tool_name"] == tool_name
    assert output["data"]["raw_results"]
    assert output["data"]["chart"] is not None or tool_name == (
        "get_portfolio_quality_metrics"
    )
    assert len(list(settings.audit_directory.glob("*.json"))) == 1


def test_filters_are_applied() -> None:
    output = server.get_claim_severity(
        underwriting_years=[2025],
        dimensions=["province"],  # type: ignore[list-item]
        provinces=["QC"],
    )

    assert {row["province"] for row in output["data"]["raw_results"]} == {"QC"}


def test_invalid_arguments_are_rejected_with_a_code() -> None:
    with pytest.raises(ToolError, match="VALIDATION_ERROR"):
        server.get_claim_frequency_trend(years=[2025])

    with pytest.raises(ToolError, match="VALIDATION_ERROR"):
        server.get_claim_severity(underwriting_years=[2025], provinces=["XX"])

    with pytest.raises(ToolError, match="VALIDATION_ERROR"):
        server.get_loss_ratio_by_segment(underwriting_years=[2025, 2025])


def test_year_without_data_returns_an_empty_audited_result(
    settings: Settings,
) -> None:
    output = server.get_exposure_summary(underwriting_years=[2030])

    assert output["status"] == "success"
    assert output["data"]["raw_results"] == []
    assert "No portfolio records" in output["data"]["answer"]
    assert len(list(settings.audit_directory.glob("*.json"))) == 1


def test_database_errors_are_mapped_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise OperationalError("SELECT secret", {}, Exception("password=hunter2"))

    monkeypatch.setattr(server, "run_tool_call", fail)

    with pytest.raises(ToolError, match="DATA_UNAVAILABLE") as error:
        server.get_claim_severity(underwriting_years=[2025])

    assert "hunter2" not in str(error.value)
    assert "secret" not in str(error.value)


def test_unexpected_errors_are_mapped_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("/private/path/token")

    monkeypatch.setattr(server, "run_tool_call", fail)

    with pytest.raises(ToolError, match="INTERNAL_ERROR") as error:
        server.get_claim_severity(underwriting_years=[2025])

    assert "/private" not in str(error.value)


def test_server_exposes_exactly_the_five_read_only_tools() -> None:
    tools = asyncio.run(server.mcp.list_tools())

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.description
