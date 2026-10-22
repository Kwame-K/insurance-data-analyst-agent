from __future__ import annotations

from pathlib import Path

import pytest

from insurance_data_analyst_agent.services.agent import (
    InsuranceDataAnalystAgent,
)
from insurance_data_analyst_agent.services.audit_writer import (
    AuditWriter,
)
from insurance_data_analyst_agent.services.router import (
    UnsupportedQuestionError,
)
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.tools.registry import (
    build_default_tool_registry,
)


@pytest.fixture
def agent(tmp_path: Path) -> InsuranceDataAnalystAgent:
    database_path = tmp_path / "portfolio.db"
    audit_directory = tmp_path / "audits"

    create_synthetic_database(
        database_path=database_path,
        seed=42,
    )

    return InsuranceDataAnalystAgent(
        database_path=database_path,
        dataset_version="synthetic-v1",
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(
            output_directory=audit_directory,
        ),
    )


def test_agent_answers_supported_loss_ratio_question(
    agent: InsuranceDataAnalystAgent,
) -> None:
    response = agent.answer(
        "Show the paid loss ratio for commercial property in Quebec for 2025."
    )

    assert response.question == (
        "Show the paid loss ratio for commercial property in Quebec for 2025."
    )

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == ("get_loss_ratio_by_segment")
    assert response.tool_calls[0].execution_status == "success"

    assert response.raw_results
    assert all(row["province"] == "QC" for row in response.raw_results)
    assert all(
        row["line_of_business"] == "commercial_property" for row in response.raw_results
    )
    assert all(row["underwriting_year"] == 2025 for row in response.raw_results)

    assert response.audit.dataset_version == "synthetic-v1"
    assert response.audit.calculation_definition == (
        "paid_loss_ratio = paid_claim_amount / written_premium"
    )


def test_agent_supports_french_question(
    agent: InsuranceDataAnalystAgent,
) -> None:
    response = agent.answer(
        "Afficher le ratio de sinistralité pour la propriété "
        "commerciale au Québec pour 2024 et 2025."
    )

    validated_arguments = response.tool_calls[0].validated_arguments

    assert validated_arguments["underwriting_years"] == [2024, 2025]
    assert validated_arguments["provinces"] == ["QC"]
    assert validated_arguments["lines_of_business"] == ["commercial_property"]


def test_agent_rejects_unsupported_question(
    agent: InsuranceDataAnalystAgent,
) -> None:
    with pytest.raises(
        UnsupportedQuestionError,
        match="Unsupported question",
    ):
        agent.answer("What is the average premium by broker?")


def test_agent_rejects_missing_database(
    tmp_path: Path,
) -> None:
    agent = InsuranceDataAnalystAgent(
        database_path=tmp_path / "missing.db",
        dataset_version="synthetic-v1",
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(
            output_directory=tmp_path / "audits",
        ),
    )

    with pytest.raises(
        FileNotFoundError,
        match="Database does not exist",
    ):
        agent.answer("Show loss ratio by province.")
