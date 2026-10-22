# Data Analyst Agent Evaluation Baseline

## Purpose

This document records the initial evaluation baseline for the **Insurance Data Analyst Agent**.

The baseline evaluates whether the application:

- Routes an analytical question to an explicitly authorized tool.
- Extracts and validates permitted analytical arguments.
- Executes deterministic SQLite and Python calculations.
- Produces a structured, auditable response.
- Generates a chart only through controlled Python code and approved metadata.
- Persists an audit artifact for both successful and failed runs.
- Falls back safely when an LLM provider is unavailable or returns invalid tool-selection output.

This is not a benchmark of actuarial adequacy, reserving accuracy, pricing adequacy, claims adjudication, or a production insurance portfolio. It is a project-specific quality baseline for the current synthetic dataset, tool contracts, routing rules, response schema, audit controls, and test fixtures.

## Evaluation Principles

An analytical-agent answer can fail at several layers. A valid JSON response alone does not establish a correct or safe analysis.

| Layer | Evaluation question |
|---|---|
| Dataset | Is the deterministic synthetic dataset created from the expected seed and schema? |
| Data access | Is the requested underwriting-year range available in the local database? |
| Routing | Does the question map to an authorized analytical tool? |
| Argument extraction | Are years, provinces, lines of business, and dimensions correctly identified? |
| Schema validation | Do selected tool names and arguments conform to Pydantic contracts? |
| Tool authorization | Does the registry execute only explicitly registered handlers? |
| Calculation | Does the tool apply the documented metric definition without join-induced duplication? |
| Response | Does the response include the question, tool call, validated arguments, raw results, explanation, chart metadata, and audit metadata? |
| Chart generation | Is the chart created by controlled Python code from returned data rather than generated code? |
| Audit persistence | Is a complete audit file written for success and failure outcomes? |
| LLM fallback | Does an unavailable or invalid provider response fall back to deterministic routing? |

The LLM is never trusted to calculate the metric, generate SQL, select an arbitrary function, or bypass Pydantic validation.

## Current V1 Scope

The current V1 supports one allow-listed analytical tool:

```text
get_loss_ratio_by_segment
```

The supported calculation is:

```text
paid_loss_ratio = total_paid_claim_amount / total_written_premium
```

The output may be segmented by:

- Province
- Line of business
- Underwriting year

The current supported province values are:

```text
QC, ON, BC, AB
```

The current supported line-of-business values are:

```text
commercial_property
commercial_auto
general_liability
```

## Evaluation Criteria

| Criterion | Description | V1 expectation |
|---|---|---:|
| Tool-selection validity | The selected tool conforms to the `ToolSelection` contract | 100% |
| Tool authorization | Only a tool registered in `ToolRegistry` can execute | 100% |
| Argument-schema validity | Tool arguments pass Pydantic validation | 100% |
| Province-filter validity | Province filters belong to the approved set | 100% |
| Line-of-business validity | Line-of-business filters belong to the approved set | 100% |
| Underwriting-year validity | Requested years exist in the local dataset | 100% |
| SQL safety | No user or LLM free-form SQL reaches SQLite | 100% |
| Calculation integrity | Premium is not duplicated for policies with multiple claims | 100% |
| Response-schema validity | Accepted responses conform to `AnalyticsResponse` | 100% |
| Audit persistence | One audit artifact is written per `agent.answer()` invocation | 100% |
| Failure auditing | Failed runs persist error type, message, and available execution context | 100% |
| Chart-file creation | A requested grouped-bar chart is a non-empty PNG file | 100% |
| Fallback behavior | Invalid or unavailable LLM output uses deterministic routing | 100% |
| Unsupported-question rejection | Unsupported questions execute no analytical tool | 100% |

For V1, schema validation, tool authorization, no-free-SQL behavior, calculation integrity, and audit persistence are hard requirements. A run that fails one of these controls is not considered an accepted analytical response.

## Baseline End-to-End Scenario

The initial manually verified end-to-end scenario is a loss-ratio analysis for commercial property in Quebec.

| Case ID | Scenario | Expected outcome | Status |
|---|---|---|---|
| `loss_ratio_quebec_commercial_property_2025` | Paid loss ratio for commercial property in Quebec in 2025 | Valid routing, validated filters, deterministic tool execution, JSON response, optional chart, and persisted audit | Baseline |

### Query

```text
Show the paid loss ratio for commercial property in Quebec for 2025.
```

### Expected tool selection

```json
{
  "tool_name": "get_loss_ratio_by_segment",
  "arguments": {
    "underwriting_years": [2025],
    "dimensions": [
      "province",
      "line_of_business",
      "underwriting_year"
    ],
    "provinces": ["QC"],
    "lines_of_business": ["commercial_property"]
  }
}
```

