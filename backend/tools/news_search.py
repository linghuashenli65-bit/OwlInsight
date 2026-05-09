"""新闻搜索工具 — 多引擎并行搜索 + AI 去重总结."""

from backend.logger import logger
from datetime import date, timedelta
from typing import Any, Optional
import concurrent.futures
import os as _os


# 新闻分类映射：检测中文类别 → 优化搜索词
_NEWS_CATEGORIES = {
    "国际": {"kw": ["国际", "全球", "世界", "海外", "国外", "foreign", "world", "global", "international"],
             "boost": "world international news",
             "lang": "zh-cn"},
    "科技": {"kw": ["科技", "技术", "数码", "互联网", "AI", "人工智能", "机器人", "芯片"],
             "boost": "technology tech news",
             "lang": "zh-cn"},
    "财经": {"kw": ["财经", "金融", "经济", "股市", "股票", "A股", "基金", "ETF"],
             "boost": "finance economy market news",
             "lang": "zh-cn"},
    "能源": {"kw": ["能源", "原油", "石油", "天然气", "新能源", "碳中和"],
             "boost": "energy oil gas news",
             "lang": "zh-cn"},
    "地产": {"kw": ["地产", "房地产", "楼市", "房产"],
             "boost": "real estate property news",
             "lang": "zh-cn"},
}


# ── 系统代理检测（Clash/V2Ray 常见端口）──
_SYSTEM_PROXY_CANDIDATES = [
    "http://127.0.0.1:7890",
    "http://127.0.0.1:10809",
    "http://127.0.0.1:1080",
    "http://127.0.0.1:8080",
]


def _find_proxy() -> str | None:
    """检测可用的系统代理。优先读环境变量，其次检测常见代理端口."""
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        val = _os.environ.get(key)
        if val:
            return val
    # 快速 socket 检测常见代理端口是否存活
    import socket
    for candidate in _SYSTEM_PROXY_CANDIDATES:
        try:
            host, port = candidate.split("://")[1].split(":")
            with socket.create_connection((host, int(port)), timeout=0.5):
                return candidate
        except Exception:
            continue
    return None


_PROXY_URL = _find_proxy()
if _PROXY_URL:
    logger.info("检测到系统代理: %s", _PROXY_URL)


def _detect_category(query: str) -> tuple[str, str]:
    """检测新闻分类，返回 (分类名, 增强搜索词)."""
    for cat, config in _NEWS_CATEGORIES.items():
        if any(kw in query for kw in config["kw"]):
            return cat, config["boost"]
    return "", ""


def _decompose_query(query: str, context: str = "") -> list[str]:
    """AI 将用户问题分解为多个搜索关键词."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        from backend.config import settings
        import json as _json

        if not settings.LLM_API_KEY:
            return [query]

        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.3,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            timeout=15,
        )

        context_section = f"\n对话上下文（之前讨论过的内容）：{context}\n" if context else ""
        prompt = f"""用户想搜索新闻："{query}"{context_section}
请将这个问题分解为 3-5 个具体的关键词，以便从多个角度搜索。

要求：
- 每个关键词是一个独立的搜索词
- 如果当前问题含糊（如"搜索一下"），根据对话上下文推断搜索方向
- 覆盖不同维度（如市场、政策、行业、公司等）
- 中英文均可
- 返回 JSON 数组

