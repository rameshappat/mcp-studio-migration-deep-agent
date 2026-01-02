"""Configuration management for the MCP Agent application."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # LangSmith
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "python-mcp-agent")
    langsmith_tracing: bool = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"

    # GitHub MCP
    github_mcp_url: str = os.getenv(
        "GITHUB_MCP_URL", "https://api.githubcopilot.com/mcp/"
    )
    github_token: str = os.getenv("GITHUB_TOKEN", "")

    def setup_langsmith(self) -> None:
        """Configure LangSmith environment variables."""
        if self.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = self.langsmith_api_key
            os.environ["LANGSMITH_PROJECT"] = self.langsmith_project
            os.environ["LANGSMITH_TRACING"] = str(self.langsmith_tracing).lower()

    def validate(self) -> list[str]:
        """Validate required configuration. Returns list of missing keys."""
        missing = []
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        return missing


# Global config instance
config = Config()
