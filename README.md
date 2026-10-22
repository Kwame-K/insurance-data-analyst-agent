# Insurance Data Analyst Agent

[![CI](https://github.com/Kwame-K/insurance-data-analyst-agent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Kwame-K/insurance-data-analyst-agent/actions/workflows/ci.yml)

A controlled, deterministic, and auditable agent for insurance portfolio analytics. It accepts selected analytical questions in English or French, routes each request to an allow-listed analytical tool, runs fixed SQL and Python calculations on PostgreSQL or SQLite, optionally produces a chart, and persists a JSON audit artifact for every successful or failed run. It is exposed through a CLI and a versioned REST API.

This repository is **Project 2** in a five-project insurance agentic AI portfolio. The language model never writes SQL and never calculates a metric: it only helps to choose one of five registered tools, and its output is validated like any untrusted input.

> **Scope note:** this is a portfolio and learning project. All data is synthetic. The metrics are paid-basis portfolio indicators, not reserving, pricing, or underwriting results, and must not be used for real business decisions.

## Highlights

- Five allow-listed analytical tools: loss ratio, claim frequency trend, claim severity, exposure summary, and portfolio quality metrics.
- Natural-language requests in English and French, through a deterministic router or an LLM router.
- Provider-agnostic `LLMClient` with a Gemini, Groq, then deterministic fallback chain, and a `FakeLLMClient` for offline tests.
- Strict Pydantic validation of tool names and arguments; no free-form SQL from users or LLMs.
- Deterministic SQL and Python calculations on PostgreSQL (Alembic migrations) or SQLite (local development and tests).
- Versioned REST API (`/v1`): one natural-language endpoint and one typed endpoint per tool.
- CLI with one command per tool and an `ask` command for natural-language questions.
- MCP server over stdio exposing the five tools as read-only, typed MCP tools that share the agent, audit writer, and response contract with the REST API.
- Correlation and request identifiers propagated through logs, headers, and responses.
- Uniform error envelope that never exposes internal details.
- Optional Matplotlib charts (grouped bars and lines) for the tools that support them.
- Persistent JSON audit artifact for every successful or failed run.
- Curated routing evaluation dataset, coverage gate, Ruff, mypy, and GitHub Actions with a PostgreSQL service.
- Docker image and Compose service on the Insurance Agentic Platform.

## Analytical Tools

| Tool | What it returns | Basis | REST endpoint | CLI command | Chart |
|---|---|---|---|---|---|
| `get_loss_ratio_by_segment` | Paid loss ratio by province, line of business, and underwriting year | Underwriting year | `POST /v1/loss-ratio` | `loss-ratio` | Grouped bars |
| `get_claim_frequency_trend` | Claims per exposure unit and year-over-year change (at least two years) | Calendar year | `POST /v1/claim-frequency` | `claim-frequency` | Lines |
| `get_claim_severity` | Average paid amount per claim | Underwriting year | `POST /v1/severity` | `severity` | Grouped bars |
| `get_exposure_summary` | Policy count, exposure units, written premium, average exposure per policy | Underwriting year | `POST /v1/exposure-summary` | `exposure-summary` | Grouped bars |
| `get_portfolio_quality_metrics` | Loss ratio, frequency, severity, premium per exposure unit, and share of policies with claims together | Underwriting year | `POST /v1/portfolio-quality-metrics` | `portfolio-quality-metrics` | None |

The underwriting-year tools include the claims and exposure of the policies underwritten in the selected years, whatever the claim or exposure year. The claim frequency trend uses calendar years, so its figures are not directly comparable with the cohort `claim_frequency` of the portfolio quality metrics.

Natural-language questions go through `POST /v1/analyze` or the `ask` command. A question that names several metrics is routed to the portfolio quality metrics; two unrelated analyses in one question are rejected.

Supported examples:

```text
Show the loss ratio by region and line of business for the last three underwriting years.
Show the paid loss ratio for commercial property in Quebec for 2025.
Afficher le ratio de sinistralité pour la propriété commerciale au Québec pour 2024 et 2025.
Show the claim frequency by province for 2024 and 2025.
What is the average claim severity by province?
Afficher la sévérité des sinistres pour la propriété commerciale au Québec pour 2025.
Show the exposure summary by line of business for 2024 and 2025.
Show the portfolio quality metrics by province for the last three underwriting years.
Afficher les métriques de qualité du portefeuille pour l'Alberta en 2025.
```

Unsupported examples are rejected explicitly, without executing any tool:

```text
Flag segments where claim frequency increased by more than 20% year over year.
Flag segments where claim severity exceeds 5000.
Show severity and the exposure summary.
Show the claim frequency for 2025.
```

The dataset exposes the provinces `QC`, `ON`, `BC`, and `AB`, and underwriting years 2023 to 2025.

## Architecture

```text
User question or typed request
    ↓
CLI (ask and one command per tool), REST API (POST /v1/analyze and one typed endpoint per tool), or MCP server (one typed tool each)
    ↓
InsuranceDataAnalystAgent
    ↓
DeterministicRouter or LLMRouter (Gemini → Groq → deterministic)
    ↓
ToolSelection validated by Pydantic
    ↓
ToolRegistry (five allow-listed tools)
    ↓
SQL query (PostgreSQL or SQLite) and deterministic calculation
    ↓
AnalyticsResponse
    ↓
Optional Matplotlib chart
    ↓
Persistent JSON audit artifact
```

Typed endpoints, MCP tools, and CLI commands skip the router: a fixed router selects the tool, and the same agent, registry, audit writer, and response contract are used. For a detailed description of components, sequence diagrams, evaluation flow, and extensibility, see [System Architecture](docs/architecture/system-architecture.md).

## Installation

### Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/)
- Git
- PostgreSQL 17, optional: SQLite is the local default
- A Gemini or Groq API key, optional: without keys the deterministic router is used

### Setup

```bash
git clone https://github.com/Kwame-K/insurance-data-analyst-agent.git
cd insurance-data-analyst-agent
uv sync
cp .env.example .env
```

Do not commit `.env`. Commit `.env.example` only.

### Configuration

```dotenv
DATABASE_PATH=data/insurance_portfolio.db   # local SQLite file
AUDIT_DIRECTORY=output/audits
DATASET_VERSION=synthetic-v1

GEMINI_API_KEY=
GEMINI_MODEL=
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b

LOG_LEVEL=INFO

# Optional. When set, PostgreSQL replaces the local SQLite file.
DATABASE_URL=
DATABASE_ECHO=false
```

The chart directory defaults to `output/charts`. Provider keys are read as secrets and never logged. Percent-encode special characters of a password inside `DATABASE_URL` (for example `%` as `%25`).

### Create the synthetic portfolio

SQLite:

```bash
uv run insurance-data-analyst init-data --seed 42
```

PostgreSQL (migrations, then seeded data):

```bash
DATABASE_URL=postgresql+psycopg://analyst_app:password@localhost:5432/analyst \
  uv run insurance-data-analyst init-db --seed 42
```

## Usage

### CLI

Every command prints a JSON `AnalyticsResponse` containing the question, the tool call, the raw results, the calculation definition, and the audit metadata. Repeat `-y`, `--by`, `--province`, and `--lob` for several values.

```bash
uv run insurance-data-analyst loss-ratio -y 2024 -y 2025 --province QC --lob commercial_property
uv run insurance-data-analyst claim-frequency -y 2024 -y 2025 --by province --chart-output output/charts/frequency.png
uv run insurance-data-analyst severity -y 2024 -y 2025 --by province --chart-output output/charts/severity.png
uv run insurance-data-analyst exposure-summary -y 2025 --by line_of_business
uv run insurance-data-analyst portfolio-quality-metrics -y 2024 -y 2025 --by province
```

Natural-language questions, deterministic by default or with the Groq router:

```bash
uv run insurance-data-analyst ask "Show the claim frequency by province for 2024 and 2025."
uv run insurance-data-analyst ask "Afficher le résumé de l'exposition par province pour 2025." --router groq
```

### Run the API

```bash
uv run uvicorn insurance_data_analyst_agent.api.main:app --reload --port 8003
```

Open the interactive OpenAPI interface at `http://127.0.0.1:8003/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service liveness and agent version |
| POST | `/v1/analyze` | Natural-language question, routed to one tool |
| POST | `/v1/loss-ratio` | Typed call to `get_loss_ratio_by_segment` |
| POST | `/v1/claim-frequency` | Typed call to `get_claim_frequency_trend` |
| POST | `/v1/severity` | Typed call to `get_claim_severity` |
| POST | `/v1/exposure-summary` | Typed call to `get_exposure_summary` |
| POST | `/v1/portfolio-quality-metrics` | Typed call to `get_portfolio_quality_metrics` |

```bash
curl -s http://127.0.0.1:8003/health
```

```bash
curl -s -X POST http://127.0.0.1:8003/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{"question": "Show the claim frequency by province for 2024 and 2025.", "request_id": "demo-1"}'
```

```bash
curl -s -X POST http://127.0.0.1:8003/v1/claim-frequency \
  -H 'Content-Type: application/json' \
  -d '{"arguments": {"years": [2024, 2025], "dimensions": ["province"]}, "include_chart": true}'
```

Success envelope:

```json
{
  "api_version": "v1",
  "correlation_id": "...",
  "request_id": "demo-1",
  "status": "success",
  "routing_provider": "deterministic",
  "data": { "...": "AnalyticsResponse" }
}
```

`routing_provider` is `deterministic`, `gemini`, or `groq` for `/v1/analyze`, and `direct` for the typed endpoints. A `request_id` in the body wins over the `X-Request-ID` header; an invalid `X-Correlation-ID` is replaced by a generated one. With `include_chart`, the PNG is written to `output/charts/<correlation_id>.png` (not supported by `/v1/portfolio-quality-metrics`).

Error envelope. The codes are `validation_error` and `unsupported_question` (HTTP 422), `data_unavailable` (503), and `internal_error` (500):

```json
{
  "api_version": "v1",
  "correlation_id": "...",
  "request_id": null,
  "status": "error",
  "error": { "code": "validation_error", "message": "...", "details": [] }
}
```

The API has no authentication and is intended for a trusted internal network.

## MCP Server

The five tools are also available as a [Model Context Protocol](https://modelcontextprotocol.io) server over stdio, so MCP clients and agents (for example the Underwriting Agent, Claude Desktop, or Cursor) can call them directly.

Start the server:

```bash
uv run insurance-data-analyst-mcp
```

Inspect it interactively:

```bash
npx @modelcontextprotocol/inspector uv run insurance-data-analyst-mcp
```

| MCP tool | Required parameter | Optional parameters |
|---|---|---|
| `get_loss_ratio_by_segment` | `underwriting_years` | `dimensions`, `provinces`, `lines_of_business` |
| `get_claim_frequency_trend` | `years` (at least two) | `dimensions`, `provinces`, `lines_of_business` |
| `get_claim_severity` | `underwriting_years` | `dimensions`, `provinces`, `lines_of_business` |
| `get_exposure_summary` | `underwriting_years` | `dimensions`, `provinces`, `lines_of_business` |
| `get_portfolio_quality_metrics` | `underwriting_years` | `dimensions`, `provinces`, `lines_of_business` |

The tools are annotated as read-only, non-destructive, and idempotent. They accept the same Pydantic contract as the typed REST endpoints and return the same `v1` success envelope, with `routing_provider` set to `direct`. There is no natural-language tool: the client selects the tool, the server never routes a question.

Failures are returned as MCP tool errors with a stable prefix and a generic message: `VALIDATION_ERROR` (invalid or unsupported arguments), `DATA_UNAVAILABLE` (database unreachable), and `INTERNAL_ERROR`. Database URLs, credentials, and stack traces are never returned. Every call writes the same audit artifact as the other transports.

Example client configuration (Claude Desktop, Cursor, or any stdio MCP client):

```json
{
  "mcpServers": {
    "insurance-data-analyst-agent": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/insurance-data-analyst-agent",
        "run",
        "insurance-data-analyst-mcp"
      ]
    }
  }
}
```

The database and provider settings are read from the project `.env` file. Logs are written to stderr because stdout carries the stdio protocol. Charts are not available through MCP.

## Safety model

### Controlled tool selection

The agent can execute only tools explicitly registered in `ToolRegistry`.

The current allow-list contains:

```text
get_loss_ratio_by_segment
get_claim_frequency_trend
get_claim_severity
get_exposure_summary
get_portfolio_quality_metrics
```

A request cannot select an arbitrary Python function, shell command, file path, database connection, or SQL statement.

### No free-form SQL

The user and the LLM never submit SQL. The implementation uses fixed SQL templates with:

- Allow-listed grouping dimensions mapped to fixed column names
- Bound parameters for every value filter
- Validated years (underwriting years, or calendar years for claim frequency)
- Validated province filters
- Validated line-of-business filters

### Deterministic calculations

The LLM does not calculate insurance metrics. SQL and Python perform all aggregations and metric calculations.

The loss-ratio metric is:

```text
paid_loss_ratio = total_paid_claim_amount / total_written_premium
```

The claim-frequency metric is:

```text
claim_frequency = claim_count / exposure_units  (by calendar year)
year_over_year_change = frequency / previous_requested_year_frequency - 1
```

Exposure and claims are aggregated by policy and year before joining, so a policy with several exposure rows or several claims never duplicates the other side. Claims are counted only on policies with exposure in the same year. Divisions are forced to decimal arithmetic so SQLite does not truncate integer sums.

The cohort metrics are:

```text
average_severity = paid_claim_amount / claim_count
average_exposure_per_policy = exposure_units / policy_count
premium_per_exposure_unit = written_premium / exposure_units
share_of_policies_with_claims = policies_with_claims / policy_count
```

Claims and exposure are aggregated by policy before joining, so no policy contributes its premium or exposure more than once. Severity is null for a segment without claims.

The claims table is aggregated by policy before joining policies, preventing written-premium duplication when a policy has multiple claims.

### LLM fallback

The routers treat LLM output as untrusted input.

```text
Gemini JSON response ── error or invalid ──► Groq JSON response ── error or invalid ──► deterministic router
    ↓                                              ↓
