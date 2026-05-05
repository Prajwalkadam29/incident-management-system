import structlog
import google.generativeai as genai

from app.core.config import settings
from app.services.ai_providers.base import BaseAIProvider, RunbookRequest, RunbookResponse

logger = structlog.get_logger(__name__)


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini provider.
    Uses the official google-generativeai SDK.
    Configured via GEMINI_API_KEY and GEMINI_MODEL env vars.
    """

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file or docker-compose.yml environment section."
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)
        logger.info("Gemini provider initialized", model=settings.GEMINI_MODEL)

    def provider_name(self) -> str:
        return "gemini"

    async def generate_runbook(self, request: RunbookRequest) -> RunbookResponse:
        prompt = self.build_prompt(request)

        logger.info(
            "Generating runbook with Gemini",
            model=settings.GEMINI_MODEL,
            component=request.component_id,
            severity=request.severity,
        )

        # Gemini SDK is sync — run in thread pool to not block event loop
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._model.generate_content(prompt)
        )

        raw_text = response.text
        logger.debug("Gemini raw response", text=raw_text[:200])

        return self.parse_response(raw_text, self.provider_name(), settings.GEMINI_MODEL)