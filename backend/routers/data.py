"""数据接口 — 关注公司 / 研究笔记 / K线 / 资金流向 / 机构持仓."""

from pathlib import Path
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.memory.store import memory_store
from backend.database import get_db
from backend.database.crud import get_company, list_companies
from backend.logger import logger

router = APIRouter()


@router.get("/dashboard")
def get_dashboard():
    """获取首页盯盘数据（Redis 缓存 5 分钟）. """
    from backend.cache import cache_get_json, cache_set_json
    cached = cache_get_json("dashboard")
    if cached:
        return cached

    memory_store.connect()
    raw_companies = memory_store.get_all_watched_companies()
    convs = memory_store.list_conversations(limit=5)
    notes = memory_store.get_all_notes(limit=5)

    seen = set()
    companies = []
    for c in raw_companies:
        key = c.get("company_name", c.get("company_code", ""))
        if key and key not in seen:
            seen.add(key)
            companies.append(c)

    prices = {}
    for c in companies[:6]:
        try:
            from backend.tools.financial_data import get_stock_price_history
            data = get_stock_price_history(c["company_code"], start_date="20260101")
            if data:
                last = data[-1]
                # 当日开盘→收盘变化率
                close_val = last.get("close", 0) or 0
                open_val = last.get("open", 0) or 0
                if open_val:
                    pct = round((close_val - open_val) / open_val * 100, 2)
                else:
                    pct = 0.0
                prices[c["company_code"]] = {"price": close_val, "change_pct": pct, "date": last.get("date", "")}
        except Exception:
            pass

    result = {
        "companies": [{**c, "price_info": prices.get(c["company_code"], {})} for c in companies[:8]],
        "conversation_count": len(convs),
        "notes_count": len(notes),
    }
    cache_set_json("dashboard", result, ttl=300)
    return result


class SaveNoteRequest(BaseModel):
    company_code: str
    company_name: str = ""
    title: str = ""
    content: str
    metrics: list[str] = []
    tags: list[str] = []


@router.post("/notes/save")
def save_note(body: SaveNoteRequest):
    """保存研究笔记（由前端在用户确认后调用）. """
    if not body.company_code or not body.content:
        raise HTTPException(400, "company_code 和 content 不能为空")
    memory_store.connect()
    title = body.title or ""
    # SaveNoteButton 前端保存时也用 LLM 生成标题
    if not title:
        try:
            from backend.agent.graph import _generate_note_summary
            title = _generate_note_summary(body.content, body.company_name or body.company_code)
        except Exception:
            pass
    note_id = memory_store.upsert_note(
        company_code=body.company_code,
        company_name=body.company_name or body.company_code,
        title=title,
        content=body.content,
        metrics=body.metrics,
        tags=body.tags or [body.company_name or body.company_code, "用户保存"],
    )
    return {"status": "ok", "note_id": note_id}


@router.get("/companies")
def get_companies():
    """获取所有关注的公司列表."""
    memory_store.connect()
    companies = memory_store.get_all_watched_companies()
    return {"companies": companies}


@router.delete("/companies/{code}")
def delete_company(code: str):
    """删除关注的公司."""
    memory_store.connect()
    memory_store.delete_company(code)
    return {"status": "ok"}


@router.get("/companies/{code}")
async def get_company_detail(code: str, db: AsyncSession = Depends(get_db)):
    """获取公司详情 & 分析历史 (MySQL)."""
    company = await get_company(db, code)
    if not company:
        return {
            "company_code": code,
            "company_name": code,
            "last_analysis": None,
            "analysis_count": 0,
            "notes_count": 0,
        }
    # 统计研究笔记数量
    notes_list = await list_companies(db)
    notes_count = sum(1 for n in notes_list if n.company_code == code)
    return {
        "company_code": company.company_code,
        "company_name": company.company_name,
        "last_analysis": company.last_analyzed.isoformat() if company.last_analyzed else None,
        "analysis_count": company.analysis_count,
        "notes_count": notes_count,
    }


