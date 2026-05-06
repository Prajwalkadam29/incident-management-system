import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.ai_providers.base import RunbookRequest, RunbookResponse, RCARequest, RCAResponse
from app.services.ai_providers.ai_factory import get_cached_ai_provider
from app.core.security import get_current_user
from app.db.redis_client import get_redis

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Integration"])


class RunbookAPIRequest(BaseModel):
    work_item_id: str
    component_id: str
    component_type: str
    error_code: str
    severity: str
    message: str
    signal_count: int = 1
    bypass_cache: bool = False


class RunbookAPIResponse(BaseModel):
    summary: str
    immediate_actions: list[str]
    investigation_steps: list[str]
    prevention: list[str]
    estimated_resolution_time: str
    escalation_path: str
    provider: str
    model: str


class RCAAPIRequest(BaseModel):
    work_item_id: str
    component_id: str
    component_type: str
    severity: str
    title: str
    total_signals: int
    duration_minutes: int
    resolution_notes: str
    timeline_events: list[dict]
    bypass_cache: bool = False


class RCAAPIResponse(BaseModel):
    executive_summary: str
    impact: str
    root_cause: str
    trigger: str
    resolution: str
    action_items: list[str]
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

    Includes a Redis cache layer to protect upstream model rate-limits.
    """
    try:
        redis = get_redis()
        cache_key = f"ims:cache:ai:runbook:{request.component_id}:{request.error_code}"

        if not request.bypass_cache:
            try:
                cached_val = await redis.get(cache_key)
                if cached_val:
                    import json
                    logger.info(
                        "Runbook served from Redis cache",
                        component=request.component_id,
                        error_code=request.error_code,
                    )
                    cached_data = json.loads(cached_val)
                    cached_data["provider"] = f"{cached_data.get('provider')} (cached)"
                    return RunbookAPIResponse(**cached_data)
            except Exception as e:
                logger.error("Failed to read runbook cache", error=str(e))

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

        api_res = RunbookAPIResponse(
            summary=result.summary,
            immediate_actions=result.immediate_actions,
            investigation_steps=result.investigation_steps,
            prevention=result.prevention,
            estimated_resolution_time=result.estimated_resolution_time,
            escalation_path=result.escalation_path,
            provider=result.provider,
            model=result.model,
        )

        # Store in Redis with a 1-hour (3600 seconds) expiration
        try:
            import json
            await redis.setex(cache_key, 3600, json.dumps(api_res.dict()))
        except Exception as e:
            logger.error("Failed to write runbook cache", error=str(e))

        return api_res

    except ValueError as e:
        # Config error — missing API key etc.
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Runbook generation failed", error=str(e))
        raise HTTPException(
            status_code=502,
            detail=f"AI provider error: {str(e)}"
        )


@router.post(
    "/rca-draft",
    response_model=RCAAPIResponse,
    summary="Generate AI RCA draft for a resolved incident",
)
async def generate_rca_draft(
    request: RCAAPIRequest,
    user: dict = Depends(get_current_user),
):
    """
    Generate an AI-powered Root Cause Analysis draft.

    Uses the configured AI provider to analyze incident timeline,
    signals, and resolution notes to produce a structured RCA.

    Includes a Redis cache layer to protect upstream model rate-limits.
    """
    try:
        redis = get_redis()
        cache_key = f"ims:cache:ai:rcadraft:{request.work_item_id}"

        if not request.bypass_cache:
            try:
                cached_val = await redis.get(cache_key)
                if cached_val:
                    import json
                    logger.info(
                        "RCA draft served from Redis cache",
                        work_item_id=request.work_item_id,
                    )
                    cached_data = json.loads(cached_val)
                    cached_data["provider"] = f"{cached_data.get('provider')} (cached)"
                    return RCAAPIResponse(**cached_data)
            except Exception as e:
                logger.error("Failed to read RCA draft cache", error=str(e))

        provider = get_cached_ai_provider()

        rca_request = RCARequest(
            work_item_id=request.work_item_id,
            component_id=request.component_id,
            component_type=request.component_type,
            severity=request.severity,
            title=request.title,
            total_signals=request.total_signals,
            duration_minutes=request.duration_minutes,
            resolution_notes=request.resolution_notes,
            timeline_events=request.timeline_events,
        )

        logger.info(
            "RCA generation requested",
            work_item_id=request.work_item_id,
            provider=provider.provider_name(),
            requested_by=user["username"],
        )

        result = await provider.generate_rca(rca_request)

        logger.info(
            "RCA generated successfully",
            provider=result.provider,
            model=result.model,
            work_item_id=request.work_item_id,
        )

        api_res = RCAAPIResponse(
            executive_summary=result.executive_summary,
            impact=result.impact,
            root_cause=result.root_cause,
            trigger=result.trigger,
            resolution=result.resolution,
            action_items=result.action_items,
            provider=result.provider,
            model=result.model,
        )

        # Store in Redis with a 1-hour (3600 seconds) expiration
        try:
            import json
            await redis.setex(cache_key, 3600, json.dumps(api_res.dict()))
        except Exception as e:
            logger.error("Failed to write RCA draft cache", error=str(e))

        return api_res

    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("RCA generation failed", error=str(e))
        raise HTTPException(
            status_code=502,
            detail=f"AI provider error: {str(e)}"
        )