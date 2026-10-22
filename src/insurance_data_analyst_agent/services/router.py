from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from insurance_data_analyst_agent.models.analytics import (
    ClaimFrequencyRequest,
    Dimension,
    ExposureSummaryRequest,
    LossRatioRequest,
    PortfolioQualityRequest,
    SeverityRequest,
    UnderwritingYearRequest,
)
from insurance_data_analyst_agent.models.routing import (
    CLAIM_FREQUENCY_TOOL,
    EXPOSURE_SUMMARY_TOOL,
    LOSS_RATIO_TOOL,
    PORTFOLIO_QUALITY_TOOL,
    SEVERITY_TOOL,
    ToolArguments,
    ToolName,
    ToolSelection,
    selection_for,
)


class UnsupportedQuestionError(ValueError):
    """Raised when a question cannot be mapped to an allowed tool."""


PROVINCE_ALIASES = {
    "quebec": "QC",
    "qc": "QC",
    "ontario": "ON",
    "british columbia": "BC",
    "colombie britannique": "BC",
    "alberta": "AB",
}

LINE_OF_BUSINESS_ALIASES = {
    "commercial property": "commercial_property",
    "propriete commerciale": "commercial_property",
    "commercial auto": "commercial_auto",
    "automobile commerciale": "commercial_auto",
    "general liability": "general_liability",
    "responsabilite civile generale": "general_liability",
}


def normalize_text(text: str) -> str:
    """Normalize whitespace, case, and French accents."""
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )

    return " ".join(without_accents.lower().replace("’", "'").split())


def extract_provinces(question: str) -> list[str] | None:
    """Extract recognized province filters from normalized text."""
    matched_provinces = [
        province_code
        for alias, province_code in PROVINCE_ALIASES.items()
        if re.search(rf"\b{re.escape(alias)}\b", question)
    ]

    unique_provinces = list(dict.fromkeys(matched_provinces))
    return unique_provinces or None


def extract_lines_of_business(question: str) -> list[str] | None:
    """Extract recognized line-of-business filters from normalized text."""
    matched_lines_of_business = [
        line_of_business
        for alias, line_of_business in LINE_OF_BUSINESS_ALIASES.items()
        if alias in question
    ]

    unique_lines_of_business = list(dict.fromkeys(matched_lines_of_business))
    return unique_lines_of_business or None


def extract_underwriting_years(
    question: str,
    available_years: list[int],
) -> list[int]:
    """Extract explicit years or resolve the last three available years."""
    requested_years = sorted(
        {int(year) for year in re.findall(r"\b20\d{2}\b", question)}
    )

    if requested_years:
        unavailable_years = [
            year for year in requested_years if year not in available_years
        ]

        if unavailable_years:
            unavailable_years_text = ", ".join(str(year) for year in unavailable_years)
            raise UnsupportedQuestionError(
                "Requested underwriting years are not available: "
                f"{unavailable_years_text}."
            )

        return requested_years

    requests_last_three_years = any(
        phrase in question
        for phrase in (
            "last three underwriting years",
            "last 3 underwriting years",
            "three latest underwriting years",
            "3 latest underwriting years",
            "trois dernieres annees de souscription",
            "3 dernieres annees de souscription",
        )
    )

    if requests_last_three_years:
        return available_years[-3:]

    return available_years[-3:]


LOSS_RATIO_PHRASES = (
    "loss ratio",
    "paid loss ratio",
    "ratio de sinistralite",
)

CLAIM_FREQUENCY_PHRASES = (
    "claim frequency",
    "claims frequency",
    "frequency of claims",
    "frequence des sinistres",
    "frequence de sinistres",
    "frequence de sinistralite",
)

SEVERITY_PHRASES = ("severity", "severite")

EXPOSURE_SUMMARY_PHRASES = (
    "exposure summary",
    "summary of exposure",
    "total exposure",
    "resume de l'exposition",
    "resume d'exposition",
    "exposition totale",
)

PORTFOLIO_QUALITY_PHRASES = (
    "portfolio quality",
    "quality metrics",
    "qualite du portefeuille",
    "metriques de qualite",
    "indicateurs de qualite",
)

THRESHOLD_PATTERN = re.compile(
    r"%|\b(flag|alert|alerte|threshold|seuil|exceed\w*|depass\w*|signal\w*"
    r"|more than|greater than|less than|plus de|moins de"
    r"|superieur\w*|inferieur\w*)\b"
)


def check_unsupported_scope(normalized_question: str) -> None:
    """Reject thresholds and alerts: tools only return the metrics themselves."""
    if THRESHOLD_PATTERN.search(normalized_question):
        raise UnsupportedQuestionError(
            "Unsupported question. A threshold or alert analysis is not "
            "supported; ask for the metric itself."
        )


def extract_claim_frequency_years(
    question: str,
    available_years: list[int],
) -> list[int]:
    """Extract at least two explicit years, or use the last three available."""
    if len(available_years) < 2:
        raise UnsupportedQuestionError(
            "Unsupported question. At least two years of data are needed "
            "for a claim frequency trend."
        )

    requested_years = sorted(
        {int(year) for year in re.findall(r"\b20\d{2}\b", question)}
    )

    if not requested_years:
        return available_years[-3:]

    unavailable_years = [
        year for year in requested_years if year not in available_years
    ]

    if unavailable_years:
        unavailable_years_text = ", ".join(str(year) for year in unavailable_years)
        raise UnsupportedQuestionError(
            f"Requested years are not available: {unavailable_years_text}."
        )

    if len(requested_years) < 2:
        raise UnsupportedQuestionError(
            "Unsupported question. A claim frequency trend needs at least two years."
        )

    return requested_years


