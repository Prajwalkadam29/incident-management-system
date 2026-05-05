import httpx
import structlog

from app.core.config import settings
from app.services.ai_providers.base import BaseAIProvider, RunbookRequest, RunbookResponse

logger = structlog.get_logger(__name__)


class OllamaProvider(BaseAIProvider):
    """
    Ollama provider — runs local models (llama3, mistral, etc.)
    No API key needed. Just run `ollama serve` locally.
    Configured via OLLAMA_BASE_URL and OLLAMA_MODEL env vars.
    """

    def provider_name(self) -> str:
        return "ollama"

    async def generate_runbook(self, request: RunbookRequest) -> RunbookResponse:
        prompt = self.build_prompt(request)

        logger.info(
            "Generating runbook with Ollama",
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )

        async with httpx.AsyncClient(timeout=120.0) as client:  # local models can be slow
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data["response"]

        return self.parse_response(raw_text, self.provider_name(), settings.OLLAMA_MODEL)