"""WebSocket 实时股价推送 — 共享轮询广播模式.

只有单个全局定时器拉取行情，广播给所有 WebSocket 连接。
避免每个连接独立轮询导致 API 请求爆炸。
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from backend.logger import logger

# 活跃的 WebSocket 连接
_active_connections: list[WebSocket] = []

# 全局共享的最新快照（由 _shared_polling_loop 维护）
_shared_snapshot: dict[str, dict[str, Any]] = {}

# 上一次推送的快照（用于计算变化）
_last_broadcast_snapshot: dict[str, dict[str, Any]] = {}

# 共享轮询任务
_polling_task: asyncio.Task | None = None

# 轮询 / 退避参数
POLL_INTERVAL = 10
_BASE_BACKOFF = 5
_MAX_BACKOFF = 120
_consecutive_failures = 0
_last_failure_logged = False


def _BACKOFF() -> int:
    delay = min(_BASE_BACKOFF * (2 ** (_consecutive_failures - 1)), _MAX_BACKOFF)
    return max(delay, _BASE_BACKOFF)


# ────────── 共享轮询循环 ──────────


async def _shared_polling_loop():
    """全局唯一的行情轮询循环，有连接时运行，无连接时退出."""
    global _shared_snapshot, _last_broadcast_snapshot, _consecutive_failures, _last_failure_logged
    while _active_connections:
        current = _fetch_spot_prices()
        if current:
            _shared_snapshot.update(current)
            _consecutive_failures = 0
            if _last_failure_logged:
                logger.info("实时行情连接已恢复")
                _last_failure_logged = False
            # 计算变化并广播
            changes = _diff_changes(current)
            if changes:
                payload = {"type": "update", "data": changes}
                await _broadcast(payload)
                _last_broadcast_snapshot.update(current)
        else:
            _consecutive_failures += 1
            if not _last_failure_logged:
                logger.warning("实时行情不可用，进入退避模式（间隔 %ds）", _BACKOFF())
                _last_failure_logged = True
            delay = _BACKOFF()
            # 退避期间每 5 秒检查是否还有活跃连接
            while delay > 0 and _active_connections:
                await asyncio.sleep(min(5, delay))
                delay -= 5
            continue

        await asyncio.sleep(POLL_INTERVAL)


# ────────── WebSocket 端点 ──────────


async def ws_prices(websocket: WebSocket):
    """WebSocket 端点 /ws/prices — 共享行情推送，单个全局轮询."""
    global _polling_task
    await websocket.accept()
    _active_connections.append(websocket)
    logger.info("WebSocket 客户端已连接 (当前 %d)", len(_active_connections))

    # 首次连接：启动共享轮询
    if _polling_task is None or _polling_task.done():
        _polling_task = asyncio.create_task(_shared_polling_loop())

    # 立即推送当前快照
    if _shared_snapshot:
        try:
            await websocket.send_json({"type": "snapshot", "data": list(_shared_snapshot.values())})
        except Exception:
            pass

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=POLL_INTERVAL + 5)
                if msg == "refresh" and _shared_snapshot:
                    await websocket.send_json({"type": "snapshot", "data": list(_shared_snapshot.values())})
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket 异常: %s", e)
    finally:
        if websocket in _active_connections:
            _active_connections.remove(websocket)
        logger.info("WebSocket 客户端已断开 (剩余 %d)", len(_active_connections))


# ────────── 行情数据获取 ──────────


def _fetch_spot_prices() -> dict[str, dict[str, Any]]:
    """从 ak.stock_zh_a_spot_em 获取全市场实时行情快照."""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return {}

        result = {}
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            if not code:
                continue
            result[code] = {
                "code": code,
                "name": str(row.get("名称", "")),
                "price": _safe_float(row.get("最新价")),
                "change_pct": _safe_float(row.get("涨跌幅")),
                "change_amt": _safe_float(row.get("涨跌额")),
                "volume": _safe_float(row.get("成交量")),
                "amount": _safe_float(row.get("成交额")),
                "open": _safe_float(row.get("今开")),
                "high": _safe_float(row.get("最高")),
                "low": _safe_float(row.get("最低")),
                "pre_close": _safe_float(row.get("昨收")),
                "turnover": _safe_float(row.get("换手率")),
            }
        return result
    except Exception:
        if _consecutive_failures == 0:
            logger.warning("获取实时行情失败，将进入退避模式")
        return {}


def _diff_changes(current: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """对比当前快照与上次广播快照，返回有变化的条目."""
    if not _last_broadcast_snapshot:
        return list(current.values())

    changes = []
    for code, cur in current.items():
        prev = _last_broadcast_snapshot.get(code)
        if prev is None:
            changes.append(cur)
        elif cur.get("price") != prev.get("price") or cur.get("change_pct") != prev.get("change_pct"):
            changes.append(cur)
    return changes


def _safe_float(val: Any) -> float | None:
    try:
        import pandas as pd
        if val is None:
            return None
        v = float(val)
        return None if pd.isna(v) else v
    except (ValueError, TypeError):
        return None


async def _broadcast(msg: dict[str, Any]):
    """向所有活跃客户端广播消息."""
    dead = []
    for ws in _active_connections:
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _active_connections.remove(ws)


async def broadcast_message(msg: dict[str, Any]):
    """公开的广播接口（供其他模块调用）. """
    await _broadcast(msg)
