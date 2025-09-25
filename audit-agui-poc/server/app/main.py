import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi import BackgroundTasks
from fastapi import HTTPException
from fastapi import APIRouter
from pathlib import Path
from .db import init_db, persist_event, upsert_source, insert_chunks, simple_retrieve, create_context_pack, save_questions, save_answer, save_workflow

app = FastAPI(title="Audit AG-UI POC")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
init_db()

# In-memory session and state stores for POC
sessions: Dict[str, WebSocket] = {}
questions_by_session: Dict[str, List[Dict[str, Any]]] = {}
answers_by_session: Dict[str, Dict[str, Any]] = {}
workflow_by_session: Dict[str, Dict[str, Any]] = {}


async def send_event(session_id: str, event: Dict[str, Any]) -> None:
    ws = sessions.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_text(json.dumps(event))
    except RuntimeError:
        pass
    try:
        persist_event(session_id, event.get("type", "unknown"), event)
    except Exception:
        pass


async def orchestrate_disclosure_review(session_id: str, tenant_id: str, query: str = "revenue") -> None:
    await send_event(session_id, {"type": "agent.status", "status": "running", "task": "disclosure_review"})
    # Build context pack from both enterprise and customer kinds
    rows = simple_retrieve(tenant_id=tenant_id, query=query, kinds=["enterprise", "customer"], top_k=20)
    pack_id = f"ctx_{uuid.uuid4().hex[:8]}"
    items = [(r["id"], 1.0) for r in rows]
    create_context_pack(pack_id, tenant_id, task="disclosure_review", filters={"query": query}, items=items)
    await send_event(session_id, {"type": "context.pack.created", "packId": pack_id, "size": len(items)})

    # Generate minimal questions based on presence of certain keywords
    qlist: List[Dict[str, Any]] = []
    def mkq(txt: str, cat: str, req: bool = True) -> Dict[str, Any]:
        return {"id": f"q_{uuid.uuid4().hex[:8]}", "text": txt, "citations": [], "required": req, "category": cat}

    text_join = " ".join([r["text"] for r in rows])
    if "revenue" in text_join.lower():
        qlist.append(mkq("Confirm revenue disaggregation by category (e.g., product/region)", "Revenue", True))
        qlist.append(mkq("Disclose contract balances rollforward?", "Revenue", True))
    if "cash" in text_join.lower():
        qlist.append(mkq("Does cash note reconcile opening to closing?", "Cash", False))
    if not qlist:
        qlist.append(mkq("List significant accounting policies disclosed", "Policies", False))

    questions_by_session[session_id] = qlist
    save_questions(session_id, qlist)
    for q in qlist:
        await send_event(session_id, {"type": "question.create", "question": q})
        await asyncio.sleep(0.05)
    await send_event(session_id, {"type": "agent.status", "status": "paused", "reason": "awaiting_answers"})


async def maybe_emit_workflow(session_id: str) -> None:
    qs = questions_by_session.get(session_id) or []
    ans = answers_by_session.get(session_id) or {}
    if not qs:
        return
    # Simple condition: if at least one required answered, build workflow
    answered_required = [a for a in ans.values() if a.get("required")]
    if len(answered_required) == 0:
        return

    workflow = {
        "id": f"wf_{uuid.uuid4().hex[:8]}",
        "title": "Disclosure Review Workflow",
        "nodes": [
            {"id": "n_start", "type": "task", "title": "Start", "assigneeRole": "Senior"},
            {"id": "n_rev", "type": "task", "title": "Review Revenue Disclosures", "assigneeRole": "Staff"},
            {"id": "n_cash", "type": "task", "title": "Verify Cash Note Reconciliation", "assigneeRole": "Staff"},
            {"id": "n_sign", "type": "approval", "title": "Senior Review", "assigneeRole": "Senior"},
        ],
        "edges": [
            {"from": "n_start", "to": "n_rev"},
            {"from": "n_rev", "to": "n_cash"},
            {"from": "n_cash", "to": "n_sign"},
        ],
        "widgets": [
            {
                "id": "w_rev_chart",
                "type": "chart",
                "title": "Revenue Disaggregation",
                "params": {"by": "region", "period": "FY24"},
                "editable": True,
                "dataRefs": [{"packId": "ctx_demo", "chunkIds": ["c1", "c2"]}],
                "citations": [{"sourceId": "enterprise_ifrs15", "page": 34}],
            }
        ],
    }
    workflow_by_session[session_id] = workflow
    save_workflow(session_id, workflow["id"], workflow)
    await send_event(session_id, {"type": "workflow.create", "workflow": workflow})


