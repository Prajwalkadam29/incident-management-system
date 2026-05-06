import structlog
from groq import AsyncGroq

from app.core.config import settings
from app.services.ai_providers.base import BaseAIProvider, RunbookRequest, RunbookResponse, RCARequest, RCAResponse

logger = structlog.get_logger(__name__)


class GroqProvider(BaseAIProvider):
    """
    Groq provider using the official Groq SDK.
    Configured via GROQ_API_KEY and GROQ_MODEL env vars.
    """

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file."
            )
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL
        logger.info("Groq provider initialized", model=self.model)

    def provider_name(self) -> str:
        return "groq"

    async def generate_runbook(self, request: RunbookRequest) -> RunbookResponse:
        prompt = self.build_prompt(request)

        logger.info(
            "Generating runbook with Groq",
            model=self.model,
            component=request.component_id,
            severity=request.severity,
        )

        response = await self.client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model=self.model,
            temperature=0.2,
        )

        raw_text = response.choices[0].message.content
        logger.debug("Groq raw response", text=raw_text[:200])

        return self.parse_response(raw_text, self.provider_name(), self.model)

    async def generate_rca(self, request: RCARequest) -> RCAResponse:
        prompt = self.build_rca_prompt(request)

        logger.info(
            "Generating RCA draft with Groq",
            model=self.model,
            work_item=request.work_item_id,
            severity=request.severity,
        )

        response = await self.client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model=self.model,
            temperature=0.2,
        )

        raw_text = response.choices[0].message.content
        logger.debug("Groq raw RCA response", text=raw_text[:200])

        return self.parse_rca_response(raw_text, self.provider_name(), self.model)
