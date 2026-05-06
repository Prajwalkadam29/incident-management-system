import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Type
import httpx
import structlog

from app.models.sql_models import ComponentType, Severity
from app.core.config import settings

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────
# Data class for alert payload
# ──────────────────────────────────────────

@dataclass
class AlertPayload:
    work_item_id: str
    component_id: str
    component_type: ComponentType
    severity: Severity
    title: str
    signal_count: int
    message: str


# ──────────────────────────────────────────
# Slack Webhook Client
# ──────────────────────────────────────────

async def send_slack_webhook(payload: AlertPayload, action: str, color: str = "#FF0000"):
    """
    Sends a formatted Block Kit message to Slack/Teams via incoming webhook.
    """
    if not settings.SLACK_WEBHOOK_URL:
        logger.debug("SLACK_WEBHOOK_URL not set. Skipping real webhook.")
        return

    # Map severity to emoji
    emoji = "🔴" if payload.severity in (Severity.P0, Severity.P1) else "🟡"
    if payload.severity == Severity.P0:
        emoji = "🚨"

    # Block Kit Payload (Compatible with Slack, and easily adaptable to Teams)
    slack_msg = {
        "text": f"{emoji} {payload.severity.value} Alert: {payload.title}",
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} {payload.severity.value} — {payload.title}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Component:*\n`{payload.component_id}`"},
                            {"type": "mrkdwn", "text": f"*Type:*\n{payload.component_type.value}"},
                            {"type": "mrkdwn", "text": f"*Action Req:*\n_{action}_"},
                            {"type": "mrkdwn", "text": f"*Signals:* {payload.signal_count}"}
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Message:*\n```{payload.message}```"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {"type": "mrkdwn", "text": f"Incident ID: `{payload.work_item_id}`"}
                        ]
                    }
                ]
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(settings.SLACK_WEBHOOK_URL, json=slack_msg)
            response.raise_for_status()
            logger.info("Webhook sent successfully", work_item_id=payload.work_item_id)
    except Exception as e:
        logger.error("Failed to send webhook", error=str(e), work_item_id=payload.work_item_id)


# ──────────────────────────────────────────
# Abstract Strategy
# ──────────────────────────────────────────

class AlertStrategy(ABC):
    """
    Abstract base for all alerting strategies.
    Different component types trigger different routing/urgency.
    """

    @abstractmethod
    async def send_alert(self, payload: AlertPayload) -> None:
        pass

    @abstractmethod
    def get_severity(self, component_type: ComponentType) -> Severity:
        """Each strategy knows what severity its component type maps to."""
        pass


# ──────────────────────────────────────────
# Concrete Strategies
# ──────────────────────────────────────────

class P0RDBMSAlertStrategy(AlertStrategy):
    """P0 — Critical. RDBMS failures are the most severe."""
    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P0

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.critical("🚨 P0 ALERT — DATABASE FAILURE", work_item_id=payload.work_item_id)
        await send_slack_webhook(payload, action="PAGE ON-CALL IMMEDIATELY", color="#FF0000")


class P0MCPHostAlertStrategy(AlertStrategy):
    """P0 — MCP Host failures affect all dependent services."""
    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P0

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.critical("🚨 P0 ALERT — MCP HOST FAILURE", work_item_id=payload.work_item_id)
        await send_slack_webhook(payload, action="PAGE ON-CALL IMMEDIATELY", color="#FF0000")


class P1APIAlertStrategy(AlertStrategy):
    """P1 — High. API failures are user-facing."""
    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P1

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.error("🔴 P1 ALERT — API FAILURE", work_item_id=payload.work_item_id)
        await send_slack_webhook(payload, action="NOTIFY ON-CALL", color="#FF6600")


class P1QueueAlertStrategy(AlertStrategy):
    """P1 — High. Async queue failures cause data pipeline delays."""
    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P1

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.error("🔴 P1 ALERT — QUEUE FAILURE", work_item_id=payload.work_item_id)
        await send_slack_webhook(payload, action="NOTIFY ON-CALL", color="#FF6600")


class P2CacheAlertStrategy(AlertStrategy):
    """P2 — Medium. Cache failures degrade performance but don't cause outages."""
    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P2

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.warning("🟡 P2 ALERT — CACHE FAILURE", work_item_id=payload.work_item_id)
        await send_slack_webhook(payload, action="NOTIFY INFRA TEAM", color="#FFCC00")


class P2NoSQLAlertStrategy(AlertStrategy):
    """P2 — Medium. NoSQL issues usually affect non-critical read paths."""
    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P2

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.warning("🟡 P2 ALERT — NOSQL FAILURE", work_item_id=payload.work_item_id)
        await send_slack_webhook(payload, action="NOTIFY INFRA TEAM", color="#FFCC00")


# ──────────────────────────────────────────
# Strategy Registry — maps ComponentType → Strategy
# ──────────────────────────────────────────

ALERT_STRATEGY_MAP: Dict[ComponentType, Type[AlertStrategy]] = {
    ComponentType.RDBMS:    P0RDBMSAlertStrategy,
    ComponentType.MCP_HOST: P0MCPHostAlertStrategy,
    ComponentType.API:      P1APIAlertStrategy,
    ComponentType.QUEUE:    P1QueueAlertStrategy,
    ComponentType.CACHE:    P2CacheAlertStrategy,
    ComponentType.NOSQL:    P2NoSQLAlertStrategy,
}


class AlertingService:
    """
    Context class that selects and executes the correct strategy
    based on the component type. Adding a new component type only
    requires adding a new strategy + one line in ALERT_STRATEGY_MAP.
    """

    def get_strategy(self, component_type: ComponentType) -> AlertStrategy:
        strategy_class = ALERT_STRATEGY_MAP.get(component_type)
        if not strategy_class:
            raise ValueError(f"No alert strategy for component type: {component_type}")
        return strategy_class()

    def get_severity_for_component(self, component_type: ComponentType) -> Severity:
        strategy = self.get_strategy(component_type)
        return strategy.get_severity(component_type)

    async def alert(self, payload: AlertPayload) -> None:
        strategy = self.get_strategy(payload.component_type)
        
        # We spawn the alert as a background task so it doesn't block the worker loop
        # in case the webhook endpoint is slow or timing out.
        asyncio.create_task(strategy.send_alert(payload))
        
        logger.info(
            "Alert dispatched to strategy",
            strategy=strategy.__class__.__name__,
            work_item_id=payload.work_item_id,
        )


# Singleton
alerting_service = AlertingService()