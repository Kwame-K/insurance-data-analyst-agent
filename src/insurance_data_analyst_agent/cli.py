from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal, TypeVar

import typer
from sqlalchemy.engine import make_url

from insurance_data_analyst_agent.charts import generate_chart
from insurance_data_analyst_agent.config import settings
from insurance_data_analyst_agent.infrastructure.persistence.access import DataSource
from insurance_data_analyst_agent.infrastructure.persistence.database import (
    create_database_engine,
    run_migrations,
)
from insurance_data_analyst_agent.llm.groq_client import (
    GroqLLMClient,
)
from insurance_data_analyst_agent.models.analytics import (
    AnalyticsResponse,
    ClaimFrequencyRequest,
    Dimension,
    ExposureSummaryRequest,
    LossRatioRequest,
    PortfolioQualityRequest,
    SeverityRequest,
    UnderwritingYearRequest,
)
from insurance_data_analyst_agent.services.agent import (
    InsuranceDataAnalystAgent,
)
from insurance_data_analyst_agent.services.audit_writer import (
    AuditWriter,
)
from insurance_data_analyst_agent.services.llm_router import (
    LLMRouter,
)
from insurance_data_analyst_agent.services.response_builder import (
    build_claim_frequency_response,
    build_exposure_summary_response,
    build_loss_ratio_response,
    build_portfolio_quality_response,
    build_severity_response,
)
from insurance_data_analyst_agent.services.router import (
    UnsupportedQuestionError,
    route_question,
)
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.synthetic_data.loader import load_synthetic_data
from insurance_data_analyst_agent.tools.claim_frequency import (
    get_claim_frequency_trend,
)
from insurance_data_analyst_agent.tools.exposure_summary import get_exposure_summary
from insurance_data_analyst_agent.tools.loss_ratio import (
    get_loss_ratio_by_segment,
)
from insurance_data_analyst_agent.tools.portfolio_quality import (
    get_portfolio_quality_metrics,
)
from insurance_data_analyst_agent.tools.registry import (
    build_default_tool_registry,
)
from insurance_data_analyst_agent.tools.severity import get_claim_severity

app = typer.Typer(
    name="insurance-data-analyst",
    help="Controlled and auditable insurance portfolio analytics.",
    no_args_is_help=True,
)

DatabasePathOption = Annotated[
    Path,
    typer.Option(
        "--database-path",
        "-d",
        help="Path to the SQLite portfolio database.",
    ),
]

QuestionArgument = Annotated[
    str,
    typer.Argument(
        help="Natural-language analytical question.",
    ),
]

SeedOption = Annotated[
    int,
    typer.Option(
        "--seed",
        help="Deterministic seed used to generate synthetic data.",
    ),
]

YearOption = Annotated[
    list[int],
    typer.Option(
        "--year",
        "-y",
        help="Underwriting year. Repeat the option for multiple years.",
    ),
]

FrequencyYearOption = Annotated[
    list[int],
    typer.Option(
        "--year",
        "-y",
        help="Year. Repeat the option: at least two years are required.",
    ),
]

SegmentOption = Annotated[
    list[str] | None,
    typer.Option(
        "--by",
        help="Segment: province or line_of_business. Repeat for both.",
    ),
]

ProvinceOption = Annotated[
    list[str] | None,
    typer.Option(
        "--province",
        help="Province filter. Repeat the option for multiple provinces.",
    ),
]

LineOfBusinessOption = Annotated[
    list[str] | None,
    typer.Option(
        "--line-of-business",
        "--lob",
        help="Line-of-business filter. Repeat the option for multiple values.",
    ),
]

ChartOutputOption = Annotated[
    Path | None,
    typer.Option(
        "--chart-output",
        help=("Optional path where a generated chart PNG will be saved."),
    ),
]

RouterOption = Annotated[
    Literal["deterministic", "groq"],
    typer.Option(
        "--router",
        help=("Routing mode: deterministic or groq. Default: deterministic."),
    ),
]


def build_router(
    router_name: Literal["deterministic", "groq"],
):
    """Build the requested question router."""
    if router_name == "deterministic":
        return route_question

    if settings.groq_api_key is None:
        raise typer.BadParameter("GROQ_API_KEY is required when using --router groq.")

    if settings.groq_model is None:
        raise typer.BadParameter("GROQ_MODEL is required when using --router groq.")

    groq_client = GroqLLMClient(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
    )

    return LLMRouter(client=groq_client)