@router.get("/notes")
def get_notes():
    """获取研究笔记列表（缓存 60 秒）. """
    from backend.cache import cache_get_json, cache_set_json
    cached = cache_get_json("notes_list")
    if cached:
        return cached
    memory_store.connect()
    sqlite_notes = memory_store.get_all_notes(limit=50)
    result = {"notes": sqlite_notes}
    cache_set_json("notes_list", result, ttl=60)
    return result


@router.delete("/notes/{note_id}")
def delete_note(note_id: int):
    """删除指定笔记."""
    from backend.cache import cache_invalidate
    memory_store.connect()
    memory_store.delete_note(note_id)
    cache_invalidate("notes_list")
    return {"status": "ok"}


@router.get("/notes/search")
def search_notes(q: str = ""):
    """搜索笔记（SQLite 模糊匹配）. """
    memory_store.connect()
    if not q.strip():
        notes = memory_store.get_all_notes(limit=20)
    else:
        notes = memory_store.search_notes(q.strip(), limit=20)
    return {"notes": notes}


@router.get("/notes/detail/{note_id}")
def get_note_content(note_id: int):
    """获取 SQLite 笔记完整内容（按 ID）. """
    memory_store.connect()
    note = memory_store.get_note_by_id(note_id)
    if note:
        return {"content": note.get("content", "")}
    return {"error": "笔记不存在", "content": ""}


@router.get("/notes/{path:path}")
def get_note_detail(path: str):
    """获取文件笔记详情 (path 为完整文件路径). """
    fp = Path(path)
    if fp.exists():
        return {"content": fp.read_text("utf-8")}
    return {"error": "笔记不存在", "content": ""}


# ─────────────────── K线数据（日K/周K/月K）───────────────────

