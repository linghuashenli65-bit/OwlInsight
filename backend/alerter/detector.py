"""事件检测 — 价格异常 + 新闻匹配 + 资金流异常 + 日报生成."""

from backend.logger import logger
from datetime import date, datetime
from typing import Any, Optional

from backend.memory.store import memory_store
from backend.stock_map import lookup_company_code

# ────────── 工具函数 ──────────

def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        v = float(val)
        return None if v != v else v  # NaN check
    except (ValueError, TypeError):
        return None


# ────────── 价格异常检测 ──────────

def check_price_alerts() -> list[dict[str, Any]]:
    """检查所有关注公司的价格异常.

    从 akshare 获取实时行情，对比前收盘价计算涨跌幅。
    超过阈值（默认 ±5%，可在 alert_config 中自定义）时生成告警事件。

    Returns:
        告警事件列表，每个含 company_code, company_name, event_type, title, message, severity, data.
    """
    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare 不可用，跳过价格检测")
        return []

    companies = memory_store.get_all_watched_companies()
    if not companies:
        return []

    events = []

    # 批量获取实时行情（A股）
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        logger.warning("获取实时行情失败: %s", e)
        return []

    if df is None or df.empty:
        return []

    for company in companies:
        code = company["company_code"]
        name = company.get("company_name", code)

        # 过滤该股票
        row = df[df["代码"].astype(str).str.replace(r"\.(SH|SZ|sh|sz)$", "", regex=True) == code]
        if row.empty:
            continue

        row = row.iloc[0]
        current_price = _safe_float(row.get("最新价"))
        prev_close = _safe_float(row.get("昨收"))

        if current_price is None or prev_close is None or prev_close == 0:
            continue

        change_pct = (current_price - prev_close) / prev_close * 100

        # 读取该公司的阈值配置
        config = memory_store.get_alert_config(code)
        threshold_up = config.get("price_up_pct", 5.0)
        threshold_down = config.get("price_down_pct", -5.0)

        if change_pct >= threshold_up:
            events.append({
                "company_code": code,
                "company_name": name,
                "event_type": "price_surge",
                "title": f"{name} 涨幅 {change_pct:.2f}%",
                "message": f"{name}({code}) 当前价 {current_price:.2f}，涨幅 {change_pct:.2f}%，超过阈值 +{threshold_up}%",
                "severity": "warning",
                "data": {
                    "price": current_price,
                    "change_pct": round(change_pct, 2),
                    "threshold": threshold_up,
                },
            })
        elif change_pct <= threshold_down:
            events.append({
                "company_code": code,
                "company_name": name,
                "event_type": "price_drop",
                "title": f"{name} 跌幅 {abs(change_pct):.2f}%",
                "message": f"{name}({code}) 当前价 {current_price:.2f}，跌幅 {abs(change_pct):.2f}%，超过阈值 {threshold_down}%",
                "severity": "danger",
                "data": {
                    "price": current_price,
                    "change_pct": round(change_pct, 2),
                    "threshold": threshold_down,
                },
            })

    return events


# ────────── 盘前新闻摘要 ──────────

# 宏观新闻搜索关键词
_MACRO_KEYWORDS = [
    "A股 市场 今日 要闻 开盘",
    "宏观经济 数据 最新 CPI",
    "美股 隔夜 行情 三大指数",
    "北向资金 今日 流向",
    "人民币 汇率 最新",
    "国际油价 大宗商品",
]


def search_macro_news() -> list[dict[str, str]]:
    """搜索宏观市场新闻（多维度，最多 10 条）. """
    from backend.tools.news_search import _search_bing_news

    seen = set()
    results = []
    for kw in _MACRO_KEYWORDS:
        try:
            items = _search_bing_news(kw, max_results=4)
            for r in items:
                title = r.get("title", "")
                snippet = r.get("snippet", "") or ""
                if title and title not in seen and len(snippet) > 30:
                    seen.add(title)
                    results.append({"title": title, "snippet": snippet[:400]})
        except Exception:
            continue
        if len(results) >= 10:
            break
    return results[:10]