@app.command("init-data")
def init_data(
    database_path: DatabasePathOption = settings.database_path,
    seed: SeedOption = 20260904,
) -> None:
    """Create the deterministic synthetic insurance portfolio database."""
    create_synthetic_database(
        database_path=database_path,
        seed=seed,
    )

    typer.echo(
        json.dumps(
            {
                "status": "success",
                "database_path": str(database_path),
                "seed": seed,
                "dataset_version": settings.dataset_version,
            },
            indent=2,
        )
    )


@app.command("init-db")
def init_db(seed: SeedOption = 20260904) -> None:
    """Apply Alembic migrations and load synthetic data into DATABASE_URL."""
    if not settings.database_url:
        raise typer.BadParameter("DATABASE_URL is required for init-db.")

    run_migrations(settings.database_url)

    engine = create_database_engine(settings.database_url)
    try:
        load_synthetic_data(engine, seed=seed)
    finally:
        engine.dispose()

    typer.echo(
        json.dumps(
            {
                "status": "success",
                "backend": make_url(settings.database_url).get_backend_name(),
                "seed": seed,
                "dataset_version": settings.dataset_version,
            },
            indent=2,
        )
    )


@app.command("loss-ratio")
def loss_ratio(
    years: YearOption,
    province: ProvinceOption = None,
    line_of_business: LineOfBusinessOption = None,
    database_path: DatabasePathOption = settings.database_path,
) -> None:
    """Calculate paid loss ratio by province, line of business, and year."""
    if not database_path.exists():
        raise typer.BadParameter(
            f"Database does not exist: {database_path}. Run 'init-data' first."
        )

    request = LossRatioRequest(
        underwriting_years=years,
        dimensions=[
            Dimension.PROVINCE,
            Dimension.LINE_OF_BUSINESS,
            Dimension.UNDERWRITING_YEAR,
        ],
        provinces=province,
        lines_of_business=line_of_business,
    )

    raw_results = get_loss_ratio_by_segment(
        database_path=database_path,
        request=request,
    )

    question = (
        "Show the paid loss ratio by province and line of business "
        f"for underwriting years {', '.join(str(year) for year in years)}."
    )

    response = build_loss_ratio_response(
        question=question,
        request=request,
        raw_results=raw_results,
        database_path=database_path,
        dataset_version=settings.dataset_version,
    )

    typer.echo(response.model_dump_json(indent=2))


