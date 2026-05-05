import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.ai_providers.base import RunbookRequest, RunbookResponse
from app.services.ai_providers.ai_factory import get_cached_ai_provider
from app.core.security import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Runbook"])


class RunbookAPIRequest(BaseModel):
    work_item_id: str
    component_id: str
    component_type: str
    error_code: str
    severity: str
    message: str
    signal_count: int = 1


class RunbookAPIResponse(BaseModel):
    summary: str
    immediate_actions: list[str]
    investigation_steps: list[str]
    prevention: list[str]
    estimated_resolution_time: str
    escalation_path: str
    provider: str
    model: str


@router.post(
    "/runbook",
    response_model=RunbookAPIResponse,
    summary="Generate AI runbook suggestion for an incident",
)
async def generate_runbook(
    request: RunbookAPIRequest,
    user: dict = Depends(get_current_user),
):
    """
    Generate an AI-powered runbook suggestion.

    Calls the configured AI provider (Gemini/Claude/OpenAI/Ollama)
    with the incident context and returns structured remediation steps.

    The provider is selected via the AI_PROVIDER environment variable.
    Switching providers requires zero code changes.
    """
    try:
        provider = get_cached_ai_provider()

        runbook_request = RunbookRequest(
            work_item_id=request.work_item_id,
            component_id=request.component_id,
            component_type=request.component_type,
            error_code=request.error_code,
            severity=request.severity,
            message=request.message,
            signal_count=request.signal_count,
        )

        logger.info(
            "Runbook requested",
            component=request.component_id,
            severity=request.severity,
            provider=provider.provider_name(),
            requested_by=user["username"],
        )

        result = await provider.generate_runbook(runbook_request)

        logger.info(
            "Runbook generated successfully",
            provider=result.provider,
            model=result.model,
            component=request.component_id,
        )

        return RunbookAPIResponse(
            summary=result.summary,
            immediate_actions=result.immediate_actions,
            investigation_steps=result.investigation_steps,
            prevention=result.prevention,
            estimated_resolution_time=result.estimated_resolution_time,
            escalation_path=result.escalation_path,
            provider=result.provider,
            model=result.model,
        )

    except ValueError as e:
        # Config error — missing API key etc.
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Runbook generation failed", error=str(e))
        raise HTTPException(
            status_code=502,
            detail=f"AI provider error: {str(e)}"
        )