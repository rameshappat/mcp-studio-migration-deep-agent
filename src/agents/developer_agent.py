"""Developer Agent - Generates full-stack code and pushes to GitHub."""

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from .base_agent import (
    AgentContext,
    AgentMessage,
    AgentRole,
    ApprovalStatus,
    BaseAgent,
)

logger = logging.getLogger(__name__)


class DeveloperAgent(BaseAgent):
    """Agent that acts as a Full-Stack Developer, generating code."""

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        model_name: str = "gpt-4o",
        temperature: float = 0.3,
        github_client: Any = None,
    ):
        """Initialize the Developer Agent."""
        super().__init__(
            role=AgentRole.DEVELOPER,
            llm=llm,
            model_name=model_name,
            temperature=temperature,  # Lower temperature for code generation
        )
        self._github_client = github_client

    @property
    def system_prompt(self) -> str:
        """Return the system prompt for the Developer."""
        return """You are an experienced Full-Stack Developer with expertise in 
modern web technologies and best practices.

Your responsibilities:
1. Implement features based on user stories and architecture
2. Write clean, maintainable, well-documented code
3. Follow SOLID principles and design patterns
4. Create unit tests for all components
5. Set up project structure and configurations

When generating code, structure your output as JSON:
{
    "project_structure": {
        "directories": ["src/", "tests/", "docs/"],
        "description": "Project layout explanation"
    },
    "files": [
        {
            "path": "src/main.py",
            "language": "python",
            "description": "Main application entry point",
            "content": "# File content here"
        }
    ],
    "dependencies": {
        "runtime": ["fastapi", "uvicorn", "sqlalchemy"],
        "development": ["pytest", "black", "mypy"]
    },
    "configuration_files": [
        {
            "path": "pyproject.toml",
            "content": "# Configuration content"
        }
    ],
    "docker": {
        "dockerfile": "Dockerfile content",
        "docker_compose": "docker-compose.yml content"
    },
    "tests": [
        {
            "path": "tests/test_main.py",
            "description": "Unit tests for main module",
            "content": "# Test content"
        }
    ],
    "documentation": {
        "readme": "README.md content",
        "api_docs": "API documentation"
    }
}

Follow these best practices:
- Use type hints in Python
- Write comprehensive docstrings
- Include error handling
- Add logging for debugging
- Create reusable components
- Follow the architecture provided by the Architect"""

    def set_github_client(self, github_client: Any) -> None:
        """Set the GitHub MCP client."""
        self._github_client = github_client

    async def _process_response(
        self, response: AIMessage, context: AgentContext
    ) -> AgentMessage:
        """Process the LLM response into code artifacts."""
        content = str(response.content)

        artifacts = {}
        try:
            # Extract JSON from response
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            code_output = json.loads(json_str)
            artifacts["code"] = code_output

            # Extract files for easier access
            if "files" in code_output:
                for file_info in code_output["files"]:
                    path = file_info.get("path", "")
                    content_str = file_info.get("content", "")
                    context.code_artifacts[path] = content_str

        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Could not parse structured output: {e}")
            # Try to extract code blocks
            artifacts["code_blocks"] = self._extract_code_blocks(content)

        return AgentMessage(
            from_agent=self.role,
            to_agent=None,  # End of pipeline
            content=content,
            artifacts=artifacts,
            requires_approval=True,
            approval_status=ApprovalStatus.PENDING,
            metadata={"stage": "code_generation"},
        )

    def _extract_code_blocks(self, content: str) -> list[dict[str, str]]:
        """Extract code blocks from content."""
        blocks = []
        languages = ["python", "typescript", "javascript", "yaml", "json", "dockerfile"]

        for lang in languages:
            marker = f"```{lang}"
            if marker in content.lower():
                parts = content.split(marker)
                for part in parts[1:]:
                    if "```" in part:
                        code = part.split("```")[0].strip()
                        blocks.append({"language": lang, "code": code})

        return blocks

    async def generate_code(
        self,
        context: AgentContext,
        architecture_message: AgentMessage,
    ) -> AgentMessage:
        """Generate code based on architecture and stories.

        Args:
            context: The shared workflow context.
            architecture_message: Message from Architect with design.

        Returns:
            Agent message with generated code.
        """
        architecture = architecture_message.artifacts.get("architecture", {})

        input_message = AgentMessage(
            from_agent=AgentRole.ARCHITECT,
            to_agent=self.role,
            content=f"""Based on the following architecture and user stories, generate 
the full-stack code implementation.

Project: {context.project_name}
Description: {context.project_description}

Architecture:
{json.dumps(architecture, indent=2)}

Stories to implement:
{json.dumps(context.stories[:5], indent=2)}  # Start with first 5 stories

Generate:
1. Project structure with all necessary files
2. Backend API implementation
3. Frontend components (if applicable)
4. Database models and migrations
5. Unit tests
6. Docker configuration
7. Documentation

Ensure code is production-ready with proper error handling and logging.""",
        )

        return await self.process(input_message, context)

    async def push_to_github(
        self,
        context: AgentContext,
        repo_owner: str,
        repo_name: str,
        branch: str = "main",
        commit_message: str | None = None,
    ) -> dict[str, Any]:
        """Push generated code to GitHub using MCP.

        Args:
            context: The shared workflow context.
            repo_owner: GitHub repository owner.
            repo_name: GitHub repository name.
            branch: Branch to push to.
            commit_message: Commit message.

        Returns:
            Dictionary with commit information.
        """
        if not self._github_client:
            logger.warning("GitHub client not configured")
            return {"error": "GitHub client not configured"}

        if not context.code_artifacts:
            logger.warning("No code artifacts to push")
            return {"error": "No code artifacts to push"}

        message = commit_message or f"feat: Implement {context.project_name} - Auto-generated by Developer Agent"

        try:
            # Prepare files array for push_files tool (single commit for all files)
            files = [
                {"path": file_path, "content": file_content}
                for file_path, file_content in context.code_artifacts.items()
            ]
            
            # Use push_files to push all files in a single commit
            result = await self._github_client.call_tool(
                "push_files",
                {
                    "owner": repo_owner,
                    "repo": repo_name,
                    "branch": branch,
                    "files": files,
                    "message": message,
                },
            )
            
            commit_results = [
                {"file": f["path"], "status": "success"}
                for f in files
            ]
            
            # Store commit info in context
            context.github_commits.extend(commit_results)

            return {
                "status": "success",
                "files_pushed": len(files),
                "commits": commit_results,
                "sha": result.get("commit", {}).get("sha") if isinstance(result, dict) else None,
            }

        except Exception as e:
            logger.error(f"Error pushing to GitHub: {e}")
            return {"error": str(e)}

    async def create_pull_request(
        self,
        context: AgentContext,
        repo_owner: str,
        repo_name: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> dict[str, Any]:
        """Create a pull request for the generated code.

        Args:
            context: The shared workflow context.
            repo_owner: GitHub repository owner.
            repo_name: GitHub repository name.
            head_branch: Branch with changes.
            base_branch: Branch to merge into.

        Returns:
            Pull request information.
        """
        if not self._github_client:
            return {"error": "GitHub client not configured"}

        try:
            # Generate PR description
            pr_body = f"""## {context.project_name}

### Description
{context.project_description}

### Changes
This PR implements the following stories:
{chr(10).join(f"- {story.get('title', 'Story')}" for story in context.stories[:10])}

### Architecture
- Components: {len(context.architecture.get('components', []))}
- APIs: {sum(len(c.get('apis', [])) for c in context.architecture.get('components', []))}

### Files Changed
{chr(10).join(f"- `{path}`" for path in context.code_artifacts.keys())}

---
*Auto-generated by Developer Agent*
"""

            result = await self._github_client.call_tool(
                "create_pull_request",
                {
                    "owner": repo_owner,
                    "repo": repo_name,
                    "title": f"feat: {context.project_name}",
                    "body": pr_body,
                    "head": head_branch,
                    "base": base_branch,
                },
            )

            return {
                "status": "success",
                "pr_number": result.get("number"),
                "pr_url": result.get("html_url"),
            }

        except Exception as e:
            logger.error(f"Error creating PR: {e}")
            return {"error": str(e)}

    async def implement_story(
        self,
        context: AgentContext,
        story: dict[str, Any],
    ) -> AgentMessage:
        """Implement a specific user story.

        Args:
            context: The shared workflow context.
            story: The story to implement.

        Returns:
            Agent message with implementation.
        """
        input_message = AgentMessage(
            from_agent=AgentRole.ORCHESTRATOR,
            to_agent=self.role,
            content=f"""Implement the following user story:

Story: {json.dumps(story, indent=2)}

Architecture Context:
{json.dumps(context.architecture, indent=2)}

Generate the code files needed to implement this story.
Include unit tests and documentation.""",
        )

        return await self.process(input_message, context)