ToolSelection.model_validate(...)             ToolSelection.model_validate(...)
    ↓
Dataset constraint validation
    ↓
Valid selection → execute registered tool
```

The deterministic router is used when no provider is configured, when every provider is unavailable, or when the output contains invalid JSON, an unknown tool, invalid filters, invalid dimensions, or underwriting years unavailable in the dataset.

### Safe errors and secrets

- Every error uses one versioned envelope with the `correlation_id`.
- Unexpected errors return a generic message; details stay in the server logs.
- Audit records and API responses describe the database as `postgresql:<name>` or the SQLite file path, never as a URL, host, user, or password.
- The identifiers received in headers are validated against a strict pattern before they are used in logs or file names.

## Persistence and Audit Trail

The portfolio uses three tables, `policies`, `exposure`, and `claims`, declared with SQLAlchemy and created by Alembic migrations on PostgreSQL. A deterministic seed generates the same rows for PostgreSQL and SQLite, and a single data-access layer accepts either a SQLite path or an SQLAlchemy engine.

Every run, successful or not, writes a JSON audit artifact to `output/audits/` with the run identifier, a UTC timestamp, the agent and dataset versions, the question, the status, the tool calls, the raw results, the final response, and the error when the run failed. The database is described as `postgresql:<name>` or the SQLite file path, never as a URL.

## Docker

The image runs as a non-root user and serves the API on port `8003` with a `/health` check.

```bash
docker build -t insurance-data-analyst-agent .
```

The service is orchestrated by the [`insurance-agentic-platform`](../insurance-agentic-platform) Docker Compose project as `data-analyst-agent`, with PostgreSQL, the `analyst_output` volume for audits and charts, and the Gemini and Groq settings passed as environment variables.

## Evaluation

`tests/evaluations/cases.json` holds 25 curated routing cases in English and French: 15 accepted questions across the five tools and 10 rejections (thresholds and alerts, unavailable years, single-year trends, mixed analyses, empty questions). They run offline against the deterministic router, and the same dataset is the baseline for LLM router comparisons. See [Evaluation Baseline](docs/architecture/evaluation-baseline.md).

## Quality Checks

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy .
uv run pytest
uv run pytest --cov=insurance_data_analyst_agent --cov-report=term-missing --cov-fail-under=80
```

