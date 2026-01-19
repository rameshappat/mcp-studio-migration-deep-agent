"""Human-in-the-Loop interaction handler."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from src.agents.base_agent import AgentMessage, ApprovalStatus

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """Types of human interactions."""

    APPROVAL = "approval"
    FEEDBACK = "feedback"
    SELECTION = "selection"
    CONFIRMATION = "confirmation"
    TEXT_INPUT = "text_input"


@dataclass
class HumanInteraction:
    """Represents a human interaction request."""

    interaction_type: InteractionType
    prompt: str
    context: dict[str, Any]
    options: list[str] | None = None
    default: str | None = None
    timeout_seconds: int = 300  # 5 minute default timeout


class HumanInTheLoop:
    """Handler for Human-in-the-Loop interactions."""

    def __init__(
        self,
        interactive: bool = True,
        auto_approve: bool = False,
        default_feedback: str = "",
    ):
        """Initialize the Human-in-the-Loop handler.

        Args:
            interactive: Whether to prompt for user input.
            auto_approve: Auto-approve all requests (for testing).
            default_feedback: Default feedback when non-interactive.
        """
        self.interactive = interactive
        self.auto_approve = auto_approve
        self.default_feedback = default_feedback
        self._interaction_callbacks: dict[InteractionType, Callable] = {}

    def register_callback(
        self,
        interaction_type: InteractionType,
        callback: Callable[[HumanInteraction], Any],
    ) -> None:
        """Register a callback for a specific interaction type.

        Args:
            interaction_type: Type of interaction.
            callback: Callback function to handle the interaction.
        """
        self._interaction_callbacks[interaction_type] = callback

    def request_approval(self, message: AgentMessage) -> ApprovalStatus:
        """Request human approval for an agent's output.

        Args:
            message: The agent message requiring approval.

        Returns:
            Approval status.
        """
        if self.auto_approve:
            logger.info("Auto-approving message")
            return ApprovalStatus.APPROVED

        if not self.interactive:
            logger.info("Non-interactive mode, auto-approving")
            return ApprovalStatus.APPROVED

        # Check for registered callback
        if InteractionType.APPROVAL in self._interaction_callbacks:
            interaction = HumanInteraction(
                interaction_type=InteractionType.APPROVAL,
                prompt=f"Approve output from {message.from_agent.value}?",
                context={
                    "content": message.content[:500],  # Truncate for display
                    "artifacts": list(message.artifacts.keys()),
                },
                options=["approve", "reject", "revise"],
            )
            result = self._interaction_callbacks[InteractionType.APPROVAL](interaction)
            return self._parse_approval_result(result)

        # Default CLI interaction
        return self._cli_approval(message)

    def _cli_approval(self, message: AgentMessage) -> ApprovalStatus:
        """Request approval via CLI."""
        print("\n" + "=" * 60)
        print(f"APPROVAL REQUIRED: {message.from_agent.value}")
        print("=" * 60)
        print(f"\nContent Preview:\n{message.content[:1000]}...")
        print(f"\nArtifacts: {list(message.artifacts.keys())}")
        print("\nOptions: [a]pprove, [r]eject, [v]ision requested")

        try:
            response = input("Your choice (a/r/v): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return ApprovalStatus.REJECTED

        if response in ("a", "approve", "y", "yes"):
            return ApprovalStatus.APPROVED
        elif response in ("r", "reject", "n", "no"):
            return ApprovalStatus.REJECTED
        elif response in ("v", "revise", "revision"):
            return ApprovalStatus.REVISION_REQUESTED
        else:
            print("Invalid input, defaulting to pending")
            return ApprovalStatus.PENDING

    def _parse_approval_result(self, result: Any) -> ApprovalStatus:
        """Parse approval result from callback."""
        if isinstance(result, ApprovalStatus):
            return result
        if isinstance(result, str):
            result = result.lower()
            if result in ("approve", "approved", "yes", "y", "a"):
                return ApprovalStatus.APPROVED
            elif result in ("reject", "rejected", "no", "n", "r"):
                return ApprovalStatus.REJECTED
            elif result in ("revise", "revision", "v"):
                return ApprovalStatus.REVISION_REQUESTED
        return ApprovalStatus.PENDING

    def request_feedback(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Request feedback from human.

        Args:
            prompt: Prompt to display to the human.
            context: Additional context.

        Returns:
            Human feedback text.
        """
        if not self.interactive:
            return self.default_feedback

        if InteractionType.FEEDBACK in self._interaction_callbacks:
            interaction = HumanInteraction(
                interaction_type=InteractionType.FEEDBACK,
                prompt=prompt,
                context=context or {},
            )
            return self._interaction_callbacks[InteractionType.FEEDBACK](interaction)

        # Default CLI interaction
        print(f"\n{prompt}")
        if context:
            print(f"Context: {context}")

        try:
            return input("Your feedback: ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def request_selection(
        self,
        prompt: str,
        options: list[str],
        allow_multiple: bool = False,
    ) -> list[str] | str:
        """Request selection from options.

        Args:
            prompt: Prompt to display.
            options: List of options to choose from.
            allow_multiple: Whether to allow multiple selections.

        Returns:
            Selected option(s).
        """
        if not self.interactive:
            return options[0] if options else ""

        if InteractionType.SELECTION in self._interaction_callbacks:
            interaction = HumanInteraction(
                interaction_type=InteractionType.SELECTION,
                prompt=prompt,
                context={"allow_multiple": allow_multiple},
                options=options,
            )
            return self._interaction_callbacks[InteractionType.SELECTION](interaction)

        # Default CLI interaction
        print(f"\n{prompt}")
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")

        try:
            choice = input("Your choice (number): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except (ValueError, EOFError, KeyboardInterrupt):
            pass

        return options[0] if options else ""

    def request_confirmation(
        self,
        prompt: str,
        default: bool = False,
    ) -> bool:
        """Request yes/no confirmation.

        Args:
            prompt: Prompt to display.
            default: Default value if no input.

        Returns:
            Boolean confirmation.
        """
        if self.auto_approve:
            return True

        if not self.interactive:
            return default

        if InteractionType.CONFIRMATION in self._interaction_callbacks:
            interaction = HumanInteraction(
                interaction_type=InteractionType.CONFIRMATION,
                prompt=prompt,
                context={},
                default="yes" if default else "no",
            )
            result = self._interaction_callbacks[InteractionType.CONFIRMATION](interaction)
            return result in (True, "yes", "y", "true", "1")

        # Default CLI interaction
        default_str = "Y/n" if default else "y/N"
        try:
            response = input(f"{prompt} [{default_str}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return default

        if not response:
            return default
        return response in ("y", "yes", "true", "1")

    def notify(self, message: str, level: str = "info") -> None:
        """Send a notification to the human.

        Args:
            message: Notification message.
            level: Notification level (info, warning, error).
        """
        prefix = {
            "info": "ℹ️ ",
            "warning": "⚠️ ",
            "error": "❌ ",
            "success": "✅ ",
        }.get(level, "")

        if self.interactive:
            print(f"\n{prefix}{message}")
        else:
            logger.info(f"{level.upper()}: {message}")

    def display_progress(
        self,
        stage: str,
        current: int,
        total: int,
        details: str = "",
    ) -> None:
        """Display progress to the human.

        Args:
            stage: Current stage name.
            current: Current step number.
            total: Total steps.
            details: Additional details.
        """
        percentage = (current / total * 100) if total > 0 else 0
        bar_length = 30
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        if self.interactive:
            print(f"\r[{bar}] {percentage:.0f}% - {stage}: {details}", end="", flush=True)
            if current >= total:
                print()  # New line when complete
        else:
            logger.info(f"Progress: {stage} - {current}/{total} ({percentage:.0f}%) - {details}")