def _get_yesterday_market_indexes() -> dict[str, Any]:
    """获取昨日主要指数涨跌情况."""
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        if df is not None and not df.empty:
            latest = df.tail(2)
            if len(latest) >= 2:
                prev_close = latest.iloc[-2].get("close", 0)
                cur_close = latest.iloc[-1].get("close", 0)
                change_pct = round((cur_close - prev_close) / prev_close * 100, 2) if prev_close else 0
                return {"index_name": "上证指数", "value": cur_close, "change_pct": change_pct}
    except Exception:
        pass
    return {}


def _get_hot_sectors() -> list[dict[str, Any]]:
    """获取今日热门板块（前 5）. """
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return []
        # 按涨跌幅排序，取前 5
        df = df.sort_values("涨跌幅", ascending=False).head(5)
        return [
            {"name": row.get("板块名称", ""), "change_pct": row.get("涨跌幅", 0)}
            for _, row in df.iterrows()
        ]
    except Exception:
        return []


def get_pre_market_alerts() -> dict[str, Any]:
    """生成盘前简报：并行搜索 → AI 去重摘要 → AI 总览.

    Returns:
        dict with keys:
          - macro_news: list[{title, snippet, ai_summary}]
          - company_alerts: list[{company_name, code, summary, news}]
          - overview: str 全局总览
          - market_index: {...}
          - hot_sectors: list
          - risk_warnings: list[str]
    """
    import concurrent.futures

    companies = memory_store.get_all_watched_companies()
    if not companies:
        return {"macro_news": [], "company_alerts": [], "overview": "",
                "market_index": {}, "hot_sectors": [], "risk_warnings": []}

    # ── 阶段1: 全部搜索并行 ──
    logger.info("[盘前] 并行搜索宏观+公司新闻 ...")

    def _search_macro() -> list[dict]:
        news = search_macro_news()
        return news or [{"title": "A股开盘前瞻", "snippet": "市场关注今日宏观经济数据与外围市场表现。"}]

    def _search_one(c: dict) -> dict:
        code = c["company_code"]
        name = c.get("company_name", code)
        raw = search_company_news(name, code)
        news = [n for n in raw if len(n.get("snippet", "")) > 20][:8]
        prev_close = None
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"].astype(str).str.replace(r"\.(SH|SZ|sh|sz)$", "", regex=True) == code]
            prev_close = _safe_float(row.iloc[0].get("昨收")) if not row.empty else None
        except Exception:
            pass
        return {"code": code, "name": name, "news": news, "prev_close": prev_close}

    macro_news = []
    company_alerts = []
    all_industry_titles = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        f_macro = pool.submit(_search_macro)
        f_companies = {}
        for company in companies:
            if memory_store.get_alert_config(company["company_code"]).get("news_enabled", 1):
                f = pool.submit(_search_one, company)
                f_companies[f] = company

        # 收集宏观结果
        try:
            macro_news = f_macro.result()
        except Exception as e:
            logger.warning("宏观搜索异常: %s", e)
            macro_news = [{"title": "A股开盘前瞻", "snippet": "市场关注今日宏观经济数据与外围市场表现。"}]

        # 收集公司结果
        for f in concurrent.futures.as_completed(f_companies):
            try:
                r = f.result()
            except Exception:
                continue
            code, name, news, prev_close = r["code"], r["name"], r["news"], r["prev_close"]
            for item in news:
                for kw in ["板块", "行业", "产业", "新能源", "白酒", "科技", "医药", "汽车", "金融", "地产"]:
                    if kw in item.get("title", ""):
                        all_industry_titles.add(item["title"])
            summary = "，".join(filter(None, [
                f"昨收 {prev_close:.2f}" if prev_close else "已上市",
                f"近期 {len(news)} 条相关新闻" if news else "",
            ]))
            company_alerts.append({
                "company_name": name, "code": code,
                "summary": summary, "news": news[:8],
            })

    # ── 阶段2: AI 去重摘要（并行）──
    # 宏观新闻：AI 合并同类项，替换原列表
    macro_news = _summarize_macro(macro_news)
    # 公司新闻：并行逐条摘要
    _ai_summarize_batch(company_alerts)

    # ── 阶段3: AI 总览（等前面全部完成后再汇总）──
    overview = _ai_overview(macro_news, company_alerts)

    # 大盘指数 & 热门板块 & 风险提示
    market_index = _get_yesterday_market_indexes()
    hot_sectors = _get_hot_sectors()
    risk_warnings = [
        "美联储政策会议临近，短期市场波动风险",
        "个别股票可能出现异动，请关注盘中告警",
    ]

    return {
        "macro_news": macro_news,
        "market_index": market_index,
        "hot_sectors": hot_sectors,
        "company_alerts": company_alerts,
        "overview": overview,
        "industry_news": [{"title": t, "snippet": ""} for t in list(all_industry_titles)[:4]],
        "risk_warnings": risk_warnings,
    }