PostgreSQL parity tests compare PostgreSQL and SQLite results for every tool. They are skipped unless `TEST_DATABASE_URL` points to a disposable database:

```bash
TEST_DATABASE_URL=postgresql+psycopg://analyst_app:ci_password@localhost:5432/analyst_test uv run pytest tests/test_postgres.py
```

End-to-end tests call the running platform over HTTP (default `http://127.0.0.1:8003`, override with `E2E_API_URL`) and are skipped unless selected. They check contracts and cross-endpoint consistency, not exact figures:

```bash
# in insurance-agentic-platform
docker compose up --build -d
# in this project
uv run pytest -m e2e -rs -v
```

GitHub Actions runs formatting, linting, mypy, the test suite against a PostgreSQL 17 service, and the coverage gate on every push and pull request.

## Project Structure

```text
insurance-data-analyst-agent/
├── .github/workflows/ci.yml
├── data/                          # local SQLite portfolio
├── docs/
│   ├── architecture/
│   │   ├── evaluation-baseline.md
│   │   └── system-architecture.md
│   └── roadmap.md
├── output/
│   ├── audits/                    # JSON audit artifacts
│   └── charts/                    # generated PNG charts
├── src/insurance_data_analyst_agent/
│   ├── api/                       # app factory, routes, schemas, errors, middleware
│   ├── infrastructure/persistence/  # engine, data access, ORM models, Alembic migrations
│   ├── llm/                       # LLMClient, Gemini, Groq, fallback, fake, prompts
│   ├── mcp_server/                # stdio MCP server, five read-only tools
│   ├── models/                    # analytics, routing, and audit contracts
│   ├── services/                  # agent, routers, response builders, audit writer, shared direct call
│   ├── synthetic_data/            # seeded generator and loader
│   ├── tools/                     # registry and the five analytical tools
│   ├── charts.py
│   ├── cli.py
│   └── config.py
├── tests/                         # unit, API, CLI, PostgreSQL, and evaluation tests
├── Dockerfile
└── pyproject.toml
```

