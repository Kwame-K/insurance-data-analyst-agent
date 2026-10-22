from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from insurance_data_analyst_agent.cli import app

runner = CliRunner()


def test_init_data_creates_database(tmp_path: Path) -> None:
    database_path = tmp_path / "portfolio.db"

    result = runner.invoke(
        app,
        [
            "init-data",
            "--database-path",
            str(database_path),
            "--seed",
            "42",
        ],
    )

    assert result.exit_code == 0
    assert database_path.exists()

    payload = json.loads(result.stdout)

    assert payload["status"] == "success"
    assert payload["database_path"] == str(database_path)
    assert payload["seed"] == 42
    assert payload["dataset_version"] == "synthetic-v1"


def test_loss_ratio_returns_auditable_json(tmp_path: Path) -> None:
    database_path = tmp_path / "portfolio.db"

    init_result = runner.invoke(
        app,
        [
            "init-data",
            "--database-path",
            str(database_path),
            "--seed",
            "42",
        ],
    )

    assert init_result.exit_code == 0
    assert database_path.exists()

    result = runner.invoke(
        app,
        [
            "loss-ratio",
            "--database-path",
            str(database_path),
            "--year",
            "2023",
            "--year",
            "2024",
            "--year",
            "2025",
            "--province",
            "QC",
        ],
    )

    assert result.exit_code == 0

    payload = json.loads(result.stdout)

    assert payload["question"]
    assert payload["raw_results"]
    assert payload["answer"]
    assert payload["chart"] is not None
    assert payload["audit"] is not None

    assert payload["tool_calls"] == [
        {
            "tool_name": "get_loss_ratio_by_segment",
            "validated_arguments": {
                "underwriting_years": [2023, 2024, 2025],
                "dimensions": [
                    "province",
                    "line_of_business",
                    "underwriting_year",
                ],
                "provinces": ["QC"],
                "lines_of_business": None,
            },
            "execution_status": "success",
        }
    ]

    assert payload["audit"]["dataset_version"] == "synthetic-v1"
    assert (
        payload["audit"]["calculation_definition"]
        == "paid_loss_ratio = paid_claim_amount / written_premium"
    )

    assert all(row["province"] == "QC" for row in payload["raw_results"])
    assert all(row["written_premium"] > 0 for row in payload["raw_results"])
    assert all(row["paid_claim_amount"] >= 0 for row in payload["raw_results"])
    assert all(row["loss_ratio"] >= 0 for row in payload["raw_results"])


def test_loss_ratio_fails_when_database_does_not_exist(tmp_path: Path) -> None:
    database_path = tmp_path / "missing.db"

    result = runner.invoke(
        app,
        [
            "loss-ratio",
            "--database-path",
            str(database_path),
            "--year",
            "2025",
        ],
    )

    assert result.exit_code != 0
    assert "Database does not exist" in result.stderr


