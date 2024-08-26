import logging

from ...llm import Message
from .base import BaseAuditor

logger = logging.getLogger(__name__)


# TODO (GLENN): Implement this.
class DBAuditor(BaseAuditor):
    def _accept(self, message: Message):
        pass

    def close(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