@router.post("/sessions")
async def create_session() -> Dict[str, str]:
    session_id = uuid.uuid4().hex
    return {"sessionId": session_id}


@router.post("/files")
async def upload_file(background_tasks: BackgroundTasks, sessionId: str = Form(...), file: UploadFile = File(...)):
    if not sessionId:
        raise HTTPException(status_code=400, detail="sessionId required")
    dest = UPLOADS_DIR / f"{sessionId}_{file.filename}"
    content = await file.read()
    dest.write_bytes(content)
    # Notify via event and simulate processing
    background_tasks.add_task(send_event, sessionId, {"type": "file.uploaded", "filename": file.filename})
    return {"ok": True, "path": str(dest)}


@router.post("/questions/{question_id}/answers")
async def answer_question(question_id: str, payload: Dict[str, Any]):
    session_id = payload.get("sessionId")
    answer_text = payload.get("answer")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId required")
    # Find question to attach metadata
    qs = questions_by_session.get(session_id) or []
    q_meta: Optional[Dict[str, Any]] = next((q for q in qs if q.get("id") == question_id), None)
    if session_id not in answers_by_session:
        answers_by_session[session_id] = {}
    answers_by_session[session_id][question_id] = {
        "answer": answer_text,
        "required": bool(q_meta and q_meta.get("required")),
        "category": q_meta.get("category") if q_meta else None,
    }
    save_answer(session_id, question_id, answer_text or "", {"required": answers_by_session[session_id][question_id]["required"], "category": answers_by_session[session_id][question_id]["category"]})
    await send_event(session_id, {"type": "question.answered", "questionId": question_id})
    await maybe_emit_workflow(session_id)
    return {"ok": True}


@router.get("/workflow/latest")
async def get_latest_workflow(sessionId: str):
    wf = workflow_by_session.get(sessionId)
    if not wf:
        raise HTTPException(status_code=404, detail="no workflow for session")
    return wf


app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/events")
async def events(ws: WebSocket):
    await ws.accept()
    # Expect a handshake with sessionId as first message, or query param
    params = dict(ws.query_params)
    session_id = params.get("sessionId")
    if not session_id:
        # fallback to first json message
        try:
            init = await ws.receive_json()
            session_id = init.get("sessionId")
        except Exception:
            await ws.close()
            return
    sessions[session_id] = ws
    try:
        await ws.send_text(json.dumps({"type": "session.start.ack", "sessionId": session_id}))
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue
            event_type = data.get("type")
            if event_type == "agent.run":
                task = data.get("task")
                tenant = data.get("tenantId", "tenant_demo")
                if task == "disclosure_review":
                    asyncio.create_task(orchestrate_disclosure_review(session_id, tenant_id=tenant, query=data.get("query", "revenue")))
            elif event_type == "widget.patch":
                # apply minimal patch to workflow widgets
                wf = workflow_by_session.get(session_id)
                if wf:
                    patch = data.get("patch", {})
                    for w in wf.get("widgets", []):
                        if w.get("id") == patch.get("id"):
                            w.update(patch.get("changes", {}))
                    await send_event(session_id, {"type": "workflow.update", "workflow": wf})
            elif event_type == "knowledge.add_source":
                # Persist a source and its naive chunks
                tenant = data.get("tenantId", "tenant_demo")
                source = data.get("source", {})
                source_id = source.get("id", f"src_{uuid.uuid4().hex[:8]}")
                kind = source.get("kind", "enterprise")
                title = source.get("title", "Untitled")
                text = source.get("text", "")
                upsert_source(source_id, tenant, kind, title, {k: v for k, v in source.items() if k not in {"id", "kind", "title", "text"}})
                # simple chunking by paragraphs
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                chunk_rows = []
                for idx, para in enumerate(paragraphs):
                    cid = f"ck_{uuid.uuid4().hex[:8]}"
                    chunk_rows.append((cid, idx, para, {"sourceTitle": title}))
                insert_chunks(source_id, chunk_rows)
                await send_event(session_id, {"type": "knowledge.indexed", "sourceId": source_id, "chunks": len(chunk_rows)})
            else:
                # echo unknown
                await send_event(session_id, {"type": "echo", "data": data})
    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup
        if sessions.get(session_id) is ws:
            sessions.pop(session_id, None)
