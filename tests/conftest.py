import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "e2e: needs the running platform (docker compose); run with -m e2e",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if "e2e" in (config.getoption("markexpr") or ""):
        return

    skip_e2e = pytest.mark.skip(reason="end-to-end test; run with: pytest -m e2e")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)
