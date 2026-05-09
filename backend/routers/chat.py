"""对话接口 — SSE 流式对话 + 非流式补全 + 对话历史管理."""

import asyncio
import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent.graph import run_agent
from backend.memory.store import memory_store

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    thread_id: str = ""
    history: list[dict] = []


class CitationDict(BaseModel):
    index: int
    source: str
    detail: str


class AnomalyDict(BaseModel):
    metric: str
    value: str
    change: str
    description: str


class CreateConversationRequest(BaseModel):
    id: str = ""
    title: str = "新对话"


class UpdateTitleRequest(BaseModel):
    title: str


class AddMessageRequest(BaseModel):
    role: str
    content: str
    reasoning: list[str] = []
    citations: list[dict] = []
    anomalies: list[dict] = []
    chart_data: Optional[str] = None


def _parse_citations(raw: Any) -> list[dict]:
    """将 Citation 对象或 dict 统一为 dict."""
    result = []
    for c in (raw or []):
        if hasattr(c, "index"):
            result.append({"index": c.index, "source": c.source, "detail": c.detail})
        elif isinstance(c, dict):
            result.append(c)
    return result


def _parse_anomalies(raw: Any) -> list[dict]:
    """将 Anomaly 对象或 dict 统一为 dict."""
    result = []
    for a in (raw or []):
        if hasattr(a, "metric"):
            result.append({
                "metric": a.metric, "value": a.value,
                "change": a.change, "description": a.description,
            })
        elif isinstance(a, dict):
            result.append(a)
    return result


async def _stream_events(message: str, thread_id: str, history: list[dict]):
    """运行 Agent 并将结果以 SSE 事件流的形式推送."""

    yield {"event": "step", "data": json.dumps({"step": "classifying", "detail": "正在分析意图..."})}

    try:
        result = run_agent(message, thread_id=thread_id, history=history)
    except Exception as e:
        yield {"event": "error", "data": json.dumps({"error": str(e)})}
        return

    # 思考步骤
    steps = result.get("streaming_steps", [])
    for s in steps:
        yield {"event": "step", "data": json.dumps({"step": "executing", "detail": s})}

    # 引用
    citations = _parse_citations(result.get("citations", []))
    for c in citations:
        yield {"event": "citation", "data": json.dumps(c)}

    # 异常
    anomalies = _parse_anomalies(result.get("anomalies", []))
    for a in anomalies:
        yield {"event": "anomaly", "data": json.dumps(a)}

    # 数据状态
    for s in result.get("data_status", []):
        yield {"event": "status", "data": json.dumps({"message": s})}

    # ── 股价图表数据 ──
    for r in result.get("tool_results", []):
        if r.get("tool") == "get_stock_price" and r.get("status") == "ok" and r.get("data"):
            yield {"event": "chart", "data": json.dumps({"type": "line", "data": r["data"]})}

    # 答案正文（逐块流式输出，模拟打字效果）
    answer = result.get("final_answer") or ""
    chunk_size = 3
    for i in range(0, len(answer), chunk_size):
        yield {"event": "token", "data": json.dumps({"content": answer[i:i+chunk_size]})}
        await asyncio.sleep(0.008)

    # ── 保存笔记确认提示 ──
    note_info = result.get("note_info")
    if note_info:
        yield {"event": "save_prompt", "data": json.dumps(note_info)}

    yield {"event": "done", "data": json.dumps({"message_id": str(uuid.uuid4())})}


@router.post("/stream")
async def chat_stream(body: ChatRequest):
    """SSE 流式对话接口."""
    thread_id = body.thread_id or str(uuid.uuid4())

    async def generate():
        async for ev in _stream_events(body.message, thread_id, body.history):
            yield f"event: {ev['event']}\ndata: {ev['data']}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/completion")
async def chat_completion(body: ChatRequest):
    """非流式对话接口（备选）. """
    thread_id = body.thread_id or str(uuid.uuid4())
    try:
        result = run_agent(body.message, thread_id=thread_id, history=body.history)
        return {
            "message_id": str(uuid.uuid4()),
            "content": result.get("final_answer", ""),
            "steps": result.get("streaming_steps", []),
            "citations": _parse_citations(result.get("citations", [])),
            "anomalies": _parse_anomalies(result.get("anomalies", [])),
            "data_status": result.get("data_status", []),
        }
    except Exception as e:
        return {"error": str(e)}


# ────────── 对话历史 CRUD ──────────

@router.get("/conversations")
def list_conversations():
    """获取对话列表."""
    memory_store.connect()
    convs = memory_store.list_conversations()
    return {"conversations": convs}


@router.post("/conversations")
def create_conversation(body: CreateConversationRequest):
    """创建新对话."""
    memory_store.connect()
    cid = memory_store.create_conversation(conv_id=body.id or None, title=body.title)
    conv = memory_store.get_conversation(cid)
    return {"conversation": conv}


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str):
    """获取对话详情（含消息）. """
    memory_store.connect()
    conv = memory_store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "对话不存在")
    messages = memory_store.get_messages(conv_id)
    return {"conversation": conv, "messages": messages}


@router.put("/conversations/{conv_id}")
def update_conversation(conv_id: str, body: UpdateTitleRequest):
    """更新对话标题."""
    memory_store.connect()
    memory_store.update_conversation_title(conv_id, body.title)
    return {"status": "ok"}


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """删除对话."""
    memory_store.connect()
    memory_store.delete_conversation(conv_id)
    return {"status": "ok"}


@router.post("/conversations/{conv_id}/messages")
def add_message(conv_id: str, body: AddMessageRequest):
    """向对话追加消息."""
    memory_store.connect()
    msg_id = memory_store.add_message(
        conv_id=conv_id,
        role=body.role,
        content=body.content,
        reasoning=body.reasoning,
        citations=body.citations,
        anomalies=body.anomalies,
        chart_data=body.chart_data,
    )
    return {"message_id": msg_id}


@router.post("/conversations/{conv_id}/generate-title")
def generate_conversation_title(conv_id: str):
    """用 LLM 为对话生成标题."""
    memory_store.connect()
    messages = memory_store.get_messages(conv_id)
    if not messages:
        return {"title": "新对话"}

    # 取前几轮内容作为上下文
    context_parts = []
    for m in messages[:6]:
        role = "用户" if m["role"] == "user" else "AI"
        text = (m.get("content") or "")[:100]
        if text.strip():
            context_parts.append(f"{role}: {text}")

    if not context_parts:
        return {"title": "新对话"}

    context = "\n".join(context_parts)
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        from backend.config import settings
        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.3,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            timeout=15,
        )
        prompt = f"""根据以下对话内容，生成一个简洁的标题（10 字以内，不要引号）：

{context}

标题："""
        resp = llm.invoke([
            SystemMessage(content="你是一个专业的标题生成器。只输出标题本身，不要多余内容。"),
            HumanMessage(content=prompt),
        ])
        title = resp.content.strip().strip('"').strip("'")[:30]
    except Exception:
        # fallback: 用第一条用户消息
        for m in messages:
            if m["role"] == "user" and m.get("content", "").strip():
                title = m["content"].strip()[:20]
                break
        else:
            title = "新对话"

    memory_store.update_conversation_title(conv_id, title)
    return {"title": title}
