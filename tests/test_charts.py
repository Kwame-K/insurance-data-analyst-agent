from __future__ import annotations

from pathlib import Path

import pytest

from insurance_data_analyst_agent.charts import (
    UnsupportedChartError,
    generate_chart,
)
from insurance_data_analyst_agent.models.analytics import (
    ChartMetadata,
    ChartType,
)


@pytest.fixture
def chart_metadata() -> ChartMetadata:
    return ChartMetadata(
        chart_type=ChartType.GROUPED_BAR,
        x="underwriting_year",
        y="loss_ratio",
        series=[
            "province",
            "line_of_business",
        ],
        title="Paid loss ratio by segment",
    )


@pytest.fixture
def raw_results() -> list[dict]:
    return [
        {
            "province": "QC",
            "line_of_business": "commercial_property",
            "underwriting_year": 2024,
            "loss_ratio": 0.45,
        },
        {
            "province": "QC",
            "line_of_business": "commercial_property",
            "underwriting_year": 2025,
            "loss_ratio": 0.52,
        },
        {
            "province": "ON",
            "line_of_business": "commercial_property",
            "underwriting_year": 2024,
            "loss_ratio": 0.38,
        },
        {
            "province": "ON",
            "line_of_business": "commercial_property",
            "underwriting_year": 2025,
            "loss_ratio": 0.41,
        },
    ]


def test_generate_grouped_bar_chart(
    tmp_path: Path,
    raw_results: list[dict],
    chart_metadata: ChartMetadata,
) -> None:
    output_path = tmp_path / "loss_ratio.png"

    result = generate_chart(
        raw_results=raw_results,
        metadata=chart_metadata,
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.exists()
    assert output_path.suffix == ".png"
    assert output_path.stat().st_size > 0


def test_generate_chart_rejects_empty_results(
    tmp_path: Path,
    chart_metadata: ChartMetadata,
) -> None:
    with pytest.raises(
        ValueError,
        match="Cannot generate a chart from empty results",
    ):
        generate_chart(
            raw_results=[],
            metadata=chart_metadata,
            output_path=tmp_path / "empty.png",
        )


def test_generate_chart_rejects_unsupported_chart_type(
    tmp_path: Path,
    raw_results: list[dict],
) -> None:
    metadata = ChartMetadata(
        chart_type=ChartType.TABLE,
        x="underwriting_year",
        y="loss_ratio",
        series=[
            "province",
            "line_of_business",
        ],
        title="Unsupported chart",
    )

    with pytest.raises(
        UnsupportedChartError,
        match="Unsupported chart type",
    ):
        generate_chart(
            raw_results=raw_results,
            metadata=metadata,
            output_path=tmp_path / "unsupported.png",
        )
