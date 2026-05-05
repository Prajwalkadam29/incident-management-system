import httpx
import structlog

from app.core.config import settings
from app.services.ai_providers.base import BaseAIProvider, RunbookRequest, RunbookResponse

logger = structlog.get_logger(__name__)


class ClaudeProvider(BaseAIProvider):
    """
    Anthropic Claude provider.
    Uses direct HTTP calls to /v1/messages.
    Configured via CLAUDE_API_KEY and CLAUDE_MODEL env vars.
    """

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

    def provider_name(self) -> str:
        return "claude"

    async def generate_runbook(self, request: RunbookRequest) -> RunbookResponse:
        if not settings.CLAUDE_API_KEY:
            raise ValueError("CLAUDE_API_KEY is not set.")

        prompt = self.build_prompt(request)

        logger.info("Generating runbook with Claude", model=settings.CLAUDE_MODEL)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.ANTHROPIC_API_URL,
                headers={
                    "x-api-key": settings.CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.CLAUDE_MODEL,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data["content"][0]["text"]

        return self.parse_response(raw_text, self.provider_name(), settings.CLAUDE_MODEL)