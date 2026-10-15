import logging

from insurance_data_analyst_agent.logging_config import (
    configure_logging,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
)


def test_new_correlation_id_is_unique() -> None:
    assert new_correlation_id() != new_correlation_id()


def test_correlation_id_is_bound_to_context() -> None:
    set_correlation_id("abc-123")
    assert get_correlation_id() == "abc-123"


def test_log_records_carry_correlation_id(capsys) -> None:
    configure_logging("INFO")
    set_correlation_id("req-42")

    logging.getLogger("test").info("hello")

    assert "[req-42]" in capsys.readouterr().err
