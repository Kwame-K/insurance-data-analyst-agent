from __future__ import annotations

import json
from pathlib import Path

import pytest

from insurance_data_analyst_agent.models.audit import (
    AgentRunAudit,
)
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


def test_audit_writer_persists_json_file(
    tmp_path: Path,
) -> None:
    audit_directory = tmp_path / "audits"

    audit = AgentRunAudit(
        agent_version="0.1.0",
        dataset_version="synthetic-v1",
        database_path="data/insurance_portfolio.db",
        question="Show loss ratio by province for 2025.",
        status="success",
    )

    output_path = AuditWriter(
        output_directory=audit_directory,
    ).write(audit)

    assert output_path.exists()
    assert output_path.suffix == ".json"

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["run_id"]
    assert payload["timestamp_utc"]
    assert payload["status"] == "success"
    assert payload["question"] == ("Show loss ratio by province for 2025.")


def test_agent_persists_successful_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "portfolio.db"
    audit_directory = tmp_path / "audits"

    create_synthetic_database(
        database_path=database_path,
        seed=42,
    )

    agent = InsuranceDataAnalystAgent(
        database_path=database_path,
        dataset_version="synthetic-v1",
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(
            output_directory=audit_directory,
        ),
    )

    response = agent.answer("Show paid loss ratio for Quebec in 2025.")

    audit_files = list(audit_directory.glob("*.json"))

    assert response.raw_results
    assert len(audit_files) == 1

    payload = json.loads(audit_files[0].read_text(encoding="utf-8"))

    assert payload["status"] == "success"
    assert payload["question"] == ("Show paid loss ratio for Quebec in 2025.")
    assert payload["tool_calls"][0]["tool_name"] == ("get_loss_ratio_by_segment")
    assert payload["raw_results"]
    assert payload["final_response"] is not None
    assert payload["error"] is None


def test_agent_persists_failed_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "portfolio.db"
    audit_directory = tmp_path / "audits"

    create_synthetic_database(
        database_path=database_path,
        seed=42,
    )

    agent = InsuranceDataAnalystAgent(
        database_path=database_path,
        dataset_version="synthetic-v1",
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(
            output_directory=audit_directory,
        ),
    )

    with pytest.raises(
        UnsupportedQuestionError,
        match="Unsupported question",
    ):
        agent.answer("What is the average premium by broker?")

    audit_files = list(audit_directory.glob("*.json"))

    assert len(audit_files) == 1

    payload = json.loads(audit_files[0].read_text(encoding="utf-8"))

    assert payload["status"] == "failed"
    assert payload["tool_calls"] == []
    assert payload["raw_results"] == []
    assert payload["final_response"] is None
    assert payload["error"]["error_type"] == ("UnsupportedQuestionError")
    assert "Unsupported question" in payload["error"]["message"]
