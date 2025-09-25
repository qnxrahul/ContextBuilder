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
from .db import init_db, persist_event, upsert_source, insert_chunks, simple_retrieve, create_context_pack, save_questions, save_answer, save_workflow, save_usage_metrics
from .agents import run_ingestion_agent, run_context_agent, run_qa_agent

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
session_states: Dict[str, Dict[str, Any]] = {}


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
    state = session_states.setdefault(session_id, {"stage": "idle", "paused": False, "cancelled": False, "weights": {}})
    await send_event(session_id, {"type": "agent.status", "status": "running", "task": "disclosure_review", "agent": "orchestrator"})
    state.update({"stage": "ingestion"})
    await run_ingestion_agent(send_event, session_id, tenant_id)
    if state.get("cancelled"):
        await send_event(session_id, {"type": "agent.status", "status": "cancelled", "task": "disclosure_review", "agent": "orchestrator"})
        return
    state.update({"stage": "context"})
    ctx = await run_context_agent(send_event, session_id, tenant_id, query=query)
    if state.get("cancelled"):
        await send_event(session_id, {"type": "agent.status", "status": "cancelled", "task": "disclosure_review", "agent": "orchestrator"})
        return
    state.update({"stage": "qa"})
    qlist = await run_qa_agent(send_event, session_id, ctx.get("rows", []))
    questions_by_session[session_id] = qlist


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
    # naive usage estimation: AG-UI packs keep prompts short; baseline assumes raw doc prompt
    # For demo purposes, estimate tokens by text lengths
    qs = questions_by_session.get(session_id) or []
    answers = answers_by_session.get(session_id) or {}
    num_q = len(qs)
    num_ans = len(answers)
    agui_prompt_tokens = max(50, num_q * 20)  # compact prompts per question
    agui_output_tokens = max(100, num_ans * 30)
    baseline_prompt_tokens = max(500, num_q * 150)  # long raw-doc prompts
    baseline_output_tokens = agui_output_tokens  # similar answers length
    save_usage_metrics(session_id, agui_prompt_tokens, agui_output_tokens, baseline_prompt_tokens, baseline_output_tokens)
    await send_event(session_id, {
        "type": "metrics.usage",
        "sessionId": session_id,
        "agui": {"prompt": agui_prompt_tokens, "output": agui_output_tokens},
        "baseline": {"prompt": baseline_prompt_tokens, "output": baseline_output_tokens}
    })


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
            elif event_type in ("interrupt.pause", "agent.pause"):
                st = session_states.setdefault(session_id, {"stage": "idle", "paused": False, "cancelled": False, "weights": {}})
                st["paused"] = True
                await send_event(session_id, {"type": "agent.status", "status": "paused", "task": st.get("stage"), "agent": "orchestrator", "reason": "user_interrupt"})
            elif event_type in ("interrupt.resume", "agent.resume"):
                st = session_states.setdefault(session_id, {"stage": "idle", "paused": False, "cancelled": False, "weights": {}})
                st["paused"] = False
                await send_event(session_id, {"type": "agent.status", "status": "running", "task": st.get("stage"), "agent": "orchestrator"})
                # If currently in QA stage, attempt to build workflow now
                if st.get("stage") == "qa":
                    await maybe_emit_workflow(session_id)
            elif event_type in ("agent.cancel", "interrupt.cancel"):
                st = session_states.setdefault(session_id, {"stage": "idle", "paused": False, "cancelled": False, "weights": {}})
                st["cancelled"] = True
                await send_event(session_id, {"type": "agent.status", "status": "cancelled", "task": st.get("stage"), "agent": "orchestrator"})
            elif event_type == "widget.patch":
                # apply minimal patch to workflow widgets
                wf = workflow_by_session.get(session_id)
                if wf:
                    patch = data.get("patch", {})
                    for w in wf.get("widgets", []):
                        if w.get("id") == patch.get("id"):
                            w.update(patch.get("changes", {}))
                    await send_event(session_id, {"type": "workflow.update", "workflow": wf})
            elif event_type == "user.answer":
                # Accept answers via WS (AG-UI style)
                qid = data.get("questionId")
                answer_text = data.get("answer")
                if qid and answer_text is not None:
                    qs = questions_by_session.get(session_id) or []
                    q_meta = next((q for q in qs if q.get("id") == qid), None)
                    if session_id not in answers_by_session:
                        answers_by_session[session_id] = {}
                    answers_by_session[session_id][qid] = {
                        "answer": answer_text,
                        "required": bool(q_meta and q_meta.get("required")),
                        "category": q_meta.get("category") if q_meta else None,
                    }
                    await send_event(session_id, {"type": "question.answered", "questionId": qid})
            elif event_type == "context.weights.update":
                st = session_states.setdefault(session_id, {"stage": "idle", "paused": False, "cancelled": False, "weights": {}})
                st["weights"] = data.get("weights", {})
                await send_event(session_id, {"type": "context.plan", "agent": "context", "weights": st["weights"]})
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