## Limitations

- The loss ratio is paid claims over written premium: not earned premium, not incurred losses, and IBNR is not covered.
- Claim frequency counts claims by `claim_year` on policies with exposure in the same year; reporting lags are not adjusted.
- Routing treats the available underwriting years as the available exposure years, which holds for the synthetic data but not necessarily for a real portfolio.
- Thresholds and alerts are rejected: the tools return metrics, not decisions.
- The API has no authentication, and the MCP server is stdio only and meant for a local trusted client.
- The portfolio quality metrics have no chart yet.
- Data is synthetic and the dataset has four provinces and three lines of business.

## Position in the Insurance Agentic Platform

| Project | Repository | Role |
|---|---|---|
| 1 | insurance-submission-extractor | Structured submission intake and validation |
| 2 | insurance-data-analyst-agent (this repo) | Controlled portfolio analytics with five deterministic tools |
| 3 | insurance-rag-assistant | Insurance Knowledge Agent with grounded, cited retrieval |
| 4 | underwriting-agent | Deterministic underwriting rules, risk scoring, pricing, and evidence retrieval |
| — | insurance-agentic-platform | Docker Compose orchestration layer for the running services |

## Roadmap

- [x] Versioned FastAPI API with correlation and request identifiers
- [x] Gemini, Groq, then deterministic routing with validation of LLM output
- [x] PostgreSQL persistence with Alembic migrations, SQLite kept for local use
- [x] Docker image and platform Compose service
- [x] Claim frequency, severity, exposure summary, and portfolio quality tools
- [x] Route-rule table and 25-case evaluation dataset
- [x] PostgreSQL parity tests and mypy in CI
- [x] MCP server (stdio) sharing the direct-call service with the REST API
- [ ] Earned premium and incurred-loss bases, with a `basis` field
- [ ] Chart for the portfolio quality metrics
- [ ] Portfolio context for the Underwriting Agent (Project 4) through MCP or HTTP
- [ ] API authentication

