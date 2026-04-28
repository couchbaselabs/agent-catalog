"""
Test configuration for agentc_cli tests.
This module configures pytest fixtures and logging to prevent
"I/O operation on closed file" errors when using click_extra.testing.ExtraCliRunner.
"""

import logging
import pytest

# Store the original emit method
_original_emit = logging.StreamHandler.emit


def _safe_emit(self, record):
    """
    Wrapper for StreamHandler.emit that catches closed file errors.
    This prevents "I/O operation on closed file" errors in test environments.
    """
    try:
        # Check if stream is closed before attempting to write
        if hasattr(self, "stream") and hasattr(self.stream, "closed") and self.stream.closed:
            return  # Silently skip if stream is already closed
        _original_emit(self, record)
    except (ValueError, OSError, AttributeError) as e:
        # Catch various stream-related errors that can occur in test environments
        if "I/O operation on closed file" in str(e) or "closed" in str(e).lower():
            pass  # Silently ignore closed file errors
        else:
            # For unexpected errors, try to handle gracefully
            pass
    except Exception:
        # Catch any other unexpected errors
        pass


# Monkey-patch StreamHandler.emit at module import time
logging.StreamHandler.emit = _safe_emit


@pytest.fixture(autouse=True, scope="session")
def restore_logging_on_exit():
    """
    Restore the original logging.StreamHandler.emit after all tests complete.
    """
    yield
    # Restore original emit method after all tests
    logging.StreamHandler.emit = _original_emit
