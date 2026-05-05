from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class RunbookRequest:
    """
    Standardized input — same regardless of which AI provider is used.
    """
    component_id: str
    component_type: str
    error_code: str
    severity: str
    message: str
    signal_count: int
    work_item_id: str


@dataclass
class RunbookResponse:
    """
    Standardized output — same regardless of which AI provider is used.
    """
    summary: str                    # 1-2 sentence incident summary
    immediate_actions: list[str]    # what to do RIGHT NOW
    investigation_steps: list[str]  # how to dig deeper
    prevention: list[str]           # long-term fixes
    estimated_resolution_time: str  # e.g. "15-30 minutes"
    escalation_path: str            # who to call if this doesn't work
    provider: str                   # which AI generated this
    model: str                      # which model specifically


class BaseAIProvider(ABC):
    """
    Abstract base class for all AI providers.

    To add a new provider:
    1. Create a new file in this folder (e.g. openai_provider.py)
    2. Subclass BaseAIProvider
    3. Implement generate_runbook()
    4. Register it in the factory (ai_factory.py)
    5. Set AI_PROVIDER=openai in your .env

    That's it. Zero changes to any other file.
    """

    @abstractmethod
    async def generate_runbook(self, request: RunbookRequest) -> RunbookResponse:
        """Generate a runbook suggestion for an incident."""
        pass

    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging/display."""
        pass

    def build_prompt(self, request: RunbookRequest) -> str:
        """
        Shared prompt template used by ALL providers.
        Defined here so changing the prompt doesn't require
        touching each provider separately.
        """
        return f"""You are an expert Site Reliability Engineer (SRE) responding to a production incident.

INCIDENT DETAILS:
- Component ID: {request.component_id}
- Component Type: {request.component_type}
- Error Code: {request.error_code}
- Severity: {request.severity}
- Error Message: {request.message}
- Signal Count: {request.signal_count} signals received
- Work Item ID: {request.work_item_id}

Generate a concise, actionable runbook for this incident.
Respond ONLY with a valid JSON object in this exact format, no markdown, no explanation:

{{
  "summary": "One or two sentence summary of what is likely happening and its impact",
  "immediate_actions": [
    "First thing to do right now",
    "Second immediate action",
    "Third immediate action"
  ],
  "investigation_steps": [
    "How to confirm the root cause",
    "What logs/metrics to check",
    "What queries to run"
  ],
  "prevention": [
    "Long term fix 1",
    "Long term fix 2"
  ],
  "estimated_resolution_time": "X-Y minutes",
  "escalation_path": "Who to escalate to if unresolved in X minutes"
}}"""

    def parse_response(self, raw_text: str, provider: str, model: str) -> RunbookResponse:
        """
        Shared JSON parser used by ALL providers.
        Handles cleanup of markdown fences if the model adds them.
        """
        import json
        import re

        # Strip markdown code fences if present
        clean = re.sub(r"```(?:json)?", "", raw_text).strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            # Fallback — extract whatever JSON object exists in the text
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError(f"Could not parse JSON from AI response: {clean[:200]}")

        return RunbookResponse(
            summary=data.get("summary", "No summary provided"),
            immediate_actions=data.get("immediate_actions", []),
            investigation_steps=data.get("investigation_steps", []),
            prevention=data.get("prevention", []),
            estimated_resolution_time=data.get("estimated_resolution_time", "Unknown"),
            escalation_path=data.get("escalation_path", "Contact on-call lead"),
            provider=provider,
            model=model,
        )