# ────────── 盘后总结 ──────────

def get_post_market_summaries() -> list[dict[str, Any]]:
    """生成盘后总结：今日涨跌幅 + 事件回顾.

    Returns:
        每公司一条总结，含涨跌幅、收盘价、今日事件。
    """
    companies = memory_store.get_all_watched_companies()
    if not companies:
        return []

    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
    except Exception:
        return []

    summaries = []
    for company in companies:
        code = company["company_code"]
        name = company.get("company_name", code)

        row = df[df["代码"].astype(str).str.replace(r"\.(SH|SZ|sh|sz)$", "", regex=True) == code]
        if row.empty:
            continue

        row = row.iloc[0]
        current_price = _safe_float(row.get("最新价"))
        prev_close = _safe_float(row.get("昨收"))
        high = _safe_float(row.get("最高"))
        low = _safe_float(row.get("最低"))
        volume = _safe_float(row.get("成交量"))

        change_pct = 0.0
        if current_price and prev_close and prev_close != 0:
            change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        # 查看今日是否有告警事件
        today_events = memory_store.get_recent_alerts(limit=5, unread_only=False)
        today_events = [
            e for e in today_events
            if e.get("company_code") == code
        ]

        event_summary = "、".join(
            [e.get("title", "") for e in today_events[:3]]
        ) if today_events else "无异常"

        summaries.append({
            "company_name": name,
            "code": code,
            "change_pct": change_pct,
            "close": current_price,
            "high": high,
            "low": low,
            "volume": volume,
            "events": event_summary,
        })

    return summaries


# ────────── AI 批量摘要 ──────────

def _summarize_macro(macro_news: list[dict]) -> list[dict]:
    """宏观新闻：AI 合并同类事件，每条 50-80 字摘要.

    区别于公司新闻的逐条摘要，宏观新闻需要 AI 先识别"哪些条说的是同一件事"
    再合并输出，避免重复。返回新的去重+摘要后的列表。
    """
    if not macro_news:
        return macro_news

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        from backend.config import settings
        import json as _json

        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.15,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            timeout=30,
        )

        lines = []
        for i, item in enumerate(macro_news):
            t = item.get("title", "")[:80]
            s = item.get("snippet", "")[:200]
            lines.append(f"[{i+1}] {t}\n   {s}")
        text = "\n".join(lines)

        prompt = f"""你是一个财经主编。以下是今日宏观新闻素材，请完成：

1. **合并同类**：同一事件的多个报道合并为一个主题
2. **过滤无用**：忽略与金融市场无关的内容
3. **写摘要**：每个主题输出一行摘要，50-80 字，提炼核心事实与影响

新闻素材：
{text}

输出 JSON 数组（纯 JSON，不要 markdown）：
[{{"title": "主题标题（15字以内）", "summary": "摘要内容50-80字"}}]"""

        resp = llm.invoke([
            SystemMessage(content="你是财经主编。输出 JSON 格式的合并摘要。"),
            HumanMessage(content=prompt),
        ])
        raw = resp.content.strip().removeprefix(
            "```json").removeprefix("```").removesuffix("```").strip()
        topics = _json.loads(raw)

        result = []
        for t in topics:
            title = t.get("title", "")
            summary = t.get("summary", "")
            if title and summary:
                result.append({"title": title, "snippet": "", "ai_summary": summary})

        if result:
            logger.info("  宏观合并摘要: %d 组 → %d 条", len(macro_news), len(result))
            return result
    except Exception as e:
        logger.warning("  宏观合并摘要失败: %s", e)

    # fallback: 逐条简单摘要
    return macro_news


