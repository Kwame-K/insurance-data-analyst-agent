from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

import typer
from sqlalchemy.engine import make_url

from insurance_data_analyst_agent.config import settings
from insurance_data_analyst_agent.infrastructure.persistence.database import (
    create_database_engine,
    run_migrations,
)
from insurance_data_analyst_agent.llm.groq_client import (
    GroqLLMClient,
)
from insurance_data_analyst_agent.models.analytics import (
    Dimension,
    LossRatioRequest,
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
    build_loss_ratio_response,
)
from insurance_data_analyst_agent.services.router import (
    UnsupportedQuestionError,
    route_question,
)
from insurance_data_analyst_agent.synthetic_data.generator import (
    create_synthetic_database,
)
from insurance_data_analyst_agent.synthetic_data.loader import load_synthetic_data
from insurance_data_analyst_agent.tools.loss_ratio import (
    get_loss_ratio_by_segment,
)
from insurance_data_analyst_agent.tools.registry import (
    build_default_tool_registry,
)

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
    years: YearOption = ...,
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
