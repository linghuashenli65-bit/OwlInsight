"""WebSocket 实时股价推送.

通过轮询 ak.stock_zh_a_spot_em 获取 A 股实时行情，
当价格发生变化时推送给所有连接的客户端。
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

# 上一次推送的价格快照 {code: {price, change_pct, ...}}
_last_snapshot: dict[str, dict[str, Any]] = {}

# 轮询间隔（秒）
POLL_INTERVAL = 10
# 失败后退避参数
_BASE_BACKOFF = 5          # 初始退避 5 秒
_MAX_BACKOFF = 120         # 最大退避 2 分钟
_consecutive_failures = 0   # 全局连续失败计数
_last_failure_logged = False


def _BACKOFF() -> int:
    """指数退避：5, 10, 20, 40, 80, 120, 120..."""
    delay = min(_BASE_BACKOFF * (2 ** (_consecutive_failures - 1)), _MAX_BACKOFF)
    return max(delay, _BASE_BACKOFF)


async def ws_prices(websocket: WebSocket):
    """WebSocket 端点 /ws/prices — 实时推送关注公司股价变化."""
    global _consecutive_failures, _last_failure_logged
    await websocket.accept()
    _active_connections.append(websocket)
    logger.info("WebSocket 客户端已连接 (当前 %d)", len(_active_connections))

    try:
        # 立即推送一次当前快照
        snapshot = _fetch_spot_prices()
        if snapshot:
            await websocket.send_json({"type": "snapshot", "data": snapshot})

        # 保持连接，等待客户端消息或断开
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=POLL_INTERVAL)
                # 客户端可以发送 "refresh" 强制刷新
                if msg == "refresh":
                    snapshot = _fetch_spot_prices()
                    if snapshot:
                        await websocket.send_json({"type": "snapshot", "data": snapshot})
            except asyncio.TimeoutError:
                # 超时 = 轮询时间到，推送变化
                pass

            # 轮询最新价格（带失败退避）
            current = _fetch_spot_prices()
            changes = _diff_changes(current)
            if current:
                _consecutive_failures = 0
                if _last_failure_logged:
                    logger.info("实时行情连接已恢复")
                    _last_failure_logged = False
                if changes:
                    await websocket.send_json({"type": "update", "data": changes})
                    _last_snapshot.update(current)
            else:
                _consecutive_failures += 1
                if not _last_failure_logged:
                    logger.warning("实时行情不可用，进入退避模式（间隔 %ds）", _BACKOFF())
                    _last_failure_logged = True
                await asyncio.sleep(_BACKOFF())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket 异常: %s", e)
    finally:
        if websocket in _active_connections:
            _active_connections.remove(websocket)
        logger.info("WebSocket 客户端已断开 (剩余 %d)", len(_active_connections))


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
        # 退避模式下静默，避免刷屏
        if _consecutive_failures == 0:
            logger.warning("获取实时行情失败，将进入退避模式")
        return {}


def _diff_changes(current: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """对比当前快照与上次快照，返回有变化的条目."""
    if not _last_snapshot:
        return list(current.values())

    changes = []
    for code, cur in current.items():
        prev = _last_snapshot.get(code)
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


async def broadcast_message(msg: dict[str, Any]):
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
