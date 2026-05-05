import httpx
import structlog

from app.core.config import settings
from app.services.ai_providers.base import BaseAIProvider, RunbookRequest, RunbookResponse

logger = structlog.get_logger(__name__)


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI provider.
    Uses direct HTTP calls to /v1/chat/completions.
    Configured via OPENAI_API_KEY and OPENAI_MODEL env vars.
    """

    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

    def provider_name(self) -> str:
        return "openai"

    async def generate_runbook(self, request: RunbookRequest) -> RunbookResponse:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set.")

        prompt = self.build_prompt(request)

        logger.info("Generating runbook with OpenAI", model=settings.OPENAI_MODEL)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.OPENAI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]

        return self.parse_response(raw_text, self.provider_name(), settings.OPENAI_MODEL)