@router.get("/stock/{code}/kline")
def get_stock_kline(code: str, period: str = "daily"):
    """获取 K线数据.
    period: daily(60日), weekly(60周), monthly(24月)
    """
    from backend.cache import cache_get_json, cache_set_json
    cache_key = f"kline:{code}:{period}"
    cached = cache_get_json(cache_key)
    if cached:
        return cached

    try:
        import akshare as ak
        today = date.today()

        if period == "monthly":
            start_date = (today - timedelta(days=730)).strftime("%Y%m%d")
        elif period == "weekly":
            start_date = (today - timedelta(days=420)).strftime("%Y%m%d")
        else:
            start_date = (today - timedelta(days=90)).strftime("%Y%m%d")
        end_date = today.strftime("%Y%m%d")

        is_hk = len(code) == 5
        if is_hk:
            df = ak.stock_hk_hist(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date, adjust="qfq",
            )
        else:
            from backend.tools.financial_data import _to_tx_symbol
            tx_symbol = _to_tx_symbol(code)
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_symbol, start_date=start_date, end_date=end_date,
            )

        if df is None or df.empty:
            return {"code": code, "period": period, "data": []}

        results = []
        for _, row in df.iterrows():
            date_val = row.get("日期" if is_hk else "date")
            date_str = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val)
            results.append({
                "date": date_str,
                "open": _safe_float_num(row.get("开盘" if is_hk else "open")),
                "close": _safe_float_num(row.get("收盘" if is_hk else "close")),
                "high": _safe_float_num(row.get("最高" if is_hk else "high")),
                "low": _safe_float_num(row.get("最低" if is_hk else "low")),
                "volume": _safe_float_num(row.get("成交量" if is_hk else "volume")) or 0,
            })

        # 周/月聚合
        if period in ("weekly", "monthly") and results:
            grouped = {}
            for r in results:
                try:
                    d = date.fromisoformat(r["date"][:10])
                    if period == "weekly":
                        key = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
                    else:
                        key = f"{d.year}-{d.month:02d}"
                except Exception:
                    key = r["date"][:7]
                if key not in grouped:
                    grouped[key] = {"open": r["open"], "high": r["high"], "low": r["low"],
                                    "close": r["close"], "date": r["date"], "volume": r["volume"]}
                else:
                    g = grouped[key]
                    g["high"] = max(g["high"] or 0, r["high"] or 0)
                    g["low"] = min(g["low"] or float("inf"), r["low"] or float("inf"))
                    g["close"] = r["close"]
                    g["volume"] = (g["volume"] or 0) + (r["volume"] or 0)
            results = sorted(grouped.values(), key=lambda x: x["date"])

        result = {"code": code, "period": period, "data": results}
        # 日K/周K/月K 缓存 1 小时，这些数据变动不大
        cache_set_json(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        logger.warning("获取K线失败 (%s/%s): %s", code, period, e)
        return {"code": code, "period": period, "data": [], "error": str(e)}


# ─────────────────── 分钟K线 ───────────────────

@router.get("/stock/{code}/minute-kline")
def get_stock_minute_kline(code: str, interval: int = 5):
    """获取分钟K线.
    interval: 1/5/15/30/60 分钟
    使用东方财富 API 直连，更稳定。
    """
    try:
        import httpx
        market = 1 if code.startswith("6") else 0
        end_sec = int(date.today().timestamp())
        # klt: 1=1分, 5=5分, 15=15分, 30=30分, 60=60分
        klt_map = {1: 1, 5: 5, 15: 15, 30: 30, 60: 60}
        klt = klt_map.get(interval, 5)
        limit = 120  # 返回120根K线

        url = (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={market}.{code}"
            f"&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57"
            f"&klt={klt}&fqt=1&end={end_sec}&lmt={limit}"
        )
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        if resp.status_code != 200:
            return {"code": code, "interval": interval, "data": []}

        json_data = resp.json()
        raw = (json_data.get("data") or {}).get("klines") or []

        results = []
        for line in raw:
            parts = line.split(",")
            if len(parts) >= 6:
                results.append({
                    "date": parts[0],
                    "open": _safe_float_num(parts[1]),
                    "close": _safe_float_num(parts[2]),
                    "high": _safe_float_num(parts[3]),
                    "low": _safe_float_num(parts[4]),
                    "volume": int(float(parts[5])) if parts[5] else 0,
                })
        return {"code": code, "interval": interval, "data": results}
    except Exception as e:
        logger.warning("获取分钟K线失败 (%s/%dmin): %s", code, interval, e)
        return {"code": code, "interval": interval, "data": [], "error": str(e)}


# ─────────────────── 日内分时数据 ───────────────────

@router.get("/stock/{code}/intraday")
def get_stock_intraday(code: str):
    """获取当天日内分时数据（每分钟一个点）. """
    try:
        import httpx
        today_ts = int(date.today().timestamp())
        market = 1 if code.startswith("6") else 0

        url = (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={market}.{code}"
            f"&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57"
            f"&klt=1&fqt=1&end={today_ts}&lmt=250"
        )
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        if resp.status_code != 200:
            return {"code": code, "data": []}

        json_data = resp.json()
        raw = (json_data.get("data") or {}).get("klines") or []

        results = []
        today_str = date.today().strftime("%Y-%m-%d")
        for line in raw:
            parts = line.split(",")
            if len(parts) < 6:
                continue
            dt = parts[0]
            # 只保留当天数据
            if today_str in dt:
                results.append({
                    "time": dt.split(" ")[-1][:5],
                    "price": _safe_float_num(parts[2]),
                    "volume": int(float(parts[5])) if parts[5] else 0,
                    "change_pct": None,
                })

        return {"code": code, "data": results}
    except Exception as e:
        logger.warning("获取分时数据失败 (%s): %s", code, e)
        return {"code": code, "data": [], "error": str(e)}


def _safe_float_num(val) -> float | None:
    import pandas as pd
    try:
        if val is None:
            return None
        v = float(val)
        return None if pd.isna(v) else v
    except (ValueError, TypeError):
        return None


# ─────────────────── 资金流向 ───────────────────

@router.get("/stock/{code}/fund-flow")
def get_stock_fund_flow(code: str):
    """获取个股资金流向（主力/散户），绕过系统代理直连 eastmoney."""
    from backend.cache import cache_get_json, cache_set_json
    cache_key = f"fund_flow:{code}"
    cached = cache_get_json(cache_key)
    if cached:
        return cached

    # 非 A 股不支持资金流向
    if not code.isdigit() or len(code) != 6:
        return {"code": code, "data": []}

    try:
        data = _fetch_fund_flow_from_em(code)
        result = {"code": code, "data": data}
        if data:
            cache_set_json(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        logger.warning("获取资金流向失败 (%s): %s", code, e)
        return {"code": code, "data": [], "error": str(e)}


def _fetch_fund_flow_from_em(code: str) -> list[dict]:
    """直连 eastmoney push2his API 获取个股资金流向，绕过系统代理."""
    import time

    market = "1" if code.startswith("6") else "0"
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "lmt": "0",
        "klt": "101",
        "secid": f"{market}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": "b2884a393a59ad64002292a3e90d46a5",
        "_": str(int(time.time() * 1000)),
    }

    # 方案 A：requests + trust_env=False（绕过 HTTP_PROXY/HTTPS_PROXY 环境变量）
    import requests as _req
    sess = _req.Session()
    sess.trust_env = False
    try:
        resp = sess.get(url, params=params, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://data.eastmoney.com/",
        })
        resp.raise_for_status()
        klines = resp.json().get("data", {}).get("klines", [])
        if klines:
            return _parse_fund_flow_klines(klines)
    except Exception as e:
        logger.debug("资金流向 requests 方式失败 (%s)，尝试 urllib 回退: %s", code, e)

    # 方案 B：urllib + ProxyHandler({})（绕过 Windows 系统代理）
    import urllib.request as _urllib_req
    import json as _json
    proxy_handler = _urllib_req.ProxyHandler({})
    opener = _urllib_req.build_opener(proxy_handler)
    req = _urllib_req.Request(
        f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://data.eastmoney.com/",
        },
    )
    resp = opener.open(req, timeout=10)
    raw = _json.loads(resp.read().decode())
    klines = raw.get("data", {}).get("klines", [])
    return _parse_fund_flow_klines(klines)


