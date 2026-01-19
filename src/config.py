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

    # Anthropic
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

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
        # Require OpenAI key if any provider is OpenAI (default)
        provider_default = os.getenv("SDLC_LLM_PROVIDER_DEFAULT", "openai").lower()
        provider_roles = [
            os.getenv("SDLC_LLM_PROVIDER_PRODUCT_MANAGER", ""),
            os.getenv("SDLC_LLM_PROVIDER_BUSINESS_ANALYST", ""),
            os.getenv("SDLC_LLM_PROVIDER_ARCHITECT", ""),
            os.getenv("SDLC_LLM_PROVIDER_DEVELOPER", ""),
        ]
        uses_anthropic = provider_default == "anthropic" or any(
            p.strip().lower() == "anthropic" for p in provider_roles if p
        )
        uses_openai = not uses_anthropic or provider_default == "openai" or any(
            p.strip().lower() == "openai" for p in provider_roles if p
        )

        if uses_openai and not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if uses_anthropic and not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        return missing


# Global config instance
config = Config()
