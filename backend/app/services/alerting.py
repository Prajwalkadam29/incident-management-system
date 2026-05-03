from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Type
import structlog

from app.models.sql_models import ComponentType, Severity

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
# Abstract Strategy
# ──────────────────────────────────────────

class AlertStrategy(ABC):
    """
    Abstract base for all alerting strategies.
    In production you'd call PagerDuty / OpsGenie / Slack here.
    For this project we log structured alerts — easily swappable.
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
    """
    P0 — Critical. RDBMS failures are the most severe.
    Would page on-call immediately in production.
    """

    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P0

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.critical(
            "🚨 P0 ALERT — DATABASE FAILURE",
            work_item_id=payload.work_item_id,
            component_id=payload.component_id,
            title=payload.title,
            signal_count=payload.signal_count,
            action="PAGE_ON_CALL_IMMEDIATELY",
            channel="pagerduty",   # in prod: await pagerduty_client.trigger(payload)
        )


class P0MCPHostAlertStrategy(AlertStrategy):
    """
    P0 — MCP Host failures affect all dependent services.
    """

    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P0

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.critical(
            "🚨 P0 ALERT — MCP HOST FAILURE",
            work_item_id=payload.work_item_id,
            component_id=payload.component_id,
            title=payload.title,
            signal_count=payload.signal_count,
            action="PAGE_ON_CALL_IMMEDIATELY",
            channel="pagerduty",
        )


class P1APIAlertStrategy(AlertStrategy):
    """
    P1 — High. API failures are user-facing.
    """

    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P1

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.error(
            "🔴 P1 ALERT — API FAILURE",
            work_item_id=payload.work_item_id,
            component_id=payload.component_id,
            title=payload.title,
            signal_count=payload.signal_count,
            action="NOTIFY_ON_CALL",
            channel="slack_oncall",  # in prod: await slack_client.post(payload)
        )


class P1QueueAlertStrategy(AlertStrategy):
    """
    P1 — High. Async queue failures cause data pipeline delays.
    """

    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P1

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.error(
            "🔴 P1 ALERT — QUEUE FAILURE",
            work_item_id=payload.work_item_id,
            component_id=payload.component_id,
            title=payload.title,
            signal_count=payload.signal_count,
            action="NOTIFY_ON_CALL",
            channel="slack_oncall",
        )


class P2CacheAlertStrategy(AlertStrategy):
    """
    P2 — Medium. Cache failures degrade performance but don't cause outages.
    """

    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P2

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.warning(
            "🟡 P2 ALERT — CACHE FAILURE",
            work_item_id=payload.work_item_id,
            component_id=payload.component_id,
            title=payload.title,
            signal_count=payload.signal_count,
            action="NOTIFY_TEAM_CHANNEL",
            channel="slack_infra",
        )


class P2NoSQLAlertStrategy(AlertStrategy):
    """
    P2 — Medium. NoSQL issues usually affect non-critical read paths.
    """

    def get_severity(self, component_type: ComponentType) -> Severity:
        return Severity.P2

    async def send_alert(self, payload: AlertPayload) -> None:
        logger.warning(
            "🟡 P2 ALERT — NOSQL FAILURE",
            work_item_id=payload.work_item_id,
            component_id=payload.component_id,
            title=payload.title,
            signal_count=payload.signal_count,
            action="NOTIFY_TEAM_CHANNEL",
            channel="slack_infra",
        )


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
        await strategy.send_alert(payload)
        logger.info(
            "Alert dispatched",
            strategy=strategy.__class__.__name__,
            work_item_id=payload.work_item_id,
        )


# Singleton
alerting_service = AlertingService()