def extract_claim_frequency_dimensions(question: str) -> list[Dimension]:
    """Return the segments explicitly requested for a claim frequency trend."""
    dimensions: list[Dimension] = []

    if re.search(r"\b(province|provinces|region|regions)\b", question):
        dimensions.append(Dimension.PROVINCE)

    if re.search(r"line of business|lines of business|lignes? d.affaires", question):
        dimensions.append(Dimension.LINE_OF_BUSINESS)

    return dimensions


RequestT = TypeVar("RequestT", bound=UnderwritingYearRequest)


@dataclass(frozen=True)
class RouteRule:
    """How one tool is recognized in a question and how its arguments are built."""

    tool_name: ToolName
    phrases: tuple[str, ...]
    build_arguments: Callable[[str, list[int]], ToolArguments]
    composite: bool = False
    scope_check: Callable[[str], None] | None = None


def _loss_ratio_arguments(
    question: str,
    available_years: list[int],
) -> LossRatioRequest:
    return LossRatioRequest(
        underwriting_years=extract_underwriting_years(
            question=question,
            available_years=available_years,
        ),
        dimensions=[
            Dimension.PROVINCE,
            Dimension.LINE_OF_BUSINESS,
            Dimension.UNDERWRITING_YEAR,
        ],
        provinces=extract_provinces(question),
        lines_of_business=extract_lines_of_business(question),
    )


def _claim_frequency_arguments(
    question: str,
    available_years: list[int],
) -> ClaimFrequencyRequest:
    return ClaimFrequencyRequest(
        years=extract_claim_frequency_years(
            question=question,
            available_years=available_years,
        ),
        dimensions=extract_claim_frequency_dimensions(question),
        provinces=extract_provinces(question),
        lines_of_business=extract_lines_of_business(question),
    )


def extract_underwriting_dimensions(question: str) -> list[Dimension]:
    """Requested segments, always followed by the underwriting year."""
    return [
        *extract_claim_frequency_dimensions(question),
        Dimension.UNDERWRITING_YEAR,
    ]


def _underwriting_year_arguments(
    request_model: type[RequestT],
) -> Callable[[str, list[int]], RequestT]:
    def build(question: str, available_years: list[int]) -> RequestT:
        return request_model(
            underwriting_years=extract_underwriting_years(
                question=question,
                available_years=available_years,
            ),
            dimensions=extract_underwriting_dimensions(question),
            provinces=extract_provinces(question),
            lines_of_business=extract_lines_of_business(question),
        )

    return build


ROUTE_RULES: tuple[RouteRule, ...] = (
    RouteRule(
        tool_name=LOSS_RATIO_TOOL,
        phrases=LOSS_RATIO_PHRASES,
        build_arguments=_loss_ratio_arguments,
    ),
    RouteRule(
        tool_name=CLAIM_FREQUENCY_TOOL,
        phrases=CLAIM_FREQUENCY_PHRASES,
        build_arguments=_claim_frequency_arguments,
        scope_check=check_unsupported_scope,
    ),
    RouteRule(
        tool_name=SEVERITY_TOOL,
        phrases=SEVERITY_PHRASES,
        build_arguments=_underwriting_year_arguments(SeverityRequest),
        scope_check=check_unsupported_scope,
    ),
    RouteRule(
        tool_name=EXPOSURE_SUMMARY_TOOL,
        phrases=EXPOSURE_SUMMARY_PHRASES,
        build_arguments=_underwriting_year_arguments(ExposureSummaryRequest),
        scope_check=check_unsupported_scope,
    ),
    RouteRule(
        tool_name=PORTFOLIO_QUALITY_TOOL,
        phrases=PORTFOLIO_QUALITY_PHRASES,
        build_arguments=_underwriting_year_arguments(PortfolioQualityRequest),
        composite=True,
        scope_check=check_unsupported_scope,
    ),
)

UNSUPPORTED_QUESTION_MESSAGE = (
    "Unsupported question. Currently supported analysis: "
    "loss ratio by province, line of business, and underwriting year. "
    "Also supported: claim frequency trend by year, province, "
    "and line of business; claim severity, exposure summary, and "
    "portfolio quality metrics by underwriting year, province, "
    "and line of business."
)


def select_route_rule(normalized_question: str) -> RouteRule:
    """Return the single rule matching the question, or reject it."""
    matches = [
        rule
        for rule in ROUTE_RULES
        if any(phrase in normalized_question for phrase in rule.phrases)
    ]

    composites = [rule for rule in matches if rule.composite]

    if len(matches) > 1 and len(composites) == 1:
        return composites[0]

    if len(matches) > 1:
        raise UnsupportedQuestionError(
            "Unsupported question. Ask for one analysis at a time. "
            "To get several metrics together, ask for the portfolio quality "
            "metrics."
        )

    if not matches:
        raise UnsupportedQuestionError(UNSUPPORTED_QUESTION_MESSAGE)

    return matches[0]


def route_question(
    question: str,
    available_years: list[int],
) -> ToolSelection:
    """Route a supported question to a validated analytical tool call."""
    if not question.strip():
        raise UnsupportedQuestionError("Question must not be empty.")

    if not available_years:
        raise UnsupportedQuestionError(
            "No underwriting years are available in the portfolio database."
        )

    normalized_question = normalize_text(question)
    rule = select_route_rule(normalized_question)

    if rule.scope_check is not None:
        rule.scope_check(normalized_question)

    return selection_for(rule.build_arguments(normalized_question, available_years))
