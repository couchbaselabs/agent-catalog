import datetime
import os

from agentc_core.config import Config


def test_dotenv():
    # TODO (GLENN): Implement this test!
    pass


def test_ttl_env_parsing():
    os.environ["AGENT_CATALOG_LOG_TTL"] = "2"
    config = Config()
    assert config.log_ttl == datetime.timedelta(seconds=2)

    os.environ["AGENT_CATALOG_LOG_TTL"] = "P3DT12H30M5S"
    config = Config()
    assert config.log_ttl == datetime.timedelta(days=3, hours=12, minutes=30, seconds=5)
