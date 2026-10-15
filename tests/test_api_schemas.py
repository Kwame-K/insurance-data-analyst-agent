import pytest
from pydantic import ValidationError

from insurance_data_analyst_agent.api.schemas import (
    AnalyzeRequest,
    LossRatioApiRequest,
)


def test_analyze_request_accepts_valid_payload() -> None:
    request = AnalyzeRequest(question="Loss ratio in QC 2025", request_id="abc-1")
    assert request.request_id == "abc-1"


def test_analyze_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest(question="Loss ratio in QC", sql="DROP TABLE claims")


def test_analyze_request_rejects_bad_request_id() -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest(question="Loss ratio in QC", request_id="bad id!")


def test_loss_ratio_request_reuses_domain_validation() -> None:
    with pytest.raises(ValidationError):
        LossRatioApiRequest(arguments={"underwriting_years": [2025, 2025]})

    with pytest.raises(ValidationError):
        LossRatioApiRequest(
            arguments={"underwriting_years": [2025], "provinces": ["XX"]}
        )


def test_loss_ratio_chart_requires_all_dimensions() -> None:
    with pytest.raises(ValidationError, match="include_chart requires"):
        LossRatioApiRequest(
            arguments={"underwriting_years": [2025]},
            include_chart=True,
        )