## Recommended Technology Upgrades

| Area | Current | Recommended | Benefit |
|---|---|---|---|
| Tool protocol | REST, CLI, and MCP over stdio | Streamable HTTP MCP transport behind the platform gateway, with authentication | MCP use by remote clients and services, not only local processes |
| Observability | Correlation ids and JSON logs | Langfuse or OpenTelemetry spans around routing, SQL, and chart generation | Latency and fallback visibility per run |
| Audit store | JSON files | PostgreSQL table keyed by `correlation_id` | Cross-project analytics on decisions |
| Security | No authentication | API key or OAuth2 at the platform gateway | Safe exposure beyond a trusted network |
| Calculation basis | Paid over written premium | Earned premium and incurred losses with explicit `basis` | Metrics closer to actuarial practice |

## Improvements and Next Steps

1. Connect the Underwriting Agent (Project 4) to the MCP server or the REST API for portfolio context.
2. Add earned premium and incurred losses: policy dates, claim reserves, an Alembic migration, a `basis` field on the relevant tools, and parity tests.
3. Add a chart for the portfolio quality metrics once the measure to plot is chosen.
4. Instrument `agent.answer()` with tracing for router mode, fallback events, and latency.
5. Add a Streamable HTTP transport for the MCP server once authentication exists.

## Agentic AI Best Practices Applied Here

- **Closed tool allow-list:** the agent can run only registered tools, and the MCP server exposes exactly those five as read-only tools; a request cannot select a function, a file path, a shell command, or a SQL statement.
- **LLM as router, not calculator:** the model selects a tool and arguments; SQL and Python compute every metric.
- **Untrusted model output:** every LLM selection is validated by Pydantic and against the dataset constraints, then falls back to the next provider and finally to the deterministic router.
- **Explicit rejection over guessing:** ambiguous, mixed, threshold, and unavailable-year questions are rejected with a controlled message.
- **Traceability:** each response carries its calculation definition, tool call, and dataset version, and each run writes an audit artifact.
- **Evaluation before change:** routing behavior is protected by a curated dataset, calculation-integrity tests, and PostgreSQL parity tests.
- **Safe failure:** one error envelope, generic messages for unexpected errors, and no credentials in logs, audits, or responses.