def _parse_fund_flow_klines(klines: list[str]) -> list[dict]:
    """解析 eastmoney 资金流向 K 线数据.

    API 返回格式（f51~f65 逗号分隔）:
      date, main_net, small_net, medium_net, large_net, super_large_net,
      main_pct, small_pct, medium_pct, large_pct, super_large_pct,
      close, change_pct, -, -
    """
    results = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        results.append({
            "date": parts[0],
            "main_net": _safe_float_num(parts[1]),
            "main_pct": _safe_float_num(parts[6]),
            "super_large_net": _safe_float_num(parts[5]),
            "super_large_pct": _safe_float_num(parts[10]),
            "large_net": _safe_float_num(parts[4]),
            "large_pct": _safe_float_num(parts[9]),
            "medium_net": _safe_float_num(parts[3]),
            "medium_pct": _safe_float_num(parts[8]),
            "small_net": _safe_float_num(parts[2]),
            "small_pct": _safe_float_num(parts[7]),
        })
    # eastmoney 按日期降序排列，取最近 20 条
    results.sort(key=lambda r: r["date"], reverse=True)
    return results[:20]


# ─────────────────── 机构持仓 ───────────────────

@router.get("/stock/{code}/institution")
def get_stock_institution(code: str):
    """获取机构持仓/基金持仓数据（多重降级）."""
    results = []

    # 方法1: akshare stock_institute_hold_detail
    try:
        import akshare as ak
        for indicator in ["基金持仓", "券商持仓", "保险持仓", "QFII持仓", "社保基金"]:
            try:
                df = ak.stock_institute_hold_detail(symbol=code, indicator=indicator)
                if df is not None and not df.empty:
                    for _, row in df.head(10).iterrows():
                        cols = list(row.index)
                        name_col = _find_col_name(cols, "名称", "机构", "基金")
                        shares_col = _find_col_name(cols, "持股数", "持仓股数", "股数")
                        value_col = _find_col_name(cols, "持仓市值", "市值")
                        pct_col = _find_col_name(cols, "占流通股", "占比", "比例")
                        results.append({
                            "name": str(row.get(name_col, "")) if name_col else "",
                            "type": indicator,
                            "hold_shares": _safe_float_num(row.get(shares_col)) if shares_col else None,
                            "hold_value": _safe_float_num(row.get(value_col)) if value_col else None,
                            "hold_pct": _safe_float_num(row.get(pct_col)) if pct_col else None,
                        })
            except TypeError:
                continue
            except Exception:
                continue
    except Exception as e:
        logger.debug("stock_institute_hold_detail 失败 (%s): %s", code, e)

    # 方法2: akshare stock_report_fund_hold_detail
    if not results:
        try:
            import akshare as ak
            df = ak.stock_report_fund_hold_detail(stock=code)
            if df is not None and not df.empty:
                cols = list(df.columns)
                name_col = _find_col_name(cols, "基金名称", "名称", "机构")
                shares_col = _find_col_name(cols, "持股数", "持仓股数", "股数")
                value_col = _find_col_name(cols, "持仓市值", "市值")
                pct_col = _find_col_name(cols, "占流通股", "占净值", "比例")
                for _, row in df.head(15).iterrows():
                    results.append({
                        "name": str(row.get(name_col, "")) if name_col else "",
                        "type": "基金",
                        "hold_shares": _safe_float_num(row.get(shares_col)) if shares_col else None,
                        "hold_value": _safe_float_num(row.get(value_col)) if value_col else None,
                        "hold_pct": _safe_float_num(row.get(pct_col)) if pct_col else None,
                    })
        except Exception as e:
            logger.debug("stock_report_fund_hold_detail 失败 (%s): %s", code, e)

    # 方法3: 东方财富 API 直接请求
    if not results:
        try:
            import httpx
            # 用 stock_individual_fund_flow 的机构数据
            market = "sh" if code.startswith("6") else "sz"
            url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_MUTUAL_STOCK_NORTHSTA&columns=ALL&filter=(SECURITY_CODE=%22{code}%22)&pageSize=20&sortColumns=HOLD_DATE&sortTypes=-1"
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json().get("result", {}).get("data", [])
                for item in data[:15]:
                    results.append({
                        "name": str(item.get("INSTITUTION_NAME", item.get("HOLDER_NAME", ""))),
                        "type": "机构",
                        "hold_shares": _safe_float_num(item.get("HOLD_NUM", item.get("SHARES_RATIO"))),
                        "hold_value": _safe_float_num(item.get("HOLD_MARKET_CAP")),
                        "hold_pct": _safe_float_num(item.get("HOLD_RATIO", item.get("FREE_SHARES_RATIO"))),
                    })
        except Exception as e:
            logger.debug("东方财富机构数据也失败 (%s): %s", code, e)

    return {"code": code, "data": results}


def _find_col_name(columns: list[str], *keywords: str) -> str | None:
    """在列名列表中模糊匹配包含任一关键词的列."""
    for col in columns:
        for kw in keywords:
            if kw in col:
                return col
    return None


# ─────────────────── 刷新实时价格（用 spot API） ───────────────────

@router.get("/companies/refresh")
def refresh_companies_price():
    """用 ak.stock_zh_a_spot_em 刷新所有关注公司的实时价格."""
    memory_store.connect()
    companies = memory_store.get_all_watched_companies()
    if not companies:
        return {"prices": {}}

    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return {"prices": {}}

        spot_map = {}
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            if code:
                spot_map[code] = {
                    "price": _safe_float_num(row.get("最新价")),
                    "change_pct": _safe_float_num(row.get("涨跌幅")),
                    "open": _safe_float_num(row.get("今开")),
                    "high": _safe_float_num(row.get("最高")),
                    "low": _safe_float_num(row.get("最低")),
                }

        prices = {}
        for c in companies:
            code = c.get("company_code", "")
            if code in spot_map:
                prices[code] = spot_map[code]
        return {"prices": prices}
    except Exception as e:
        logger.warning("刷新实时价格失败: %s", e)
        return {"prices": {}}
