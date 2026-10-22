from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from insurance_data_analyst_agent.charts import generate_chart
from insurance_data_analyst_agent.models.analytics import (
    ChartType,
    ClaimFrequencyRequest,
    Dimension,
)
from insurance_data_analyst_agent.models.routing import (
    CLAIM_FREQUENCY_TOOL,
    ToolSelection,
)
from insurance_data_analyst_agent.services.response_builder import build_response
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.tools.registry import build_default_tool_registry


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic.db"
    create_synthetic_database(path, seed=42, policies_per_segment_year=10)
    return path


def make_selection(**arguments: Any) -> ToolSelection:
    return ToolSelection(
        tool_name=CLAIM_FREQUENCY_TOOL,
        arguments=ClaimFrequencyRequest(years=[2023, 2024, 2025], **arguments),
    )


def test_registry_executes_claim_frequency_tool(database_path: Path) -> None:
    selection = make_selection(dimensions=[Dimension.PROVINCE])

    results = build_default_tool_registry().execute(selection, database_path)

    assert results
    assert {"year", "province", "claim_frequency"} <= set(results[0])


def test_response_describes_segmented_trend(database_path: Path) -> None:
    selection = make_selection(dimensions=[Dimension.PROVINCE])
    results = build_default_tool_registry().execute(selection, database_path)

    response = build_response(
        question="claim frequency by province",
        selection=selection,
        raw_results=results,
        database_path=database_path,
        dataset_version="test",
    )

    assert response.tool_calls[0].tool_name == CLAIM_FREQUENCY_TOOL
    assert response.tool_calls[0].validated_arguments["years"] == [2023, 2024, 2025]
    assert response.chart is not None
    assert response.chart.chart_type == ChartType.LINE
    assert response.chart.series == ["province"]
    assert "highest claim frequency" in response.answer
    assert "claims / exposure units" in response.audit.calculation_definition


def test_portfolio_response_mentions_latest_change(database_path: Path) -> None:
    selection = make_selection()
    results = build_default_tool_registry().execute(selection, database_path)

    response = build_response(
        question="claim frequency trend",
        selection=selection,
        raw_results=results,
        database_path=database_path,
        dataset_version="test",
    )

    assert response.chart is not None
    assert response.chart.series == []
    assert "year-over-year change" in response.answer


def test_empty_results_give_explicit_answer(database_path: Path) -> None:
    response = build_response(
        question="q",
        selection=make_selection(),
        raw_results=[],
        database_path=database_path,
        dataset_version="test",
    )

    assert "No exposure records matched" in response.answer


@pytest.mark.parametrize("dimensions", [[], [Dimension.PROVINCE]])
def test_line_chart_is_written(
    database_path: Path, tmp_path: Path, dimensions: list[Dimension]
) -> None:
    selection = make_selection(dimensions=dimensions)
    results = build_default_tool_registry().execute(selection, database_path)
    response = build_response(
        question="q",
        selection=selection,
        raw_results=results,
        database_path=database_path,
        dataset_version="test",
    )
    assert response.chart is not None

    path = generate_chart(results, response.chart, tmp_path / "line.png")

    assert path.exists()
    assert path.stat().st_size > 0