输出格式：{{"keywords": ["关键词1", "关键词2", "关键词3"]}}"""

        resp = llm.invoke([
            SystemMessage(content="你是一个新闻搜索策划。输出 JSON 关键词列表。"),
            HumanMessage(content=prompt),
        ])
        text = resp.content.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = _json.loads(text)
        keywords = parsed.get("keywords", [])
        if keywords:
            logger.info("AI 分解搜索词: %s → %s", query[:30], keywords)
            return keywords[:5]
    except Exception as e:
        logger.warning("AI 分解搜索词失败: %s", e)

    return [query]


def search_news(
    query: str,
    max_results: int = 5,
    days_back: int = 30,
    context: str = "",
) -> list[dict[str, Any]]:
    """多关键词并行搜索 + AI 主题总结.

    Args:
        query: 用户搜索词。
        max_results: 每路最多返回条数。
        context: 对话上下文，用于模糊搜索时推断方向。

    Returns:
        [{"title", "link", "snippet", "source", "date", "ai_summary"}, ...]
    """
    # 1. AI 分解为多个搜索词（带上下文，支持模糊推断）
    keywords = _decompose_query(query, context=context)
    category, boost = _detect_category(query)
    # 如果检测到分类，给每个关键词加上 boost
    if boost:
        keywords = [f"{kw} {boost}" if category in kw else kw for kw in keywords]

    # 2. 多关键词并行搜索
    all_items = _parallel_search(keywords, max_results)

    if not all_items:
        return []

    # 3. AI 去重 + 主题总结
    result = _ai_dedup_and_summarize(query, all_items, max_results)

    if category and result:
        result[0]["news_category"] = category

    return result


def _parallel_search(queries: list[str], max_results: int) -> list[dict[str, Any]]:
    """多关键词 × 多引擎并行搜索."""
    results = []
    tasks = []

    for q in queries:
        tasks.append((_search_bing_news, q, max_results))
        tasks.append((_search_bing_web, q, max_results))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fn, q, n) for fn, q, n in tasks]
        for f in concurrent.futures.as_completed(futures):
            try:
                items = f.result()
                if items:
                    results.extend(items)
            except Exception as e:
                logger.warning("搜索异常: %s", e)

    return results


def _try_fetch(url: str, headers: dict, method_name: str, proxy_url: str | None = None) -> tuple[str | None, str]:
    """用 urllib 尝试抓取 URL，可选代理或无代理."""
    import urllib.request
    try:
        if proxy_url:
            proxy_handler = urllib.request.ProxyHandler({
                "http": proxy_url,
                "https": proxy_url,
            })
        else:
            proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace"), method_name
    except Exception as e:
        logger.warning("Bing fetch %s 失败: %s", method_name, e)
    return None, method_name


# ── 国内财经 RSS 备选源 ──
_FALLBACK_NEWS_FEEDS = [
    ("东方财富 7x24", "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001&fields=f43,f44,f45,f46,f47,f48,f50,f51,f52,f58,f170,f171"),
    ("新浪财经 滚动", "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=10"),
]


def _search_fallback_news(query: str, max_results: int) -> list[dict[str, Any]]:
    """国内财经 RSS 备选（Bing 不可用时的后备方案）. """
    import urllib.request
    import json as _json

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    results = []
    for feed_name, feed_url in _FALLBACK_NEWS_FEEDS:
        try:
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(feed_url, headers=headers)
            with opener.open(req, timeout=10) as resp:
                text = resp.read().decode("utf-8", errors="replace")

            # 东方财富返回 JSON 格式
            data = _json.loads(text)
            if "data" in data and "diff" in data["data"]:
                for item in data["data"]["diff"][:max_results]:
                    title = item.get("f58", "") or item.get("f14", "")
                    if title and query.lower() in title.lower():
                        results.append({
                            "title": title,
                            "link": f"https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code={item.get('f12', '')}",
                            "snippet": item.get("f100", "") or f"{feed_name} 实时行情",
                            "source": "东方财富",
                            "date": date.today().isoformat(),
                        })
        except Exception as e:
            logger.warning("备选源 %s 抓取失败: %s", feed_name, e)

    return results[:max_results]


def _search_bing_news(query: str, max_results: int) -> list[dict[str, Any]]:
    """Bing News RSS 搜索（先代理后直连 + 双解析引擎）. """
    import time
    import random
    from urllib.parse import quote

    time.sleep(random.uniform(0.5, 1.5))

    url = f"https://www.bing.com/news/search?q={quote(query)}&format=rss"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    xml_content = None
    source_name = ""

    # 策略1: 有代理 → 先走代理（Bing 国际版，RSS 支持正常）
    if _PROXY_URL:
        xml_content, source_name = _try_fetch(url, headers, f"urllib(proxy:{_PROXY_URL})", _PROXY_URL)

    # 策略2: 无代理直连（可能被重定向到 cn.bing.com 首页）
    if not xml_content:
        xml_content, source_name = _try_fetch(url, headers, "urllib(no-proxy)")

    # 策略3: httpx fallback
    if not xml_content:
        try:
            import httpx
            params = {}
            if _PROXY_URL:
                params["proxy"] = _PROXY_URL
            with httpx.Client(timeout=15, follow_redirects=True, headers=headers, **params) as client:
                resp = client.get(url)
                resp.raise_for_status()
                xml_content = resp.text
                source_name = f"httpx(proxy:{_PROXY_URL})" if _PROXY_URL else "httpx(no-proxy)"
        except Exception as e:
            logger.warning("Bing News httpx fallback 失败: %s", e)

    if not xml_content:
        return []

    # 解析 XML（兼容 RSS 和 Atom）
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(xml_content, "xml")

        # RSS 格式
        items = soup.select("item")
        # Atom 格式
        if not items:
            items = soup.select("entry")

        results = []
        for item in items:
            title = ""
            link = ""
            desc = ""
            pub_date = ""
            source = ""

            if item.name == "item":
                # RSS
                title = item.title.get_text(strip=True) if item.title else ""
                link = item.link.get_text(strip=True) if item.link else ""
                desc = item.description.get_text(strip=True) if item.description else ""
                pub_date = item.pubDate.get_text(strip=True) if item.pubDate else ""
                source = item.source.get_text(strip=True) if item.source else _extract_source(link)
            else:
                # Atom
                title = item.title.get_text(strip=True) if item.title else ""
                link_el = item.select_one("link[href]")
                link = link_el.get("href", "") if link_el else ""
                desc = item.summary.get_text(strip=True) if item.summary else item.content.get_text(strip=True) if item.content else ""
                pub_date = item.published.get_text(strip=True) if item.published else item.updated.get_text(strip=True) if item.updated else ""
                source = item.source.get_text(strip=True) if item.source else _extract_source(link)

            if not title or not link:
                continue
            results.append({
                "title": title,
                "link": link,
                "snippet": desc[:500],
                "source": source,
                "date": pub_date[:10] if pub_date else date.today().isoformat(),
            })
            if len(results) >= max_results:
                break

        if results:
            logger.info("Bing News RSS 搜索成功 (q='%s'): %d 条 via %s", query[:30], len(results), source_name)
            return results

        # 无结果时保存 debug 信息
        logger.warning("Bing News RSS 无 item (q='%s'): %d bytes via %s → 可能是非 RSS 响应",
                       query[:30], len(xml_content), source_name)
        try:
            import tempfile
            dump = tempfile.mktemp(suffix=".html", prefix=f"bing_{abs(hash(query)) % 10000}_")
            with open(dump, "w", encoding="utf-8") as f:
                f.write(xml_content[:50000])
            logger.warning("已保存响应到 %s", dump)
        except Exception:
            pass

    except Exception as e:
        logger.warning("Bing News XML 解析失败 (q='%s'): %s", query[:30], e)

    # Bing 全失败 → fallback 到国内财经源
    logger.info("Bing 无结果，尝试国内财经备选源 (q='%s')", query[:30])
    fallback = _search_fallback_news(query, max_results)
    if fallback:
        logger.info("备选源返回 %d 条结果", len(fallback))
    return fallback


def _search_bing_web(query: str, max_results: int) -> list[dict[str, Any]]:
    """Bing 通用网页搜索（先代理后直连）. """
    import time
    import random
    from urllib.parse import quote

    time.sleep(random.uniform(0.5, 1.5))
    url = f"https://www.bing.com/search?q={quote(query)}&setlang=zh-cn"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    html_content = None
    source_name = ""

    # 策略1: 有代理 → 先走代理
    if _PROXY_URL:
        html_content, source_name = _try_fetch(url, headers, f"urllib(proxy:{_PROXY_URL})", _PROXY_URL)

    # 策略2: 无代理直连
    if not html_content:
        html_content, source_name = _try_fetch(url, headers, "urllib(no-proxy)")

    # 策略3: httpx fallback
    if not html_content:
        try:
            import httpx
            params = {}
            if _PROXY_URL:
                params["proxy"] = _PROXY_URL
            with httpx.Client(timeout=15, follow_redirects=True, headers=headers, **params) as client:
                resp = client.get(url)
                resp.raise_for_status()
                html_content = resp.text
                source_name = f"httpx(proxy:{_PROXY_URL})" if _PROXY_URL else "httpx(no-proxy)"
        except Exception as e:
            logger.warning("Bing Web httpx fallback 失败: %s", e)

    if not html_content:
        return []

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # 检查是否被重定向到首页
        title_tag = soup.select_one("title")
        if title_tag and "搜索 - Microsoft 必应" in title_tag.get_text():
            logger.warning("Bing Web 被重定向到首页 (q='%s') via %s", query[:30], source_name)
            return []

        results = []
        for item in soup.select(".b_algo"):
            title_el = item.select_one("h2 a")
            snippet_el = item.select_one(".b_caption p, .b_caption .b_snippet")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            if title and link:
                results.append({
                    "title": title,
                    "link": link,
                    "snippet": snippet[:300],
                    "source": _extract_source(link),
                    "date": date.today().isoformat(),
                })
                if len(results) >= max_results:
                    break
        return results
    except Exception as e:
        logger.warning("Bing Web 解析异常: %s", e)
    return []


def _ai_dedup_and_summarize(
    query: str, items: list[dict], max_results: int
) -> list[dict]:
    """AI 去重 + 抓正文 + 主题分组描述."""
    if not items:
        return []

    # 1. 先去重
    seen = set()
    unique = []
    for item in items:
        key = item.get("link", "") or item.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    items = unique[:max_results * 2]

    # 2. 并行抓正文
    contents = _fetch_articles_parallel(items[:max_results])

    # 3. AI 主题分组（替换原来的逐条摘要）
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        from backend.config import settings

        if settings.LLM_API_KEY:
            themes = _ai_theme_group(query, items[:max_results], contents)
            if themes:
                # 将主题分组数据存入 items[0] 的 news_themes 字段
                items[0]["news_themes"] = themes
                items[0]["is_theme_view"] = True
    except Exception as e:
        logger.warning("AI 主题分组失败: %s", e)

    return items[:max_results]


def _ai_theme_group(
    query: str, items: list[dict], contents: dict[int, str]
) -> list[dict]:
    """将新闻按主题分组，生成 AI 描述型内容."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from backend.config import settings
    import json as _json

    # 构建文章输入
    articles_input = ""
    for i, item in enumerate(items):
        art = contents.get(i, "") or item.get("snippet", "")
        title = item.get("title", "")
        if art:
            articles_input += f"\n[{i+1}] {title}\n{art[:400]}\n"

    if not articles_input.strip():
        return []

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0.3,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        timeout=30,
    )

    prompt = f"""你是一个财经主编。请阅读以下新闻素材，按主题分组，输出描述型卡片。

用户搜索: "{query}"

要求：
1. 将相关文章合并为 2-4 个主题
2. 每个主题包含：
   - tag: 标签（如 "宏观" "ETF" "新能源" "原油"），用 2-4 个字
   - title: 主题标题（10 字以内）
   - summary: 一段 60-100 字描述，把该主题下所有信息融合成连贯的文字
   - impact: 影响或趋势判断（30-50 字）
   - sources: 引用来源序号（如 [1][2]）
3. 忽略不相关或低质量内容
4. 用主编视角提炼，不是堆叠搜索结果

文章素材：
{articles_input}

输出 JSON（纯 JSON 数组，不要 markdown 包裹）：
[{{"tag": "宏观", "title": "市场风险情绪升温", "summary": "...", "impact": "...", "sources": [1, 2]}}]"""

    try:
        resp = llm.invoke([
            SystemMessage(content="你是一个财经主编。输出 JSON 格式的主题卡片。"),
            HumanMessage(content=prompt),
        ])
        text = resp.content.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = _json.loads(text)

        # 同时生成 AI 总览
        _add_ai_overview(query, items, contents, llm)

        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        logger.warning("主题分组解析失败: %s", e)
        return []