### Expected execution evidence

| Control | Expected evidence |
|---|---|
| Router output | `get_loss_ratio_by_segment` is selected |
| Province filter | `QC` |
| Line-of-business filter | `commercial_property` |
| Year filter | `2025` |
| Tool-call status | `success` |
| Raw results | Every row has `province = QC`, `line_of_business = commercial_property`, and `underwriting_year = 2025` |
| Metric definition | `paid_loss_ratio = paid_claim_amount / written_premium` |
| Audit status | `success` |
| Optional chart | Non-empty PNG file when `--chart-output` is supplied |

### Acceptance command

```bash
uv run insurance-data-analyst ask \
  "Show the paid loss ratio for commercial property in Quebec for 2025." \
  --chart-output output/charts/quebec-commercial-property-2025.png
```

The command must produce a structured response in standard output, a chart at the requested path, and an audit JSON file in `output/audits/`.

## Core Regression Scenarios

The evaluation suite must include the following classes of scenarios.

| Category | Example scenario | Required behavior |
|---|---|---|
| English routing | `Show loss ratio by region for the last three underwriting years.` | Select the loss-ratio tool and use the latest available years |
| French routing | `Afficher le ratio de sinistralité au Québec pour 2025.` | Recognize French wording and map Quebec to `QC` |
| Accent normalization | `Québec`, `sinistralité`, `propriété commerciale` | Normalize typography without changing analytical meaning |
| Explicit years | `Show loss ratio for 2024 and 2025.` | Use exactly `[2024, 2025]` |
| Relative years | `last three underwriting years` | Resolve from database metadata, not hard-coded values |
| Province filters | `Quebec and Alberta` | Extract `QC` and `AB` in deterministic order |
| Line-of-business filters | `commercial auto in Ontario` | Extract `commercial_auto` and `ON` |
| Unsupported analytical request | `Flag segments where claim severity exceeds 5000.` | Reject without tool execution |
| Threshold or alert | `Flag frequency increases above 20%.` | Reject: tools return metrics, not alerts |
| Empty input | Empty or whitespace-only question | Reject with a controlled error |
| Unavailable year | `Show loss ratio for 2021.` | Reject rather than silently replace the requested year |
| Missing database | Database path does not exist | Raise a controlled error and persist a failed audit |
| Unknown tool | Tool name absent from the registry | Reject with `ToolNotFoundError` |
| Invalid LLM JSON | Provider returns malformed or non-object JSON | Fall back to deterministic routing |
| Invalid LLM tool name | Provider requests arbitrary SQL or an unknown tool | Fall back to deterministic routing |
| Invalid LLM filters | Provider returns unsupported province or line of business | Fall back to deterministic routing |
| Multiple claims | One policy has multiple claims | Aggregate claims before joining to prevent premium duplication |
| Empty chart data | Chart requested for no returned results | Reject chart generation safely and persist failure context |

## Tool-Selection Evaluation Dataset

The versioned router evaluation dataset lives in:

```text
tests/evaluations/cases.json
```

Each case should define a user question and one expected outcome: either an authorized tool-selection object or a controlled error.

Suggested fixture format for a successful route:

```json
{
  "id": "english-quebec-commercial-property",
  "question": "Show the paid loss ratio for commercial property in Quebec for 2025.",
  "expected_tool_name": "get_loss_ratio_by_segment",
  "expected_arguments": {
    "underwriting_years": [2025],
    "dimensions": [
      "province",
      "line_of_business",
      "underwriting_year"
    ],
    "provinces": ["QC"],
    "lines_of_business": ["commercial_property"]
  }
}
```

Suggested fixture format for a rejection:

```json
{
  "id": "unsupported-severity-threshold",
  "question": "Flag segments where claim severity exceeds 5000.",
  "expected_error": "UnsupportedQuestionError",
  "expected_error_message": "Unsupported question"
}
```

The initial V1 target is 15-20 curated router and tool-execution cases. The suite currently holds 25 router cases: 15 accepted (loss ratio, claim frequency, severity, exposure summary, and portfolio quality metrics, in English and French) and 10 rejected (frequency and severity thresholds, unavailable years, single-year trends, mixed analyses, empty question).

## Calculation-Integrity Tests

The calculation layer must be tested independently from routing and response generation.

### Multiple-claims protection

A policy with written premium of CAD 1,000 and two paid claims of CAD 200 and CAD 300 must return:

```text
written_premium = 1,000
paid_claim_amount = 500
paid_loss_ratio = 0.50
```

It must not return a written premium of CAD 2,000 after a one-to-many join with claims.

### Zero-claim segments

A segment with positive written premium and no paid claims must return:

```text
paid_claim_amount = 0
paid_loss_ratio = 0
```

### Deterministic synthetic data

