"""
Pytest configuration.
"""

import pytest
import sys
import os

# Skip tests that require heavy dependencies (faiss, sentence-transformers)
# unless explicitly enabled
SKIP_HEAVY = not os.environ.get("OPENCLAW_TEST_FULL", "")

pytestmark = pytest.mark.skipif(SKIP_HEAVY, reason="Heavy tests disabled by default")