def _add_ai_overview(
    query: str, items: list[dict], contents: dict[int, str], llm
) -> None:
    """生成 AI 总览和观点."""
    try:
        import json as _json

        titles = "\n".join(f"- {item['title']}" for item in items[:5] if item.get("title"))
        prompt = f"""以下是一组财经新闻标题，请完成两个任务：

1. 写一句总览标题（10 字以内），概括今天的新闻主线
2. 写一句 AI 观点（30-50 字），从投资者角度给出见解

新闻标题：
{titles}

输出 JSON：
{{"overview_title": "...", "ai_view": "..."}}"""

        resp = llm.invoke([
            SystemMessage(content="你是一个财经主编。输出 JSON。"),
            HumanMessage(content=prompt),
        ])
        text = resp.content.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = _json.loads(text)
        items[0]["overview_title"] = parsed.get("overview_title", "今日财经要点")
        items[0]["ai_view"] = parsed.get("ai_view", "")
    except Exception:
        pass


def _fetch_articles_parallel(items: list[dict]) -> dict[int, str]:
    """并行获取文章正文."""
    import httpx
    from bs4 import BeautifulSoup
    import concurrent.futures

    def fetch_one(idx: int, url: str) -> tuple[int, str]:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
            with httpx.Client(timeout=8, follow_redirects=True, headers=headers) as c:
                resp = c.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in ("article", ".article", ".content", "#content", ".maintext", "main"):
                    container = soup.select_one(tag)
                    if container:
                        texts = container.get_text(separator="\n", strip=True)
                        if len(texts) > 100:
                            return idx, texts[:2000]
                paras = [p.get_text(strip=True) for p in soup.select("p") if len(p.get_text(strip=True)) > 30]
                if paras:
                    return idx, "\n".join(paras)[:2000]
                return idx, ""
        except Exception:
            return idx, ""

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = []
        for i, item in enumerate(items):
            if item.get("link"):
                futures.append(pool.submit(fetch_one, i, item["link"]))
        for f in concurrent.futures.as_completed(futures):
            idx, text = f.result()
            results[idx] = text
    return results


def _extract_source(url: str) -> str:
    """从 URL 中提取来源名称."""
    from urllib.parse import urlparse
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "").split(".")[0][:20]
    except Exception:
        return ""
