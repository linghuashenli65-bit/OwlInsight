"""告警配置与事件接口 — 阈值设置 / 邮件偏好 / 事件查询 / SSE 推送."""

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.alerter import alert_engine
from backend.alerter.notifier import sse_manager
from backend.memory.store import memory_store

router = APIRouter(prefix="/api/alerter", tags=["alerter"])


# ────────── 请求模型 ──────────


class AlertConfigItem(BaseModel):
    company_code: str
    price_up_pct: float = 5.0
    price_down_pct: float = -5.0
    fund_flow_threshold: float = 100000000.0
    news_enabled: bool = True
    intraday_enabled: bool = True


class AlertConfigBatch(BaseModel):
    configs: list[AlertConfigItem]


class PreferencesBatch(BaseModel):
    preferences: dict[str, str]


# ────────── 告警阈值配置 ──────────


@router.get("/config")
def get_alert_configs():
    """获取所有关注公司的告警阈值配置 + 当前偏好设置."""
    memory_store.connect()
    configs = memory_store.get_all_alert_configs()
    # 同时返回所有未配置的公司，用默认值
    companies = memory_store.get_all_watched_companies()
    existing_codes = {c["company_code"] for c in configs}
    for company in companies:
        if company["company_code"] not in existing_codes:
            configs.append({
                "company_code": company["company_code"],
                "company_name": company.get("company_name", ""),
                "price_up_pct": 5.0,
                "price_down_pct": -5.0,
                "fund_flow_threshold": 100000000.0,
                "news_enabled": 1,
                "intraday_enabled": 1,
            })
    preferences = memory_store.get_all_preferences()
    return {"configs": configs, "preferences": preferences}


@router.put("/config")
def save_alert_configs(body: AlertConfigBatch):
    """批量保存告警阈值配置."""
    memory_store.connect()
    for cfg in body.configs:
        memory_store.save_alert_config(cfg.model_dump())
    return {"status": "ok"}


# ────────── 邮件偏好设置 ──────────


@router.get("/preferences")
def get_preferences():
    """获取告警偏好（邮件设置等）. """
    memory_store.connect()
    prefs = memory_store.get_all_preferences()
    return {"preferences": prefs}


@router.put("/preferences")
def save_preferences(body: PreferencesBatch):
    """保存告警偏好，并刷新调度器时间配置."""
    memory_store.connect()
    memory_store.set_preferences_batch(body.preferences)
    # 刷新调度器，使新时间配置立即生效
    alert_engine.refresh_jobs()
    return {"status": "ok"}


# ────────── 告警事件 ──────────


@router.get("/events")
def get_alert_events(
    unread_only: bool = Query(False),
    limit: int = Query(50),
    company_code: Optional[str] = Query(None),
):
    """获取告警事件列表."""
    memory_store.connect()
    events = memory_store.get_recent_alerts(limit=limit, unread_only=unread_only)
    if company_code:
        events = [e for e in events if e.get("company_code") == company_code]
    unread = memory_store.get_unread_alert_count()
    return {"events": events, "unread_count": unread}


@router.put("/events/read")
def mark_alert_read(alert_id: Optional[int] = Query(None)):
    """标记告警为已读. 不传 alert_id 则标记全部已读."""
    memory_store.connect()
    if alert_id:
        memory_store.mark_alert_read(alert_id)
    else:
        memory_store.mark_all_alerts_read()
    # 返回最新的未读数
    unread = memory_store.get_unread_alert_count()
    return {"status": "ok", "unread_count": unread}


# ────────── 手动触发 ──────────


@router.post("/trigger/{job_name}")
async def trigger_job(job_name: str):
    """手动触发指定任务：pre_market / intraday / post_market."""
    job_map = {
        "pre_market": alert_engine._pre_market_job,
        "intraday": alert_engine._intraday_job,
        "post_market": alert_engine._post_market_job,
    }
    job = job_map.get(job_name)
    if not job:
        return {"status": "error", "message": f"未知任务: {job_name}，可选: pre_market, intraday, post_market"}
    try:
        await job()
        return {"status": "ok", "message": f"任务 {job_name} 执行完成"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ────────── SSE 实时推送 ──────────


class SSEQueueConnection:
    """包装 asyncio.Queue，适配 SSEManager 的 write 接口."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def write(self, data: bytes) -> None:
        await self.queue.put(data)


@router.get("/events/stream")
async def stream_alerts():
    """SSE 实时推送告警事件（用于前端弹窗）. """

    async def event_stream():
        conn = SSEQueueConnection()
        sse_manager.add(conn)
        try:
            while True:
                data = await conn.queue.get()
                yield data.decode("utf-8")
        except asyncio.CancelledError:
            pass
        finally:
            sse_manager.remove(conn)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
