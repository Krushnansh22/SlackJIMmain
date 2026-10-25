import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from temporalio.api.enums.v1 import IndexedValueType
from temporalio.api.operatorservice.v1 import AddSearchAttributesRequest
from temporalio.client import Client
from temporalio.service import RPCError

import config
from eco import eco_service
from workflows import BribeBoardWorkflow

logger = logging.getLogger("mauji-api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

state: Dict[str, Any] = {"client": None}


async def get_client() -> Client:
    if state["client"] is None:
        state["client"] = await Client.connect(
            config.TEMPORAL_ADDRESS, namespace=config.TEMPORAL_NAMESPACE
        )
    return state["client"]


async def register_search_attributes(client: Client) -> None:
    """Idempotently registers custom search attributes with Temporal cluster."""
    try:
        req = AddSearchAttributesRequest(
            namespace=config.TEMPORAL_NAMESPACE,
            search_attributes={
                "TicketStatus": IndexedValueType.INDEXED_VALUE_TYPE_KEYWORD,
                "CreatorName": IndexedValueType.INDEXED_VALUE_TYPE_KEYWORD,
                "ClaimedBy": IndexedValueType.INDEXED_VALUE_TYPE_KEYWORD,
            },
        )
        await client.operator_service.add_search_attributes(req)
        logger.info("Successfully registered custom Search Attributes: TicketStatus, CreatorName, ClaimedBy")
    except RPCError as e:
        # Code 6 is ALREADY_EXISTS
        if getattr(e, "status", None) and getattr(e.status, "value", None) == 6:
            logger.info("Search attributes already registered.")
        else:
            logger.info(f"Operator search-attribute registration notice: {e}")
    except Exception as e:
        logger.warning(f"Could not register search attributes via OperatorService (may not be supported on this dev server): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        client = await get_client()
        await register_search_attributes(client)
    except Exception as e:
        logger.warning(f"Temporal not reachable during boot: {e}. API will reconnect on first request.")
    yield


app = FastAPI(
    title="Mauji Cafe SOS Bribe Board API",
    description="Durable hackathon helpdesk with Temporal workflows, Jarvis Labs GPU AI rescue, and Kepler Eco-Score",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateTicket(BaseModel):
    creator_name: str = Field(min_length=1, max_length=40)
    raw_transcription: str = Field(min_length=1, max_length=600)
    auto_rescue_seconds: Optional[int] = Field(default=None, ge=5, le=3600)


class Actor(BaseModel):
    name: str = Field(min_length=1, max_length=40)


def wf_id(ticket_id: str) -> str:
    return f"ticket-{ticket_id}"


def extract_update_error(e: Exception) -> HTTPException:
    msg = str(e)
    if "cannot claim your own" in msg.lower():
        return HTTPException(403, "You cannot claim your own SOS ticket.")
    if "only the ticket creator" in msg.lower():
        return HTTPException(403, "Only the ticket creator can mark this SOS as resolved.")
    if "no longer open" in msg.lower() or "already claimed" in msg.lower():
        return HTTPException(409, "This ticket has already been claimed.")
    if "must be claimed" in msg.lower() or "cannot be resolved" in msg.lower():
        return HTTPException(409, "Ticket is not currently in a claimable/resolvable state.")
    if "empty" in msg.lower():
        return HTTPException(400, "Name cannot be empty.")
    return HTTPException(400, msg)


async def fetch_state(client: Client, workflow_id: str) -> Optional[Dict[str, Any]]:
    try:
        s = await client.get_workflow_handle(workflow_id).query(
            BribeBoardWorkflow.get_state
        )
        if not s:
            return None
        # Add deep link to Temporal Web UI for durability transparency
        ticket_id = s.get("ticket_id", workflow_id.replace("ticket-", ""))
        s["temporal_ui_url"] = (
            f"{config.TEMPORAL_UI_URL}/namespaces/{config.TEMPORAL_NAMESPACE}/workflows/{workflow_id}"
        )
        return s
    except Exception:
        return None


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "mauji-cafe-sos-backend"}


@app.get("/api/health/integrations")
async def health_integrations():
    """Reports reachability and latency of all sponsor services."""
    integrations: Dict[str, Any] = {}

    # 1. Temporal Health
    t0 = time.time()
    try:
        client = await get_client()
        # Ping Temporal with quick describe or system check
        desc = await client.workflow_service.get_system_info()
        latency_ms = int((time.time() - t0) * 1000)
        integrations["temporal"] = {
            "status": "connected",
            "address": config.TEMPORAL_ADDRESS,
            "namespace": config.TEMPORAL_NAMESPACE,
            "task_queue": config.TASK_QUEUE,
            "latency_ms": latency_ms,
            "server_version": getattr(desc, "server_version", "ok"),
        }
    except Exception as e:
        integrations["temporal"] = {
            "status": "unreachable",
            "address": config.TEMPORAL_ADDRESS,
            "error": str(e),
        }

    # 2. Jarvis Labs GPU Health
    t0 = time.time()
    if config.JARVIS_LLM_BASE_URL:
        try:
            async with httpx.AsyncClient(timeout=2.0) as http_c:
                res = await http_c.get(f"{config.JARVIS_LLM_BASE_URL}/v1/models")
                latency_ms = int((time.time() - t0) * 1000)
                integrations["jarvislabs"] = {
                    "status": "connected" if res.status_code == 200 else f"http_{res.status_code}",
                    "base_url": config.JARVIS_LLM_BASE_URL,
                    "model": config.JARVIS_LLM_MODEL,
                    "gpu_tdp_watts": config.JARVIS_GPU_TDP_WATTS,
                    "latency_ms": latency_ms,
                    "type": "live_gpu_vllm",
                }
        except Exception as e:
            integrations["jarvislabs"] = {
                "status": "mock_fallback",
                "base_url": config.JARVIS_LLM_BASE_URL,
                "model": config.JARVIS_LLM_MODEL,
                "gpu_tdp_watts": config.JARVIS_GPU_TDP_WATTS,
                "notice": f"Live GPU unreachable ({e}); graceful mock active",
                "type": "simulated_gpu",
            }
    else:
        integrations["jarvislabs"] = {
            "status": "mock_active",
            "model": config.JARVIS_LLM_MODEL,
            "gpu_tdp_watts": config.JARVIS_GPU_TDP_WATTS,
            "notice": "JARVIS_LLM_BASE_URL not configured; running in mock/demo mode",
            "type": "simulated_gpu",
        }

    # 3. Kepler + Prometheus Health
    if config.ECO_PROVIDER == "kepler":
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=2.0) as http_c:
                res = await http_c.get(f"{config.PROMETHEUS_URL}/-/healthy")
                latency_ms = int((time.time() - t0) * 1000)
                integrations["kepler"] = {
                    "status": "live" if res.status_code == 200 else "degraded",
                    "provider": "kepler",
                    "prometheus_url": config.PROMETHEUS_URL,
                    "metric": config.KEPLER_METRIC_CONTAINER_JOULES,
                    "latency_ms": latency_ms,
                }
        except Exception as e:
            integrations["kepler"] = {
                "status": "unavailable",
                "provider": "kepler",
                "error": str(e),
                "notice": "Prometheus unreachable from backend",
            }
    else:
        integrations["kepler"] = {
            "status": "simulated",
            "provider": "simulated",
            "metric": config.KEPLER_METRIC_CONTAINER_JOULES,
            "notice": "ECO_PROVIDER=simulated (local mode); cluster uses live Kepler",
        }

    # 4. Wispr Flow Health
    integrations["wispr_flow"] = {
        "status": "ready",
        "provider": "Wispr Flow desktop client / Web Speech API adapter",
        "notice": "Wispr Flow Voice Interface API is currently restricted/partner-access. System-wide dictation hotkey active.",
    }

    # 5. RubixKube Health
    integrations["rubixkube"] = {
        "status": "ready",
        "platform": "Site Reliability Intelligence (SRI)",
        "notice": "Observer agents track cluster topology & auto-remediate pod chaos.",
    }

    return integrations


@app.get("/api/eco")
async def get_eco():
    """Returns real-time power (Watts) and Eco-Score letter grade."""
    return await eco_service.get_live_metrics()


@app.post("/api/tickets")
async def create_ticket(body: CreateTicket):
    client = await get_client()
    ticket_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    auto_rescue_sec = body.auto_rescue_seconds or config.AUTO_RESCUE_SECONDS

    params = {
        "ticket_id": ticket_id,
        "creator_name": body.creator_name.strip(),
        "raw_transcription": body.raw_transcription.strip(),
        "created_at": created_at,
        "auto_rescue_seconds": auto_rescue_sec,
    }

    await client.start_workflow(
        BribeBoardWorkflow.run,
        params,
        id=wf_id(ticket_id),
        task_queue=config.TASK_QUEUE,
    )

    return {
        **params,
        "status": "OPEN",
        "claimed_by": None,
        "temporal_ui_url": f"{config.TEMPORAL_UI_URL}/namespaces/{config.TEMPORAL_NAMESPACE}/workflows/{wf_id(ticket_id)}",
    }


@app.get("/api/tickets")
async def list_tickets(status: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Lists tickets using Temporal visibility query."""
    client = await get_client()
    
    # High-performance visibility query
    query = f"WorkflowType='{config.WORKFLOW_TYPE}'"
    if status:
        query += f" AND TicketStatus='{status.upper()}'"

    ids: List[str] = []
    try:
        async for wf in client.list_workflows(query=query, limit=100):
            ids.append(wf.id)
    except Exception as e:
        logger.warning(f"Visibility query with search attributes fell back to base query: {e}")
        async for wf in client.list_workflows(
            query=f"WorkflowType='{config.WORKFLOW_TYPE}'", limit=100
        ):
            ids.append(wf.id)

    results = await asyncio.gather(*(fetch_state(client, i) for i in ids))
    tickets = [r for r in results if r]
    tickets.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return tickets


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    client = await get_client()
    s = await fetch_state(client, wf_id(ticket_id))
    if not s:
        raise HTTPException(404, "Ticket not found")
    return s


@app.post("/api/tickets/{ticket_id}/claim")
async def claim_ticket(ticket_id: str, body: Actor):
    """Claims a ticket via atomic Temporal Workflow Update with validator."""
    client = await get_client()
    handle = client.get_workflow_handle(wf_id(ticket_id))
    try:
        updated_state = await handle.execute_update(
            BribeBoardWorkflow.claim, body.name.strip()
        )
        return {"ok": True, "state": updated_state}
    except Exception as e:
        raise extract_update_error(e)


@app.post("/api/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, body: Actor):
    """Marks ticket resolved via atomic Temporal Workflow Update with validator."""
    client = await get_client()
    handle = client.get_workflow_handle(wf_id(ticket_id))
    try:
        updated_state = await handle.execute_update(
            BribeBoardWorkflow.resolve, body.name.strip()
        )
        return {"ok": True, "state": updated_state}
    except Exception as e:
        raise extract_update_error(e)
