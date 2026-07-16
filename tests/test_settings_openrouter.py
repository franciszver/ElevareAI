"""
Tests for OpenRouter config migration (Phase 1, task 1.1).
Verifies Settings exposes openrouter_* fields and OpenAIClient wires them
into the openai.OpenAI client via base_url.
"""

from unittest.mock import MagicMock, patch

from src.config.settings import Settings


def test_settings_openrouter_defaults():
    """Settings() should default to OpenRouter naming/values with no .env present."""
    s = Settings(_env_file=None)

    assert s.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert s.openrouter_model == "openai/gpt-oss-20b:free"
    assert s.openrouter_temperature == 0.7
    assert s.openrouter_max_tokens == 2000
    assert s.openrouter_api_key == ""


def test_openai_client_uses_openrouter_settings():
    """OpenAIClient should construct openai.OpenAI with OpenRouter base_url/api_key
    and pick up model/temperature/max_tokens from the renamed settings fields."""
    test_settings = Settings(_env_file=None)
    test_settings.openrouter_api_key = "test-key-123"

    with patch("src.services.ai.openai_client.settings", test_settings), patch(
        "openai.OpenAI"
    ) as mock_openai_cls:
        mock_openai_cls.return_value = MagicMock()

        from src.services.ai.openai_client import OpenAIClient

        client = OpenAIClient()

        mock_openai_cls.assert_called_once_with(
            api_key="test-key-123",
            base_url="https://openrouter.ai/api/v1",
        )
        assert client.model == "openai/gpt-oss-20b:free"
        assert client.temperature == 0.7
        assert client.max_tokens == 2000