def test_ask_routes_and_executes_loss_ratio_analysis(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "portfolio.db"

    init_result = runner.invoke(
        app,
        [
            "init-data",
            "--database-path",
            str(database_path),
            "--seed",
            "42",
        ],
    )

    assert init_result.exit_code == 0
    assert database_path.exists()

    result = runner.invoke(
        app,
        [
            "ask",
            ("Show the paid loss ratio for commercial property in Quebec for 2025."),
            "--database-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 0

    payload = json.loads(result.stdout)

    assert (
        payload["question"] == "Show the paid loss ratio for commercial property "
        "in Quebec for 2025."
    )

    assert payload["tool_calls"][0]["tool_name"] == ("get_loss_ratio_by_segment")

    assert payload["tool_calls"][0]["validated_arguments"] == {
        "underwriting_years": [2025],
        "dimensions": [
            "province",
            "line_of_business",
            "underwriting_year",
        ],
        "provinces": ["QC"],
        "lines_of_business": ["commercial_property"],
    }

    assert payload["raw_results"]
    assert all(row["province"] == "QC" for row in payload["raw_results"])
    assert all(
        row["line_of_business"] == "commercial_property"
        for row in payload["raw_results"]
    )
    assert all(row["underwriting_year"] == 2025 for row in payload["raw_results"])


def test_ask_rejects_unsupported_question(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "portfolio.db"

    init_result = runner.invoke(
        app,
        [
            "init-data",
            "--database-path",
            str(database_path),
            "--seed",
            "42",
        ],
    )

    assert init_result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "ask",
            "What is the average premium by broker?",
            "--database-path",
            str(database_path),
        ],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Unsupported question" in result.stderr


def init_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "portfolio.db"
    result = runner.invoke(
        app, ["init-data", "--database-path", str(database_path), "--seed", "42"]
    )
    assert result.exit_code == 0
    return database_path


def test_claim_frequency_returns_auditable_json(tmp_path: Path) -> None:
    database_path = init_database(tmp_path)

    result = runner.invoke(
        app,
        [
            "claim-frequency",
            "--database-path",
            str(database_path),
            "--year",
            "2024",
            "--year",
            "2025",
            "--by",
            "province",
            "--province",
            "QC",
        ],
    )

    assert result.exit_code == 0

    payload = json.loads(result.stdout)

    assert payload["tool_calls"][0]["tool_name"] == "get_claim_frequency_trend"
    assert payload["raw_results"]
    assert all(row["province"] == "QC" for row in payload["raw_results"])
    assert "claims / exposure units" in payload["audit"]["calculation_definition"]


def test_claim_frequency_writes_chart(tmp_path: Path) -> None:
    database_path = init_database(tmp_path)
    chart_path = tmp_path / "frequency.png"

    result = runner.invoke(
        app,
        [
            "claim-frequency",
            "--database-path",
            str(database_path),
            "-y",
            "2024",
            "-y",
            "2025",
            "--chart-output",
            str(chart_path),
        ],
    )

    assert result.exit_code == 0
    assert chart_path.exists()
    assert json.loads(result.stdout)["chart"]["output_path"] == str(chart_path)


def test_claim_frequency_rejects_invalid_arguments(tmp_path: Path) -> None:
    database_path = init_database(tmp_path)

    single_year = runner.invoke(
        app,
        ["claim-frequency", "--database-path", str(database_path), "-y", "2025"],
    )
    unknown_segment = runner.invoke(
        app,
        [
            "claim-frequency",
            "--database-path",
            str(database_path),
            "-y",
            "2024",
            "-y",
            "2025",
            "--by",
            "postal_code",
        ],
    )

    assert single_year.exit_code != 0
    assert unknown_segment.exit_code != 0


def test_underwriting_year_commands_return_auditable_json(tmp_path: Path) -> None:
    database_path = init_database(tmp_path)

    for command, tool_name in [
        ("severity", "get_claim_severity"),
        ("exposure-summary", "get_exposure_summary"),
        ("portfolio-quality-metrics", "get_portfolio_quality_metrics"),
    ]:
        result = runner.invoke(
            app,
            [
                command,
                "--database-path",
                str(database_path),
                "-y",
                "2024",
                "-y",
                "2025",
                "--by",
                "province",
                "--province",
                "QC",
            ],
        )

        assert result.exit_code == 0, command

        payload = json.loads(result.stdout)

        assert payload["tool_calls"][0]["tool_name"] == tool_name
        assert payload["tool_calls"][0]["validated_arguments"]["dimensions"] == [
            "province",
            "underwriting_year",
        ]
        assert payload["raw_results"]
        assert all(row["province"] == "QC" for row in payload["raw_results"])


def test_severity_and_exposure_commands_write_charts(tmp_path: Path) -> None:
    database_path = init_database(tmp_path)

    for command in ("severity", "exposure-summary"):
        chart_path = tmp_path / f"{command}.png"

        result = runner.invoke(
            app,
            [
                command,
                "--database-path",
                str(database_path),
                "-y",
                "2025",
                "--chart-output",
                str(chart_path),
            ],
        )

        assert result.exit_code == 0, command
        assert chart_path.exists()


def test_underwriting_year_commands_reject_invalid_arguments(tmp_path: Path) -> None:
    database_path = init_database(tmp_path)

    for extra in (
        ["-y", "1999"],
        ["-y", "2025", "--by", "postal_code"],
        ["-y", "2025", "--province", "XX"],
    ):
        result = runner.invoke(
            app,
            ["severity", "--database-path", str(database_path), *extra],
        )

        assert result.exit_code != 0, extra
