from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Type
import structlog

from app.models.sql_models import WorkItemStatus, RCARecord

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────
# Invalid Transition Exception
# ──────────────────────────────────────────

class InvalidStateTransitionError(Exception):
    """Raised when a state transition is not allowed."""
    pass


class MissingRCAError(Exception):
    """Raised when attempting to close a Work Item without a complete RCA."""
    pass


# ──────────────────────────────────────────
# Abstract State
# ──────────────────────────────────────────

class WorkItemState(ABC):
    """Each concrete state knows which transitions it allows."""

    @abstractmethod
    def investigate(self, work_item) -> None:
        pass

    @abstractmethod
    def resolve(self, work_item) -> None:
        pass

    @abstractmethod
    def close(self, work_item) -> None:
        pass

    @property
    @abstractmethod
    def status(self) -> WorkItemStatus:
        pass

    def _reject(self, target: str):
        raise InvalidStateTransitionError(
            f"Cannot transition from '{self.status}' to '{target}'. "
            f"Current state does not allow this transition."
        )


# ──────────────────────────────────────────
# Concrete States
# ──────────────────────────────────────────

class OpenState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.OPEN

    def investigate(self, work_item) -> None:
        work_item.status = WorkItemStatus.INVESTIGATING
        work_item.updated_at = datetime.now(timezone.utc)
        logger.info("WorkItem transitioned OPEN → INVESTIGATING",
                    work_item_id=str(work_item.id))

    def resolve(self, work_item) -> None:
        self._reject("RESOLVED")

    def close(self, work_item) -> None:
        self._reject("CLOSED")


class InvestigatingState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.INVESTIGATING

    def investigate(self, work_item) -> None:
        self._reject("INVESTIGATING")  # already in this state

    def resolve(self, work_item) -> None:
        work_item.status = WorkItemStatus.RESOLVED
        work_item.resolved_at = datetime.now(timezone.utc)
        work_item.updated_at = datetime.now(timezone.utc)
        logger.info("WorkItem transitioned INVESTIGATING → RESOLVED",
                    work_item_id=str(work_item.id))

    def close(self, work_item) -> None:
        self._reject("CLOSED")


class ResolvedState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.RESOLVED

    def investigate(self, work_item) -> None:
        self._reject("INVESTIGATING")

    def resolve(self, work_item) -> None:
        self._reject("RESOLVED")  # already resolved

    def close(self, work_item) -> None:
        # Guard: RCA must exist and be complete
        if not work_item.rca:
            raise MissingRCAError(
                "Cannot close this incident. "
                "A complete Root Cause Analysis (RCA) must be submitted first."
            )

        # Calculate MTTR — from first signal to RCA submission
        start = work_item.created_at
        end = work_item.rca.incident_end

        # Ensure both are timezone-aware for subtraction
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        mttr_minutes = (end - start).total_seconds() / 60
        work_item.mttr_minutes = round(mttr_minutes, 2)
        work_item.status = WorkItemStatus.CLOSED
        work_item.closed_at = datetime.now(timezone.utc)
        work_item.updated_at = datetime.now(timezone.utc)

        logger.info(
            "WorkItem transitioned RESOLVED → CLOSED",
            work_item_id=str(work_item.id),
            mttr_minutes=work_item.mttr_minutes,
        )


class ClosedState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.CLOSED

    def investigate(self, work_item) -> None:
        self._reject("INVESTIGATING")

    def resolve(self, work_item) -> None:
        self._reject("RESOLVED")

    def close(self, work_item) -> None:
        self._reject("CLOSED")  # already closed


# ──────────────────────────────────────────
# State Registry
# ──────────────────────────────────────────

STATE_MAP: Dict[WorkItemStatus, Type[WorkItemState]] = {
    WorkItemStatus.OPEN:          OpenState,
    WorkItemStatus.INVESTIGATING: InvestigatingState,
    WorkItemStatus.RESOLVED:      ResolvedState,
    WorkItemStatus.CLOSED:        ClosedState,
}


# ──────────────────────────────────────────
# State Machine Context
# ──────────────────────────────────────────

class WorkItemStateMachine:
    """
    Context class. Gets the current state object and delegates
    the transition call to it. The ORM model is mutated in place
    so the caller just needs to flush/commit the session.
    """

    def _get_state(self, work_item) -> WorkItemState:
        state_class = STATE_MAP.get(work_item.status)
        if not state_class:
            raise ValueError(f"Unknown WorkItem status: {work_item.status}")
        return state_class()

    def transition(self, work_item, target_status: WorkItemStatus) -> None:
        state = self._get_state(work_item)

        if target_status == WorkItemStatus.INVESTIGATING:
            state.investigate(work_item)
        elif target_status == WorkItemStatus.RESOLVED:
            state.resolve(work_item)
        elif target_status == WorkItemStatus.CLOSED:
            state.close(work_item)
        else:
            raise InvalidStateTransitionError(
                f"Cannot manually transition to status: {target_status}"
            )


# Singleton
state_machine = WorkItemStateMachine()