from __future__ import annotations

from insurance_data_analyst_agent.api.app import create_app
from insurance_data_analyst_agent.config import settings
from insurance_data_analyst_agent.logging_config import configure_logging

configure_logging(settings.log_level)

app = create_app()
