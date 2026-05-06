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


@dataclass
class RCARequest:
    """
    Input data for generating an RCA.
    """
    work_item_id: str
    component_id: str
    component_type: str
    severity: str
    title: str
    total_signals: int
    duration_minutes: int
    resolution_notes: str
    timeline_events: list[dict]  # List of significant events during the incident


@dataclass
class RCAResponse:
    """
    Standardized RCA output draft.
    """
    executive_summary: str
    impact: str
    root_cause: str
    trigger: str
    resolution: str
    action_items: list[str]
    provider: str
    model: str


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
    async def generate_rca(self, request: RCARequest) -> RCAResponse:
        """Generate an RCA draft for a resolved incident."""
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

    def build_rca_prompt(self, request: RCARequest) -> str:
        """Shared prompt template for generating RCAs."""
        import json
        timeline_str = json.dumps(request.timeline_events, indent=2)

        return f"""You are an expert Site Reliability Engineer (SRE). Write a formal Root Cause Analysis (RCA) draft for a resolved production incident.

INCIDENT DETAILS:
- Work Item ID: {request.work_item_id}
- Title: {request.title}
- Component: {request.component_id} ({request.component_type})
- Severity: {request.severity}
- Total Signals Received: {request.total_signals}
- Incident Duration: {request.duration_minutes} minutes
- Resolution Notes: {request.resolution_notes}

TIMELINE EVENTS:
{timeline_str}

Based on this data, generate a professional RCA draft. 
Respond ONLY with a valid JSON object in this exact format, no markdown, no explanation:

{{
  "executive_summary": "High-level summary of what happened, how long it lasted, and business impact.",
  "impact": "What systems/users were affected.",
  "root_cause": "The underlying technical reason the incident occurred.",
  "trigger": "The specific event that started the incident.",
  "resolution": "What actions were taken to restore service.",
  "action_items": [
    "Specific task to prevent recurrence 1",
    "Specific task to improve detection 2"
  ]
}}"""

    def parse_rca_response(self, raw_text: str, provider: str, model: str) -> RCAResponse:
        import json
        import re

        clean = re.sub(r"```(?:json)?", "", raw_text).strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError(f"Could not parse JSON from AI response: {clean[:200]}")

        return RCAResponse(
            executive_summary=data.get("executive_summary", "No summary provided"),
            impact=data.get("impact", "Unknown"),
            root_cause=data.get("root_cause", "Unknown"),
            trigger=data.get("trigger", "Unknown"),
            resolution=data.get("resolution", "Unknown"),
            action_items=data.get("action_items", []),
            provider=provider,
            model=model,
        )