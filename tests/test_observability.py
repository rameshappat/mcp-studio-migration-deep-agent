"""Tests for observability setup."""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.observability.langsmith_setup import setup_langsmith, get_langsmith_client


class TestLangSmithSetup:
    """Tests for LangSmith setup."""

    def test_setup_without_api_key(self):
        """Test setup fails gracefully without API key."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove any existing key
            os.environ.pop("LANGSMITH_API_KEY", None)
            result = setup_langsmith(api_key=None)
            assert result is False

    def test_setup_sets_environment_variables(self):
        """Test that setup sets the correct environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.observability.langsmith_setup.Client") as mock_client:
                mock_client.return_value = MagicMock()
                
                setup_langsmith(
                    api_key="test-key",
                    project="test-project",
                    tracing_enabled=True,
                )
                
                assert os.environ["LANGSMITH_API_KEY"] == "test-key"
                assert os.environ["LANGSMITH_PROJECT"] == "test-project"
                assert os.environ["LANGSMITH_TRACING"] == "true"

    def test_get_client_before_setup(self):
        """Test getting client before setup returns None."""
        # Reset the global client
        import src.observability.langsmith_setup as ls
        ls._langsmith_client = None
        
        client = get_langsmith_client()
        assert client is None
