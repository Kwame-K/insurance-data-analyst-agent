from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from insurance_data_analyst_agent.models.analytics import (
    ChartMetadata,
    ChartType,
)


class UnsupportedChartError(ValueError):
    """Raised when chart metadata requests an unsupported chart type."""


def build_series_label(
    row: dict[str, Any],
    series_columns: list[str],
) -> str:
    """Build a deterministic display label for one chart series."""
    if not series_columns:
        return "Portfolio"

    return " | ".join(str(row[column]) for column in series_columns)


def generate_grouped_bar_chart(
    raw_results: list[dict[str, Any]],
    metadata: ChartMetadata,
    output_path: Path,
) -> Path:
    """Generate and save a grouped bar chart from analytical results."""
    if not raw_results:
        raise ValueError("Cannot generate a chart from empty results.")

    x_values = sorted({row[metadata.x] for row in raw_results})

    series_labels = sorted(
        {build_series_label(row, metadata.series) for row in raw_results}
    )

    if not x_values:
        raise ValueError("Chart x-axis has no values.")

    if not series_labels:
        raise ValueError("Chart has no series.")

    values_by_series_and_x = {
        (
            build_series_label(row, metadata.series),
            row[metadata.x],
        ): row[metadata.y]
        for row in raw_results
    }

    figure, axis = plt.subplots(
        figsize=(12, 6),
        layout="constrained",
    )

    bar_width = 0.8 / len(series_labels)
    x_positions = list(range(len(x_values)))

    for index, series_label in enumerate(series_labels):
        offset = (index - (len(series_labels) - 1) / 2) * bar_width

        y_values = [
            values_by_series_and_x.get(
                (series_label, x_value),
                0,
            )
            for x_value in x_values
        ]

        bar_positions = [position + offset for position in x_positions]

        axis.bar(
            bar_positions,
            y_values,
            width=bar_width,
            label=series_label,
        )

    axis.set_title(metadata.title)
    axis.set_xlabel(metadata.x.replace("_", " ").title())
    axis.set_ylabel(metadata.y.replace("_", " ").title())

    axis.set_xticks(x_positions)
    axis.set_xticklabels(x_values)

    if metadata.y == "loss_ratio":
        axis.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))

    axis.legend(
        title=" | ".join(
            column.replace("_", " ").title() for column in metadata.series
        ),
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(figure)

    return output_path


def generate_line_chart(
    raw_results: list[dict[str, Any]],
    metadata: ChartMetadata,
    output_path: Path,
) -> Path:
    """Generate and save a line chart (one line per series, or one overall)."""
    if not raw_results:
        raise ValueError("Cannot generate a chart from empty results.")

    x_values = sorted({row[metadata.x] for row in raw_results})

    values_by_series_and_x = {
        (
            build_series_label(row, metadata.series) or "Portfolio",
            row[metadata.x],
        ): row[metadata.y]
        for row in raw_results
    }
    series_labels = sorted({label for label, _ in values_by_series_and_x})

    figure, axis = plt.subplots(
        figsize=(12, 6),
        layout="constrained",
    )

    for series_label in series_labels:
        points = [
            (x_value, values_by_series_and_x[(series_label, x_value)])
            for x_value in x_values
            if values_by_series_and_x.get((series_label, x_value)) is not None
        ]
        axis.plot(
            [x for x, _ in points],
            [y for _, y in points],
            marker="o",
            label=series_label,
        )

    axis.set_title(metadata.title)
    axis.set_xlabel(metadata.x.replace("_", " ").title())
    axis.set_ylabel(metadata.y.replace("_", " ").title())
    axis.set_xticks(x_values)
    axis.set_xticklabels(x_values)

    if metadata.series:
        axis.legend(
            title=" | ".join(
                column.replace("_", " ").title() for column in metadata.series
            ),
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(figure)

    return output_path


def generate_chart(
    raw_results: list[dict[str, Any]],
    metadata: ChartMetadata,
    output_path: Path,
) -> Path:
    """Generate one explicitly supported chart type."""
    if metadata.chart_type == ChartType.GROUPED_BAR:
        return generate_grouped_bar_chart(
            raw_results=raw_results,
            metadata=metadata,
            output_path=output_path,
        )

    if metadata.chart_type == ChartType.LINE:
        return generate_line_chart(
            raw_results=raw_results,
            metadata=metadata,
            output_path=output_path,
        )

    raise UnsupportedChartError(f"Unsupported chart type: {metadata.chart_type}")
