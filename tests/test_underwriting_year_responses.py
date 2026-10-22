from __future__ import annotations

from pathlib import Path

import pytest

from insurance_data_analyst_agent.models.analytics import (
    ChartType,
    Dimension,
    ExposureSummaryRequest,
    PortfolioQualityRequest,
    SeverityRequest,
)
from insurance_data_analyst_agent.models.routing import selection_for
from insurance_data_analyst_agent.services.agent import InsuranceDataAnalystAgent
from insurance_data_analyst_agent.services.audit_writer import AuditWriter
from insurance_data_analyst_agent.services.response_builder import build_response
from insurance_data_analyst_agent.services.router import route_question
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.tools.registry import build_default_tool_registry


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "portfolio.db"
    create_synthetic_database(path, seed=42, policies_per_segment_year=10)
    return path


def run(database_path: Path, arguments: object, question: str = "q"):
    selection = selection_for(arguments)  # type: ignore[arg-type]
    rows = build_default_tool_registry().execute(selection, database_path)
    response = build_response(
        question=question,
        selection=selection,
        raw_results=rows,
        database_path=database_path,
        dataset_version="test",
    )
    return response


def test_severity_response_and_chart(database_path: Path) -> None:
    response = run(
        database_path,
        SeverityRequest(
            underwriting_years=[2023, 2024, 2025],
            dimensions=[Dimension.PROVINCE, Dimension.UNDERWRITING_YEAR],
        ),
    )

    assert response.tool_calls[0].tool_name == "get_claim_severity"
    assert "highest average claim severity" in response.answer
    assert response.chart is not None
    assert response.chart.chart_type == ChartType.GROUPED_BAR
    assert (response.chart.x, response.chart.y) == (
        "underwriting_year",
        "average_severity",
    )
    assert response.chart.series == ["province"]
    assert "paid_claim_amount / claim_count" in response.audit.calculation_definition


def test_exposure_chart_uses_first_dimension_without_underwriting_year(
    database_path: Path,
) -> None:
    response = run(
        database_path,
        ExposureSummaryRequest(
            underwriting_years=[2025], dimensions=[Dimension.PROVINCE]
        ),
    )

    assert response.chart is not None
    assert (response.chart.x, response.chart.series) == ("province", [])
    assert "exposure units" in response.answer


def test_quality_response_lists_every_metric_without_chart(
    database_path: Path,
) -> None:
    response = run(
        database_path, PortfolioQualityRequest(underwriting_years=[2023, 2024, 2025])
    )

    assert response.chart is None
    for text in (
        "paid loss ratio",
        "claim frequency",
        "average claim severity",
        "premium per exposure unit",
        "share of policies with a claim",
    ):
        assert text in response.answer


@pytest.mark.parametrize(
    "arguments",
    [
        SeverityRequest(underwriting_years=[2099]),
        ExposureSummaryRequest(underwriting_years=[2099]),
        PortfolioQualityRequest(underwriting_years=[2099]),
    ],
)
def test_empty_results_are_explained(database_path: Path, arguments: object) -> None:
    response = run(database_path, arguments)

    assert response.raw_results == []
    assert "No portfolio records matched" in response.answer


@pytest.mark.parametrize(
    ("question", "tool_name", "has_chart"),
    [
        ("What is the average claim severity by province?", "get_claim_severity", True),
        ("Show the exposure summary for 2025.", "get_exposure_summary", True),
        (
            "Show the portfolio quality metrics by line of business.",
            "get_portfolio_quality_metrics",
            False,
        ),
    ],
)
def test_agent_answers_questions_end_to_end(
    tmp_path: Path,
    database_path: Path,
    question: str,
    tool_name: str,
    has_chart: bool,
) -> None:
    agent = InsuranceDataAnalystAgent(
        database_path=database_path,
        dataset_version="synthetic-v1",
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(output_directory=tmp_path / "audits"),
        router=route_question,
    )
    chart_path = tmp_path / "chart.png"

    response = agent.answer(question, chart_output_path=chart_path)

    assert response.tool_calls[0].tool_name == tool_name
    assert response.raw_results
    assert chart_path.exists() is has_chart
    assert len(list((tmp_path / "audits").glob("*.json"))) == 1
