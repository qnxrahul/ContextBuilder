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


async def simulate_disclosure_review(session_id: str, filename: str) -> None:
    # Simulate event stream for POC
    await send_event(session_id, {"type": "agent.status", "status": "running", "task": "disclosure_review"})
    await asyncio.sleep(0.2)
    sample_questions = [
        {
            "id": f"q_{uuid.uuid4().hex[:8]}",
            "text": "Confirm whether revenue is disaggregated by significant categories (e.g., product, region)",
            "citations": [{"sourceId": "enterprise_ifrs15", "page": 34}],
            "required": True,
            "category": "Revenue",
        },
        {
            "id": f"q_{uuid.uuid4().hex[:8]}",
            "text": "Are contract balances (contract assets and liabilities) disclosed with rollforwards?",
            "citations": [{"sourceId": "enterprise_ifrs15", "page": 56}],
            "required": True,
            "category": "Revenue",
        },
        {
            "id": f"q_{uuid.uuid4().hex[:8]}",
            "text": "Does Note X reconcile opening to closing cash and equivalents?",
            "citations": [{"sourceId": "customer_fs_pdf", "page": 12}],
            "required": False,
            "category": "Cash",
        },
    ]
    questions_by_session[session_id] = sample_questions
    for q in sample_questions:
        await send_event(session_id, {"type": "question.create", "question": q})
        await asyncio.sleep(0.1)

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
    background_tasks.add_task(simulate_disclosure_review, sessionId, file.filename)
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
                if task == "disclosure_review":
                    asyncio.create_task(simulate_disclosure_review(session_id, filename="uploaded"))
            elif event_type == "widget.patch":
                # apply minimal patch to workflow widgets
                wf = workflow_by_session.get(session_id)
                if wf:
                    patch = data.get("patch", {})
                    for w in wf.get("widgets", []):
                        if w.get("id") == patch.get("id"):
                            w.update(patch.get("changes", {}))
                    await send_event(session_id, {"type": "workflow.update", "workflow": wf})
            else:
                # echo unknown
                await send_event(session_id, {"type": "echo", "data": data})
    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup
        if sessions.get(session_id) is ws:
            sessions.pop(session_id, None)
