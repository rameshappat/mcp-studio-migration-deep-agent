"""Tests for main module."""

from src.main import demo_mode


def test_demo_mode(capsys) -> None:
    """Test demo_mode function prints expected output."""
    demo_mode()
    captured = capsys.readouterr()
    assert "GitHub MCP Agent - Demo Mode" in captured.out
    assert "OPENAI_API_KEY" in captured.out
    assert "src/mcp_client/" in captured.out