@app.command("claim-frequency")
def claim_frequency(
    years: FrequencyYearOption,
    by: SegmentOption = None,
    province: ProvinceOption = None,
    line_of_business: LineOfBusinessOption = None,
    database_path: DatabasePathOption = settings.database_path,
    chart_output: ChartOutputOption = None,
) -> None:
    """Calculate claim frequency and its year-over-year change."""
    if not database_path.exists():
        raise typer.BadParameter(
            f"Database does not exist: {database_path}. Run 'init-data' first."
        )

    try:
        request = ClaimFrequencyRequest(
            years=years,
            dimensions=[Dimension(value) for value in by or []],
            provinces=province,
            lines_of_business=line_of_business,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    raw_results = get_claim_frequency_trend(database_path, request)

    response = build_claim_frequency_response(
        question=(
            "Show the claim frequency trend for years "
            f"{', '.join(str(year) for year in request.years)}."
        ),
        request=request,
        raw_results=raw_results,
        database_path=database_path,
        dataset_version=settings.dataset_version,
    )

    if chart_output is not None and response.chart is not None and raw_results:
        generated_chart_path = generate_chart(
            raw_results=raw_results,
            metadata=response.chart,
            output_path=chart_output,
        )
        response.chart.output_path = str(generated_chart_path)

    typer.echo(response.model_dump_json(indent=2))


RequestT = TypeVar("RequestT", bound=UnderwritingYearRequest)


def run_underwriting_year_analysis(
    *,
    request_model: type[RequestT],
    tool: Callable[[DataSource, RequestT], list[dict[str, Any]]],
    build_response: Callable[..., AnalyticsResponse],
    label: str,
    years: list[int],
    by: list[str] | None,
    province: list[str] | None,
    line_of_business: list[str] | None,
    database_path: Path,
    chart_output: Path | None,
) -> None:
    """Validate options, run one underwriting-year tool, and print the response."""
    if not database_path.exists():
        raise typer.BadParameter(
            f"Database does not exist: {database_path}. Run 'init-data' first."
        )

    try:
        segments = [Dimension(value) for value in by or []]
        request = request_model(
            underwriting_years=years,
            dimensions=[
                *(d for d in segments if d != Dimension.UNDERWRITING_YEAR),
                Dimension.UNDERWRITING_YEAR,
            ],
            provinces=province,
            lines_of_business=line_of_business,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    raw_results = tool(database_path, request)

    response = build_response(
        question=(
            f"Show the {label} for underwriting years "
            f"{', '.join(str(year) for year in request.underwriting_years)}."
        ),
        request=request,
        raw_results=raw_results,
        database_path=database_path,
        dataset_version=settings.dataset_version,
    )

    if chart_output is not None and response.chart is not None and raw_results:
        generated_chart_path = generate_chart(
            raw_results=raw_results,
            metadata=response.chart,
            output_path=chart_output,
        )
        response.chart.output_path = str(generated_chart_path)

    typer.echo(response.model_dump_json(indent=2))


@app.command("severity")
def severity(
    years: YearOption,
    by: SegmentOption = None,
    province: ProvinceOption = None,
    line_of_business: LineOfBusinessOption = None,
    database_path: DatabasePathOption = settings.database_path,
    chart_output: ChartOutputOption = None,
) -> None:
    """Calculate average claim severity by underwriting year."""
    run_underwriting_year_analysis(
        request_model=SeverityRequest,
        tool=get_claim_severity,
        build_response=build_severity_response,
        label="average claim severity",
        years=years,
        by=by,
        province=province,
        line_of_business=line_of_business,
        database_path=database_path,
        chart_output=chart_output,
    )


@app.command("exposure-summary")
def exposure_summary(
    years: YearOption,
    by: SegmentOption = None,
    province: ProvinceOption = None,
    line_of_business: LineOfBusinessOption = None,
    database_path: DatabasePathOption = settings.database_path,
    chart_output: ChartOutputOption = None,
) -> None:
    """Summarize policies, exposure units, and premium by underwriting year."""
    run_underwriting_year_analysis(
        request_model=ExposureSummaryRequest,
        tool=get_exposure_summary,
        build_response=build_exposure_summary_response,
        label="exposure summary",
        years=years,
        by=by,
        province=province,
        line_of_business=line_of_business,
        database_path=database_path,
        chart_output=chart_output,
    )


@app.command("portfolio-quality-metrics")
def portfolio_quality_metrics(
    years: YearOption,
    by: SegmentOption = None,
    province: ProvinceOption = None,
    line_of_business: LineOfBusinessOption = None,
    database_path: DatabasePathOption = settings.database_path,
) -> None:
    """Calculate loss ratio, frequency, severity, premium and claim share."""
    run_underwriting_year_analysis(
        request_model=PortfolioQualityRequest,
        tool=get_portfolio_quality_metrics,
        build_response=build_portfolio_quality_response,
        label="portfolio quality metrics",
        years=years,
        by=by,
        province=province,
        line_of_business=line_of_business,
        database_path=database_path,
        chart_output=None,
    )


@app.command("ask")
def ask(
    question: QuestionArgument,
    database_path: DatabasePathOption = settings.database_path,
    chart_output: ChartOutputOption = None,
    router_name: RouterOption = "deterministic",
) -> None:
    """Answer a supported insurance portfolio analytics question."""
    agent = InsuranceDataAnalystAgent(
        database_path=database_path,
        dataset_version=settings.dataset_version,
        registry=build_default_tool_registry(),
        audit_writer=AuditWriter(
            output_directory=settings.audit_directory,
        ),
        router=build_router(router_name),
    )

    try:
        response = agent.answer(
            question=question,
            chart_output_path=chart_output,
        )

    except (
        FileNotFoundError,
        UnsupportedQuestionError,
    ) as error:
        raise typer.BadParameter(str(error)) from error

    typer.echo(response.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
