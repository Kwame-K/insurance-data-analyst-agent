# Roadmap — Insurance Data Analyst Agent

## Decisions

- Architecture unchanged: tools / services / models / llm / database stay as is. New code is added next to them.
- LLM routing chain: Gemini first, then Groq, then the deterministic router (final fallback).
- API first on local SQLite, then PostgreSQL (Phase B), then Docker and platform compose.
- Dev guidance: the user types the code himself; the assistant provides copy-paste snippets.
- Core rule kept: no free SQL, only authorized tools.
- Postgres/Alembic: escape `%` in URLs with an encoded password (bug met in Project 4).

## V1 — Structured application (current scope)

- [x] V1-1 Dependencies, settings (Gemini/Groq keys, DB URL), logging with correlation_id
- [x] V1-2 API Pydantic models (request, response, error) and exception handlers
- [x] V1-3 Gemini client, fallback chain (Gemini -> Groq -> deterministic)
- [x] V1-4 FastAPI routes: GET /health, POST /v1/analyze, POST /v1/loss-ratio
- [x] V1-5 Unit and integration tests (FakeLLMClient, offline, SQLite)
- [x] V1-6 Phase B: PostgreSQL (engine injected, role/db analyst_app), Alembic, `%` escaping, SQLite kept for tests
- [x] V1-7 Dockerfile, .dockerignore (non-root), service in platform compose.yaml, volumes (output/audits, output/charts), healthcheck
- [ ] V1-8 README: installation, configuration, API usage, limitations (no authentication)

## After V1 — original 8-step plan (to continue)

1. Versioned FastAPI API (done in V1, extend with consumer-provided request ids if missing)
2. MCP server (stdio) is done: five typed read-only tools (`insurance-data-analyst-mcp`), a `services/direct_call.py` shared with the REST API, the same `v1` envelope, stable error codes and an audit artifact per call. Still open: Streamable HTTP transport (needs authentication) and a platform e2e test
3. Docker and platform (finish whatever V1-7 leaves open)
4. Database (finish whatever V1-6 leaves open)
5. Analytical capabilities: `get_claim_frequency_trend`, `get_claim_severity`, `get_exposure_summary` and `get_portfolio_quality_metrics` are done (tool, registry, response, chart, routing, REST endpoint, CLI command, tests). Still open: earned premium instead of written premium; incurred losses (keep paid/written as an option, add a `basis` field)
6. Tests: MCP contract test (tool list, annotations) and the HTTP e2e tests marked `e2e` (`tests/e2e/`, platform only) are done; a non-regression test per new tool stays the rule
7. Underwriting agent (Project 4): HTTP client to Project 2, tolerated failure, degraded status, loss ratio of segment (province, line, year) as decision context, never an automatic rule
8. Documentation: README sections API/MCP/Docker/configuration, platform README entry, task lists, documented limits

## Known limitations

- Loss ratio is paid claims over written premium (not earned premium, not incurred losses); IBNR not covered.
- No authentication on the API.
- Five tools: loss ratio, claim frequency trend, claim severity, exposure summary, and portfolio quality metrics.
- Severity, exposure summary, and portfolio quality metrics are on an underwriting-year (cohort) basis, while the claim frequency trend is on calendar years; the two frequencies are not directly comparable.
- Claim frequency counts claims by `claim_year` on policies with exposure in the same year; reporting lags and late-reported claims are not adjusted.
- Routing treats the available underwriting years as the available exposure years; this holds for the synthetic data but is not guaranteed for real portfolios.
- Thresholds and alerts are rejected, as are questions that mix unrelated analyses; a question naming several metrics is routed to the portfolio quality metrics.