def _summarize_one(target: list[dict], key: str | None = None) -> None:
    """为公司新闻执行去重+摘要，每条 15-25 字."""
    if not target:
        return

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        from backend.config import settings

        if not settings.LLM_API_KEY:
            return

        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.15,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            timeout=30,
        )

        lines = []
        for i, item in enumerate(target):
            lines.append(f"[{i+1}] {item.get('title', '')[:60]}\n   {item.get('snippet', '')[:200]}")
        articles_text = "\n".join(lines)

        prompt = f"""你是一个财经新闻编辑。以下是一组公司新闻，请完成去重 + 摘要。

**去重要求**：
- 同一事件的不同来源报道视为重复，分配相同组号
- 同一组的新闻分配**完全相同的摘要**

**摘要要求**：
- 每组 15-25 字，提取最关键的事实
- 只陈述，不评价

新闻列表：
{articles_text}

输出格式（严格每行一条，格式：序号|组号|摘要）：
1|G1|摘要内容
2|G1|摘要内容
3|G2|摘要内容
..."""

        resp = llm.invoke([
            SystemMessage(content="你是财经新闻编辑，负责去重和摘要。"),
            HumanMessage(content=prompt),
        ])

        group_summaries: dict[str, str] = {}
        for line in resp.content.strip().split("\n"):
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|", 2)
            try:
                idx = int(parts[0].strip()) - 1
                if len(parts) >= 3 and parts[1].strip().startswith("G"):
                    group_id = parts[1].strip()
                    summary = parts[2].strip()
                    if group_id in group_summaries:
                        summary = group_summaries[group_id]
                    else:
                        group_summaries[group_id] = summary
                elif len(parts) >= 2:
                    summary = parts[1].strip()
                else:
                    continue
                if 0 <= idx < len(target):
                    target[idx]["ai_summary"] = summary
            except (ValueError, IndexError):
                continue

        done = sum(1 for item in target if item.get("ai_summary"))
        label = key or ""
        logger.info("  摘要完成 %s: %d/%d 条", label, done, len(target))
    except Exception as e:
        logger.warning("  摘要失败 %s: %s", key or "", e)


def _ai_summarize_batch(company_alerts: list[dict]) -> None:
    """并行对每组公司新闻执行去重+摘要."""
    import concurrent.futures

    tasks = []

    for company in company_alerts:
        news = company.get("news", [])
        if news:
            tasks.append((news, company.get("company_name", "")))

    if not tasks:
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_summarize_one, t, k) for t, k in tasks]
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                logger.warning("并行摘要任务异常: %s", e)


# ────────── AI 总览 ──────────

def _ai_overview(macro_news: list[dict], company_alerts: list[dict]) -> str:
    """AI 生成盘前总览（等所有搜索+摘要完成后调用）. """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        from backend.config import settings

        if not settings.LLM_API_KEY:
            return ""

        # 收集所有摘要
        summaries = []
        for m in macro_news:
            if m.get("ai_summary"):
                summaries.append(f"· {m['ai_summary']}")
        for c in company_alerts:
            for n in c.get("news", []):
                if n.get("ai_summary"):
                    summaries.append(f"· [{c.get('company_name', '')}] {n['ai_summary']}")

        if not summaries:
            return ""

        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.3,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            timeout=20,
        )

        text = "\n".join(summaries[:30])
        prompt = f"""以下是今日财经新闻摘要汇总，请用一句话概括今日市场主线（30 字以内）：

{text}

输出格式（只输出一句话）：
今日要点：..."""
        resp = llm.invoke([
            SystemMessage(content="你是一个财经主编。输出一句话总览。"),
            HumanMessage(content=prompt),
        ])
        overview = resp.content.strip().replace("今日要点：", "").strip()
        logger.info("AI 总览: %s", overview[:60])
        return overview
    except Exception as e:
        logger.warning("AI 总览失败: %s", e)
        return ""


# ────────── 新闻搜索（Bing） ──────────

def search_company_news(company_name: str, company_code: str) -> list[dict[str, str]]:
    """搜索某公司的近期新闻.

    使用 Bing News 搜索，返回新闻标题 + 链接。

    Returns:
        [{"title": str, "link": str, "snippet": str}, ...]
    """
    from backend.tools.news_search import _search_bing_news

    results = []
    try:
        items = _search_bing_news(f"{company_name} {company_code}", max_results=5)
        for r in items:
            results.append({
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
            })
    except Exception as e:
        logger.warning("搜索新闻失败 (%s): %s", company_name, e)

    return results
