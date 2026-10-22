from __future__ import annotations

from pathlib import Path

import pytest

from insurance_data_analyst_agent.models.analytics import (
    Dimension,
    LossRatioRequest,
)
from insurance_data_analyst_agent.models.routing import ToolSelection
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.tools.registry import (
    RegisteredTool,
    ToolNotFoundError,
    ToolRegistry,
    build_default_tool_registry,
)


def test_default_registry_contains_all_tools() -> None:
    registry = build_default_tool_registry()

    assert registry.list_tool_names() == [
        "get_claim_frequency_trend",
        "get_claim_severity",
        "get_exposure_summary",
        "get_loss_ratio_by_segment",
        "get_portfolio_quality_metrics",
    ]


def test_registry_returns_registered_tool() -> None:
    registry = build_default_tool_registry()

    tool = registry.get("get_loss_ratio_by_segment")

    assert tool.name == "get_loss_ratio_by_segment"
    assert "loss ratio" in tool.description.lower()


def test_registry_rejects_unknown_tool() -> None:
    registry = build_default_tool_registry()

    with pytest.raises(
        ToolNotFoundError,
        match="Tool is not registered: unknown_tool",
    ):
        registry.get("unknown_tool")


def test_registry_rejects_duplicate_tool_registration() -> None:
    registry = ToolRegistry()

    tool = RegisteredTool(
        name="test_tool",
        description="Test tool.",
        handler=lambda _database_path, _request: [],
    )

    registry.register(tool)

    with pytest.raises(
        ValueError,
        match="Tool is already registered: test_tool",
    ):
        registry.register(tool)


def test_registry_executes_loss_ratio_tool(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "portfolio.db"

    create_synthetic_database(
        database_path=database_path,
        seed=42,
    )

    selection = ToolSelection(
        tool_name="get_loss_ratio_by_segment",
        arguments=LossRatioRequest(
            underwriting_years=[2025],
            dimensions=[
                Dimension.PROVINCE,
                Dimension.LINE_OF_BUSINESS,
                Dimension.UNDERWRITING_YEAR,
            ],
            provinces=["QC"],
            lines_of_business=["commercial_property"],
        ),
    )

    registry = build_default_tool_registry()

    results = registry.execute(
        selection=selection,
        database_path=database_path,
    )

    assert results
    assert all(row["province"] == "QC" for row in results)
    assert all(row["line_of_business"] == "commercial_property" for row in results)
    assert all(row["underwriting_year"] == 2025 for row in results)
