from __future__ import annotations

import json
from pathlib import Path

import pytest

from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    Dimension,
)
from insurance_data_analyst_agent.models.routing import (
    CLAIM_FREQUENCY_TOOL,
    ToolSelection,
)
from insurance_data_analyst_agent.services.agent import InsuranceDataAnalystAgent
from insurance_data_analyst_agent.services.audit_writer import AuditWriter
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.tools.registry import build_default_tool_registry


def fixed_claim_frequency_router(
    question: str,
    available_years: list[int],
) -> ToolSelection:
    return ToolSelection(
        tool_name=CLAIM_FREQUENCY_TOOL,
        arguments=ClaimFrequencyRequest(
            years=[2023, 2024, 2025],
            dimensions=[Dimension.PROVINCE],
        ),
    )


@pytest.fixture
def audit_directory(tmp_path: Path) -> Path:
    return tmp_path / "audits"


@pytest.fixture
def agent(tmp_path: Path, audit_directory: Path) -> InsuranceDataAnalystAgent:
    database_path = tmp_path / "portfolio.db"
    create_synthetic_database(database_path=database_path, seed=42)

    return InsuranceDataAnalystAgent(
        database_path=database_path,
        dataset_version="synthetic-v1",
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(output_directory=audit_directory),
        router=fixed_claim_frequency_router,
    )


def test_agent_runs_claim_frequency_end_to_end(
    agent: InsuranceDataAnalystAgent,
    tmp_path: Path,
    audit_directory: Path,
) -> None:
    chart_path = tmp_path / "charts" / "frequency.png"

    response = agent.answer("claim frequency by province", chart_output_path=chart_path)

    assert response.tool_calls[0].tool_name == CLAIM_FREQUENCY_TOOL
    assert response.tool_calls[0].execution_status == "success"
    assert response.raw_results
    assert response.chart is not None
    assert response.chart.output_path == str(chart_path)
    assert chart_path.exists()

    audit_files = list(audit_directory.glob("*.json"))
    assert len(audit_files) == 1
    payload = json.loads(audit_files[0].read_text())
    assert payload["status"] == "success"
    assert payload["tool_calls"][0]["tool_name"] == CLAIM_FREQUENCY_TOOL
