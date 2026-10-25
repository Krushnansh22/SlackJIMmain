import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy, SearchAttributeKey

with workflow.unsafe.imports_passed_through():
    import config
    from activities import calculate_ticket_energy, generate_ai_fix, log_transition

OPEN = "OPEN"
CLAIMED = "CLAIMED"
RESOLVED = "RESOLVED"

# Custom Search Attributes for high-performance visibility queries
STATUS_KEY = SearchAttributeKey.for_keyword("TicketStatus")
CREATOR_KEY = SearchAttributeKey.for_keyword("CreatorName")
CLAIMED_BY_KEY = SearchAttributeKey.for_keyword("ClaimedBy")


@workflow.defn
class BribeBoardWorkflow:
    """Durable lifecycle of an SOS Ticket: OPEN -> CLAIMED -> RESOLVED.

    Features:
    - Auto-rescue race: Waits for a human claim OR an AUTO_RESCUE_SECONDS durable timer.
      If the timer fires before any human claims, triggers Jarvis Labs GPU AI fix.
    - Atomic Workflow Updates: Prevents claim race conditions between multiple humans or AI.
    - Custom Search Attributes: Fast indexed visibility queries in Temporal Web UI and API.
    - Durable Events Timeline: Full audit trail of status changes, actors, and eco attribution.
    """

    def __init__(self) -> None:
        self.state: Dict[str, Any] = {}
        self._logged_status: Optional[str] = None

    def _add_event(
        self,
        event_type: str,
        actor: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Appends an event to the workflow's durable timeline."""
        event = {
            "timestamp": workflow.now().isoformat(),
            "event_type": event_type,
            "actor": actor,
            "message": message,
            "details": details or {},
        }
        if "events" not in self.state:
            self.state["events"] = []
        self.state["events"].append(event)

    @workflow.run
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        auto_rescue_sec = int(
            params.get("auto_rescue_seconds") or config.AUTO_RESCUE_SECONDS
        )

        self.state = {
            "ticket_id": params["ticket_id"],
            "creator_name": params["creator_name"],
            "raw_transcription": params["raw_transcription"],
            "status": OPEN,
            "claimed_by": None,
            "created_at": params.get("created_at") or workflow.now().isoformat(),
            "claimed_at": None,
            "resolved_at": None,
            "auto_rescue_seconds": auto_rescue_sec,
            "ai_fix": None,
            "energy_attribution": None,
            "events": [],
        }
        self._logged_status = OPEN

        self._add_event(
            event_type="TICKET_CREATED",
            actor=self.state["creator_name"],
            message=f"SOS ticket published: '{self.state['raw_transcription'][:60]}...'",
        )

        # Index initial state into Temporal Search Attributes
        try:
            workflow.upsert_search_attributes(
                [
                    STATUS_KEY.value_set(OPEN),
                    CREATOR_KEY.value_set(self.state["creator_name"]),
                ]
            )
        except Exception:
            pass  # Non-fatal if cluster does not have custom search attributes registered

        await workflow.execute_activity(
            log_transition,
            args=[self.state["ticket_id"], "NONE", OPEN],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # --- PHASE 1: Durable timer vs. Human claim race ---
        # Wait until ticket leaves OPEN, or the auto-rescue timer fires
        try:
            await workflow.wait_condition(
                lambda: self.state["status"] != OPEN,
                timeout=timedelta(seconds=auto_rescue_sec),
                timeout_summary=f"AutoRescueCountdown-{auto_rescue_sec}s",
            )
        except asyncio.TimeoutError:
            pass  # Timer elapsed without a human claim

        # If still OPEN, the timer won the race -> Trigger Jarvis Labs GPU AI rescue
        if self.state["status"] == OPEN:
            workflow.logger.info(
                f"Auto-rescue timer elapsed ({auto_rescue_sec}s). Launching Jarvis Labs AI rescue..."
            )
            self._add_event(
                event_type="TIMER_EXPIRED",
                actor="Temporal Timer",
                message=f"No human claimed within {auto_rescue_sec}s; initiating AI rescue.",
            )

            # Retry policy for external AI activity
            ai_retry_policy = RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                maximum_attempts=3,
                non_retryable_error_types=["ApplicationError"],
            )

            ai_result = await workflow.execute_activity(
                generate_ai_fix,
                args=[self.state["ticket_id"], self.state["raw_transcription"]],
                start_to_close_timeout=timedelta(seconds=25),
                retry_policy=ai_retry_policy,
            )

            self.state["status"] = CLAIMED
            self.state["claimed_by"] = "🤖 Jarvis Labs GPU"
            self.state["claimed_at"] = workflow.now().isoformat()
            self.state["ai_fix"] = ai_result

            self._add_event(
                event_type="AI_FIX_GENERATED",
                actor="🤖 Jarvis Labs GPU",
                message="Diagnostic fix generated on Jarvis Labs GPU instance.",
                details={
                    "model": ai_result.get("model"),
                    "latency_ms": ai_result.get("latency_ms"),
                    "gpu_estimate_mwh": ai_result.get("gpu_estimate_mwh"),
                },
            )

            try:
                workflow.upsert_search_attributes(
                    [
                        STATUS_KEY.value_set(CLAIMED),
                        CLAIMED_BY_KEY.value_set("🤖 Jarvis Labs GPU"),
                    ]
                )
            except Exception:
                pass

            old_st, self._logged_status = self._logged_status, CLAIMED
            await workflow.execute_activity(
                log_transition,
                args=[self.state["ticket_id"], old_st or OPEN, CLAIMED],
                start_to_close_timeout=timedelta(seconds=10),
            )

        # --- PHASE 2: Wait for ticket resolution ---
        await workflow.wait_condition(lambda: self.state["status"] == RESOLVED)

        # Execute energy attribution calculation across the ticket's active lifecycle
        inf_seconds = (
            self.state["ai_fix"].get("inference_seconds", 0.0)
            if self.state.get("ai_fix")
            else 0.0
        )
        try:
            energy_result = await workflow.execute_activity(
                calculate_ticket_energy,
                args=[
                    self.state["ticket_id"],
                    self.state["created_at"],
                    self.state["resolved_at"] or workflow.now().isoformat(),
                    inf_seconds,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self.state["energy_attribution"] = energy_result
        except Exception as e:
            workflow.logger.warning(f"Could not calculate ticket energy: {e}")

        self._add_event(
            event_type="TICKET_RESOLVED",
            actor=self.state.get("resolved_by", self.state["creator_name"]),
            message="Ticket marked resolved; coffee bounty delivered.",
            details=self.state.get("energy_attribution") or {},
        )

        try:
            workflow.upsert_search_attributes([STATUS_KEY.value_set(RESOLVED)])
        except Exception:
            pass

        old_st, self._logged_status = self._logged_status, RESOLVED
        await workflow.execute_activity(
            log_transition,
            args=[self.state["ticket_id"], old_st or CLAIMED, RESOLVED],
            start_to_close_timeout=timedelta(seconds=10),
        )

        return self.state

    # --- ATOMIC WORKFLOW UPDATES ---

    @workflow.update
    async def claim(self, claimer_name: str) -> Dict[str, Any]:
        """Atomically claims the ticket for a human rescuer, canceling auto-rescue."""
        cleaned_name = claimer_name.strip()
        old_status = self.state["status"]
        self.state["status"] = CLAIMED
        self.state["claimed_by"] = cleaned_name
        self.state["claimed_at"] = workflow.now().isoformat()

        self._add_event(
            event_type="CLAIMED_BY_HUMAN",
            actor=cleaned_name,
            message=f"SOS ticket claimed by rescuer {cleaned_name}.",
        )

        try:
            workflow.upsert_search_attributes(
                [
                    STATUS_KEY.value_set(CLAIMED),
                    CLAIMED_BY_KEY.value_set(cleaned_name),
                ]
            )
        except Exception:
            pass

        return self.state

    @claim.validator
    def validate_claim(self, claimer_name: str) -> None:
        """Validates that the ticket is still OPEN and claimer is not the creator."""
        if not claimer_name or not claimer_name.strip():
            raise ValueError("Rescuer name cannot be empty.")
        current_status = self.state.get("status")
        if current_status != OPEN:
            raise ValueError(
                f"Ticket is no longer open (current status: '{current_status}'). "
                f"Claimed by: {self.state.get('claimed_by', 'unknown')}."
            )
        creator = self.state.get("creator_name", "").strip().lower()
        if creator == claimer_name.strip().lower():
            raise ValueError("You cannot claim your own SOS ticket.")

    @workflow.update
    async def resolve(self, resolver_name: str) -> Dict[str, Any]:
        """Atomically marks the ticket as resolved."""
        cleaned_name = resolver_name.strip()
        self.state["status"] = RESOLVED
        self.state["resolved_by"] = cleaned_name
        self.state["resolved_at"] = workflow.now().isoformat()
        return self.state

    @resolve.validator
    def validate_resolve(self, resolver_name: str) -> None:
        """Validates that ticket is CLAIMED and resolver is creator."""
        if not resolver_name or not resolver_name.strip():
            raise ValueError("Resolver name cannot be empty.")
        current_status = self.state.get("status")
        if current_status != CLAIMED:
            raise ValueError(
                f"Ticket cannot be resolved: status is '{current_status}' (must be CLAIMED)."
            )
        creator = self.state.get("creator_name", "").strip().lower()
        if creator != resolver_name.strip().lower():
            raise ValueError("Only the ticket creator can mark this SOS as resolved.")

    # --- SIGNALS FOR BACKWARD COMPATIBILITY ---

    @workflow.signal
    def claim_signal(self, claimer_name: str) -> None:
        if self.state.get("status") == OPEN:
            self.state["status"] = CLAIMED
            self.state["claimed_by"] = claimer_name.strip()
            self.state["claimed_at"] = workflow.now().isoformat()
            self._add_event("CLAIMED_BY_HUMAN", claimer_name.strip(), "Claimed via signal")

    @workflow.signal
    def resolve_signal(self) -> None:
        if self.state.get("status") == CLAIMED:
            self.state["status"] = RESOLVED
            self.state["resolved_at"] = workflow.now().isoformat()
            self._add_event("RESOLVED", "Creator", "Resolved via signal")

    # --- QUERIES ---

    @workflow.query
    def get_state(self) -> Dict[str, Any]:
        return self.state

    @workflow.query
    def get_events(self) -> List[Dict[str, Any]]:
        return self.state.get("events", [])