The generator must use an explicit seed. The same seed, generation parameters, and source code version must produce the same analytical values.

## Chart Evaluation

Chart generation is a controlled presentation layer, not an LLM-generated artifact.

The V1 chart tests verify:

- The requested chart type is `grouped_bar`.
- The output file exists.
- The output file has a `.png` extension.
- The output file is non-empty.
- Empty analytical results do not produce a misleading chart.
- Unsupported chart types are rejected.
- Loss-ratio charts use a percentage-formatted y-axis.

The chart itself does not replace the structured raw results or the audit record.

## Audit Evaluation

Each `agent.answer()` call must persist exactly one audit artifact unless the audit storage itself is unavailable.

### Required successful-audit fields

```text
run_id
timestamp_utc
agent_version
dataset_version
database_path
question
status
tool_calls
raw_results
final_response
```

### Required failed-audit fields

```text
run_id
timestamp_utc
agent_version
dataset_version
database_path
question
status
error.error_type
error.message
```

When a tool was selected before failure, the audit must also preserve its validated arguments and failure status.

## LLM Router Evaluation

The LLM-assisted router is evaluated separately from provider quality. The goal is to verify controls at the provider boundary.

| Provider outcome | Expected system behavior |
|---|---|
| Valid JSON with allowed tool and valid arguments | Use the validated LLM selection |
| Empty provider response | Use deterministic fallback |
| Invalid JSON | Use deterministic fallback |
| Unknown tool name | Use deterministic fallback |
| Unsupported province | Use deterministic fallback |
| Unsupported line of business | Use deterministic fallback |
| Unavailable underwriting year | Use deterministic fallback |
| Unsupported dimensions | Use deterministic fallback |
| Provider exception | Use deterministic fallback |

The `FakeLLMClient` is the default evaluation client. It allows tests to cover valid responses, malformed outputs, and provider failures without network access, API keys, cost, or nondeterminism.

## Metrics

The V1 evaluation suite is primarily assertion-based. The following metrics can be reported from the versioned case set.

| Metric | Definition | V1 target |
|---|---|---:|
| Router accuracy | Share of supported questions mapped to the expected tool and arguments | 100% on curated cases |
| Controlled-rejection accuracy | Share of unsupported questions rejected as expected | 100% on curated cases |
| Tool-authorization rate | Runs invoking only registered tools | 100% |
| Argument-validation rate | Executed tool calls with valid Pydantic arguments | 100% |
| Calculation-integrity pass rate | Deterministic calculation tests passing | 100% |
| Audit-persistence rate | Invocations producing an audit artifact | 100% |
| Failed-run audit rate | Controlled failures producing a failed audit artifact | 100% |
| Chart-generation pass rate | Requested valid charts created as non-empty files | 100% |
| Fallback success rate | Invalid or unavailable LLM calls handled by deterministic fallback | 100% |

## Regression Policy

Run the full test suite after any material change to:

- Synthetic data schema or generation logic.
- Random seed, claim-frequency assumptions, or severity assumptions.
- SQL templates or aggregation logic.
- Pydantic models and validation rules.
- Allowed province, line-of-business, or dimension values.
- Router aliases, normalization rules, or year-extraction behavior.
- Tool registration and dispatch logic.
- Chart metadata, rendering behavior, or supported chart types.
- Audit schema, file naming, or storage behavior.
- LLM prompt wording, provider adapter, model configuration, or fallback policy.

Run:

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run pytest -v
uv run pytest --cov=insurance_data_analyst_agent --cov-report=term-missing --cov-fail-under=80
```

GitHub Actions must run the same quality and test checks for every push and pull request.

## Current Limitations

- V1 supports only paid loss-ratio analysis.
- Written premium is used rather than earned premium.
- Paid claim amount is used rather than incurred loss, case reserves, or ultimate loss.
- The portfolio is synthetic and not representative of a production insurer.
- Accident-year, calendar-year, development-triangle, and reserving views are out of scope.
- The deterministic router recognizes a deliberately limited English and French vocabulary.
- The LLM router is an assistive routing layer, not a calculation engine.
- Tests for real external provider calls should be isolated from deterministic CI tests.

## Next Evaluation Steps

1. Done: `get_claim_frequency_trend` and its frequency-specific routing and calculation cases.
2. Add a year-over-year increase threshold evaluation, including the 20% frequency-increase scenario.
3. Done: severity, exposure-summary, and portfolio-quality tools with independent metric tests.
4. Add a generic response-builder registry and evaluate multi-tool response handling.
5. Record per-run latency and provider-fallback telemetry without exposing credentials or sensitive data.
6. Add a second provider adapter and run the same provider-boundary control suite.
7. Compare prompt and provider variants only against the fixed, versioned evaluation dataset.
