import asyncio
import uuid
from typing import Any, Dict, List, Tuple

from .db import (
    simple_retrieve,
    create_context_pack,
    save_questions,
)


async def run_ingestion_agent(send_event, session_id: str, tenant_id: str) -> Dict[str, Any]:
    await send_event(session_id, {"type": "agent.status", "status": "running", "task": "ingestion", "agent": "ingestion"})
    # For this POC, ingestion is driven by knowledge.add_source events handled elsewhere.
    # Emit a no-op summary indicating readiness.
    await asyncio.sleep(0.05)
    summary = {"message": "Ingestion ready (sources can be added via knowledge.add_source)", "tenantId": tenant_id}
    await send_event(session_id, {"type": "knowledge.merge.summary", "agent": "ingestion", "summary": summary})
    await send_event(session_id, {"type": "agent.status", "status": "completed", "task": "ingestion", "agent": "ingestion"})
    return summary


async def run_context_agent(send_event, session_id: str, tenant_id: str, query: str = "revenue") -> Dict[str, Any]:
    await send_event(session_id, {"type": "agent.status", "status": "running", "task": "context", "agent": "context"})
    rows = simple_retrieve(tenant_id=tenant_id, query=query, kinds=["enterprise", "customer"], top_k=20)
    pack_id = f"ctx_{uuid.uuid4().hex[:8]}"
    items: List[Tuple[str, float]] = [(r["id"], 1.0) for r in rows]
    create_context_pack(pack_id, tenant_id, task="disclosure_review", filters={"query": query}, items=items)
    await send_event(session_id, {"type": "context.plan", "agent": "context", "query": query, "hits": len(items)})
    await send_event(session_id, {"type": "context.pack.created", "agent": "context", "packId": pack_id, "size": len(items)})
    await send_event(session_id, {"type": "agent.status", "status": "completed", "task": "context", "agent": "context"})
    return {"packId": pack_id, "size": len(items), "rows": rows}


async def run_qa_agent(send_event, session_id: str, context_rows: List[Any]) -> List[Dict[str, Any]]:
    await send_event(session_id, {"type": "agent.status", "status": "running", "task": "qa", "agent": "qa"})
    text_join = " ".join([r["text"] for r in context_rows])
    qlist: List[Dict[str, Any]] = []

    def mkq(txt: str, cat: str, req: bool = True) -> Dict[str, Any]:
        return {"id": f"q_{uuid.uuid4().hex[:8]}", "text": txt, "citations": [], "required": req, "category": cat}

    tj = text_join.lower()
    if "revenue" in tj:
        qlist.append(mkq("Confirm revenue disaggregation by category (e.g., product/region)", "Revenue", True))
        qlist.append(mkq("Disclose contract balances rollforward?", "Revenue", True))
    if "cash" in tj:
        qlist.append(mkq("Does cash note reconcile opening to closing?", "Cash", False))
    if not qlist:
        qlist.append(mkq("List significant accounting policies disclosed", "Policies", False))

    save_questions(session_id, qlist)
    for q in qlist:
        await send_event(session_id, {"type": "question.create", "agent": "qa", "question": q})
        await asyncio.sleep(0.02)
    await send_event(session_id, {"type": "agent.status", "status": "paused", "task": "qa", "agent": "qa", "reason": "awaiting_answers"})
    return qlist

