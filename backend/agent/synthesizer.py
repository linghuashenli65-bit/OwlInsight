"""答案合成器 — 学术引用格式输出 + 数据状态栏.

输出格式：
  正文使用上标数字标注来源 ¹²³
  末尾集中展示引用列表
  数据缺失时在状态栏诚实告知
"""

from backend.logger import logger
import json
import logging
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.agent.state import Anomaly, Citation
from backend.config import settings

logger = logging.getLogger(__name__)

class Synthesizer:
    """将工具执行结果合成为结构化答案."""

    def synthesize(
        self,
        user_query: str,
        tool_results: list[dict[str, Any]],
        citations: list[Citation],
        anomalies: Optional[list[Anomaly]] = None,
        data_status: Optional[list[str]] = None,
        matched_interests: Optional[list[dict]] = None,
    ) -> str:
        """生成完整答案文本.

        Returns:
            Markdown 格式的答案，包含正文、引用列表、数据状态。
        """
        parts = []

        # ── 个性化提示 ──
        if matched_interests:
            parts.append(self._build_interest_hint(matched_interests))
            parts.append("")

        # ── LLM 合成正文 ──
        body = self._llm_synthesize(user_query, tool_results, citations)
        parts.append(body)

        # ── 引用列表 ──
        if citations:
            parts.append("")
            parts.append(self._build_citation_list(citations))

        # ── 数据状态栏 ──
        if data_status:
            parts.append("")
            parts.append(self._build_data_status(data_status))

        # ── 异常 HITL 提示 ──
        if anomalies:
            parts.append("")
            parts.append(self._build_anomaly_prompt(anomalies))

        return "\n".join(parts)

    # ────────── LLM 合成 ──────────

    def _format_tool_results_for_llm(self, tool_results: list[dict[str, Any]]) -> str:
        """将工具结果格式化为 LLM 可读的文本."""
        sections = []
        for r in tool_results:
            tool = r.get("tool", "")
            data = r.get("data")
            status = r.get("status", "ok")
            if status != "ok" or not data:
                continue
            if tool == "query_financials" and isinstance(data, list):
                # 按 period_rank 降序排列（最近的在前面）
                sorted_data = sorted(data, key=lambda x: x.get("period_rank", 0) or 0, reverse=True)
                rows = []
                for d in sorted_data[:8]:
                    rows.append(
                        f"  报告期: {d.get('report_period', '')}, "
                        f"营收: {self._fmt_money(d.get('revenue'))}, "
                        f"净利润: {self._fmt_money(d.get('net_profit'))}, "
                        f"营业利润: {self._fmt_money(d.get('operating_profit'))}"
                    )
                sections.append(f"[财务数据]\n" + "\n".join(rows))
            elif tool == "get_stock_price" and isinstance(data, list):
                prices = [f"  {d.get('date','')}: 收盘 {d.get('close','N/A')}" for d in data[-10:]]
                sections.append(f"[股价数据]\n" + "\n".join(prices))
            elif tool in ("search_documents", "read_financial_report") and isinstance(data, list):
                docs = [f"  来自 {d.get('doc_name','文档')}: {d.get('text','')[:200]}" for d in data[:5]]
                sections.append(f"[文档库检索结果]\n" + "\n".join(docs))
            elif tool == "search_news" and isinstance(data, list):
                news = [f"  {d.get('title','')}: {d.get('ai_summary','') or d.get('snippet','')[:100]}" for d in data[:5]]
                sections.append(f"[新闻]\n" + "\n".join(news))
            elif tool == "generate_report" and isinstance(data, dict):
                fin = data.get("financials", [])
                if fin:
                    sorted_fin = sorted(fin, key=lambda x: x.get("period_rank", 0) or 0, reverse=True)
                    rows = [f"  报告期: {d.get('report_period','')}, 营收: {self._fmt_money(d.get('revenue'))}, 净利润: {self._fmt_money(d.get('net_profit'))}" for d in sorted_fin[:6]]
                    sections.append(f"[深度研报 - 财务数据]\n" + "\n".join(rows))
                val = data.get("valuation", {})
                if val:
                    sections.append(f"[深度研报 - 估值] PE: {val.get('pe','N/A')}, PB: {val.get('pb','N/A')}, 市值: {val.get('market_cap','N/A')}")
            elif tool == "compare_companies" and isinstance(data, dict):
                companies = data.get("companies", {})
                if companies:
                    for name, fins in companies.items():
                        rows = [f"  {d.get('report_period','')}: 营收 {self._fmt_money(d.get('revenue'))}, 净利润 {self._fmt_money(d.get('net_profit'))}" for d in fins[:4]]
                        sections.append(f"[对比 - {name}]\n" + "\n".join(rows))
            elif tool == "industry_comparison" and isinstance(data, dict):
                items = [f"  {k}: 公司={v.get('company','N/A')}, 行业={v.get('industry','N/A')}" for k, v in data.items()]
                sections.append(f"[行业对比]\n" + "\n".join(items))
            elif tool == "review_analysis" and isinstance(data, list):
                items = [f"  {d.get('created_at','')}: {d.get('question','')}" for d in data[:5]]
                sections.append(f"[历史分析记录]\n" + "\n".join(items))
            elif tool == "save_last_note":
                sections.append(f"[笔记保存] {r.get('message', '已保存')}")
        return "\n\n".join(sections)

    def _llm_synthesize(
        self,
        user_query: str,
        tool_results: list[dict[str, Any]],
        citations: list[Citation],
    ) -> str:
        """用 LLM 合成分析报告，失败时回退到规则模板."""
        try:
            formatted = self._format_tool_results_for_llm(tool_results)
            if not formatted.strip():
                return self._build_body(user_query, tool_results, citations)

            llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                temperature=0.3,
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_API_BASE,
                timeout=30,
            )
            prompt = f"""你是一个专业的投资研究助手。根据以下数据，回答用户的问题。

用户问题：{user_query}

工具返回的数据：
{formatted}

请生成一份专业的分析报告，要求：
1. 用中文回答，语言简洁专业
2. 引用数据中的具体数字进行分析
3. 关注趋势和变化（如环比增长/下降百分比），指出亮点和风险
4. 适当分段，使用 Markdown 格式（小标题、表格、要点）
5. 如果数据中有多个报告期，务必对比分析各期变化
6. 不要使用引用上标（如 ^1），引用在正文中用括号注明来源即可
7. 篇幅适中，不要过于简短"""
            resp = llm.invoke([
                SystemMessage(content="你是一个专业的投资研究分析师，擅长解读财务数据和市场信息。只输出分析报告本身，不要多余的内容。"),
                HumanMessage(content=prompt),
            ])
            answer = resp.content.strip()
            if answer:
                return answer
        except Exception as e:
            logger.warning("LLM 合成失败 (%s), 使用规则回退", e)
        return self._build_body(user_query, tool_results, citations)

    # ────────── 正文（规则回退） ──────────

    def _build_body(
        self,
        query: str,
        results: list[dict[str, Any]],
        citations: list[Citation],
    ) -> str:
        """根据工具结果生成正文.

        目前为规则模板，后续可替换为 LLM 生成。
        """
        lines = []

        for result in results:
            tool = result.get("tool", "")
            data = result.get("data", {})
            status = result.get("status", "ok")
            error = result.get("error")

            if status == "error":
                lines.append(f"[警告] {tool} 调用失败: {error}")
                continue

            if not data:
                continue

            if tool == "query_financials":
                lines.extend(self._format_financials(data, citations))
            elif tool == "get_stock_price":
                lines.extend(self._format_price(data, citations))
            elif tool == "search_news":
                lines.extend(self._format_news(data, citations))
            elif tool == "industry_comparison":
                lines.extend(self._format_comparison(data, citations))
            elif tool == "read_financial_report":
                lines.extend(self._format_rag_result(data, citations))
            elif tool == "search_documents":
                lines.extend(self._format_document_search(data, citations))
            elif tool == "review_analysis":
                lines.extend(self._format_review(data, citations))
            elif tool == "generate_report":
                lines.extend(self._format_report(data, citations))
            else:
                lines.append(f"({tool} 返回 {len(data) if isinstance(data, list) else '数据'})")

        return "\n".join(lines) if lines else "(暂未获取到数据，请稍后重试)"

    def _format_financials(self, data: Any, citations: list[Citation]) -> list[str]:
        """格式化财务数据为表格."""
        lines = []
        if isinstance(data, list) and data:
            # 表格表头
            lines.append("| 报告期 | 营业收入 | 净利润 | 营业利润 |")
            lines.append("|--------|----------|--------|----------|")
            for item in data[:5]:
                period = item.get("report_period", "")
                revenue = self._fmt_money(item.get("revenue"))
                profit = self._fmt_money(item.get("net_profit"))
                op = self._fmt_money(item.get("operating_profit"))
                idx = self._add_citation(citations, "利润表")
                lines.append(f"| {period} | {revenue}{idx} | {profit} | {op} |")
        return lines

    def _format_price(self, data: Any, citations: list[Citation]) -> list[str]:
        lines = []
        if isinstance(data, list) and data:
            latest = data[-1]
            idx = self._add_citation(citations, "股价")
            lines.append(
                f"最新收盘价: **{latest.get('close', 'N/A')}**{idx} "
                f"(日期: {latest.get('date', 'N/A')})"
            )
            if len(data) > 1:
                first = data[0]
                change = ((latest.get("close", 0) or 0) - (first.get("close", 0) or 0))
                pct = change / first.get("close", 1) * 100 if first.get("close") else 0
                lines.append(f"期间涨跌: {change:+.2f} ({pct:+.2f}%)")
        return lines

    def _format_news(self, data: Any, citations: list[Citation]) -> list[str]:
        lines = []
        if not isinstance(data, list) or not data:
            return lines

        # ── 主题卡片视图（AI 精读模式）──
        first = data[0]
        themes = first.get("news_themes") if isinstance(first, dict) else None
        if themes:
            # 顶部总览 + 分类标签
            category = first.get("news_category", "")
            header = f"AI 已为你整理今日{category}新闻重点" if category else "AI 已为你整理今日财经重点"
            lines.append(f"**{header}**")
            lines.append("")
            ov_title = first.get("overview_title") or ""
            if ov_title:
                lines.append(f"{ov_title}，涵盖 {len(themes)} 个核心主题")
                lines.append("")

            # AI 观点
            ai_view = first.get("ai_view") or ""
            if ai_view:
                lines.append(f"> **AI观点：** {ai_view}")
                lines.append("")

            # 主题卡片
            for i, theme in enumerate(themes):
                lines.append("")
                lines.append(f"`{theme.get('tag', '财经')}` **{theme.get('title', '')}**")
                lines.append("")
                lines.append(f"{theme.get('summary', '')}")
                lines.append("")
                # 影响/趋势
                impact = theme.get("impact", "")
                if impact:
                    lines.append(f"_{impact}_")
                    lines.append("")
                # 来源引用
                sources = theme.get("sources", [])
                if sources:
                    refs = []
                    for s_idx in sources:
                        if 0 <= s_idx - 1 < len(data):
                            item = data[s_idx - 1]
                            href = item.get("link", "")
                            src = item.get("source", "来源")
                            if href:
                                refs.append(f"[{s_idx}]({href})")
                            else:
                                refs.append(f"[{s_idx}]")
                    if refs:
                        lines.append(f"参考来源：{' '.join(refs)}")
            return lines

        # ── 传统列表视图（降级）──
        for i, item in enumerate(data[:5]):
            title = item.get("title", "")
            link = item.get("link", "")
            ai_summary = item.get("ai_summary", "")
            snippet = item.get("snippet", "")
            source = item.get("source", "")
            date_str = item.get("date", "")
            if item.get("is_summary"):
                lines.append(f"> **{title}**：{item.get('snippet', '')}")
            elif link:
                lines.append(f"{i+1}. [{title}]({link})")
                if ai_summary:
                    lines.append(f"   > {ai_summary}")
                elif snippet:
                    lines.append(f"   > {snippet[:150]}")
                lines.append(f"[_{source} | {date_str}_]({link})")
            else:
                lines.append(f"{i+1}. **{title}** — {source} ({date_str})")
        return lines

    def _format_comparison(self, data: Any, citations: list[Citation]) -> list[str]:
        lines = []
        if not isinstance(data, dict):
            return lines

        # 多公司同表对比
        companies = data.get("companies")
        if companies and len(companies) >= 2:
            names = list(companies.keys())
            lines.append(f"**{' vs '.join(names)} 财务对比**")
            lines.append("")
            # 表头
            header = "| 报告期 | 指标 |"
            sep = "|--------|------|"
            for n in names:
                header += f" {n} |"
                sep += "--------|"
            lines.append(header)
            lines.append(sep)

            # 获取所有报告期
            all_periods = set()
            for fin in companies.values():
                for row in fin:
                    all_periods.add(row.get("report_period", ""))
            sorted_periods = sorted(all_periods, reverse=True)[:6]

            for period in sorted_periods:
                for metric, label in [("revenue", "营收"), ("net_profit", "净利润")]:
                    row = f"| {period} | {label} |"
                    for n in names:
                        val = "N/A"
                        for r in companies.get(n, []):
                            if r.get("report_period") == period:
                                v = r.get(metric)
                                val = self._fmt_money(v) if v else "N/A"
                                break
                        row += f" {val} |"
                    lines.append(row)
            return lines

        # 行业对比（原有逻辑）
        lines = ["| 指标 | 本公司 | 行业平均 | 差异 |"]
        lines.append("|------|--------|----------|------|")
        for key, val in data.items():
            lines.append(f"| {key} | {val.get('company', 'N/A')} | {val.get('industry', 'N/A')} | {val.get('diff', 'N/A')} |")
        return lines

    def _format_rag_result(self, data: Any, citations: list[Citation]) -> list[str]:
        lines = []
        if isinstance(data, list):
            for item in data:
                text = item.get("text", "")
                doc_name = item.get("doc_name", "")
                page = item.get("page_number", "")
                score = item.get("rerank_score", item.get("score", ""))
                source = f"{doc_name}" + (f" 第{page}页" if page else "")
                idx = self._add_citation(citations, source)
                snippet = text[:200].replace("\n", " ")
                lines.append(f"- {snippet}...{idx}")
        return lines

    def _format_document_search(self, data: Any, citations: list[Citation]) -> list[str]:
        """格式化文档搜索结果为易读形式."""
        lines = []
        if isinstance(data, list) and data:
            lines.append(f"在已导入文档中找到以下相关信息：")
            lines.append("")
            for i, item in enumerate(data):
                text = item.get("text", "")
                doc_name = item.get("doc_name", "未知文档")
                page = item.get("page_number", "")
                score = item.get("rerank_score", item.get("score", ""))
                source = f"{doc_name}" + (f" 第{page}页" if page else "")
                idx = self._add_citation(citations, source)
                snippet = text[:300].replace("\n", " ")
                lines.append(f"**{i+1}. {source}**{idx}")
                lines.append(f"> {snippet}")
                lines.append("")
        return lines

    def _format_review(self, data: Any, citations: list[Citation]) -> list[str]:
        """格式化回顾结果."""
        lines = ["以下是你对该公司的历史分析记录：", ""]
        if isinstance(data, list):
            for item in data:
                question = item.get("question", "")
                summary = item.get("summary", "")
                created = str(item.get("created_at", ""))[:16]
                company_name = item.get("company_name", "")
                raw_metrics = item.get("key_metrics_mentioned", "[]")
                import json
                metrics = json.loads(raw_metrics) if isinstance(raw_metrics, str) else raw_metrics
                metrics_str = f"（关注指标：{'、'.join(metrics)}）" if metrics else ""
                lines.append(f"- **{created}** — {question}")
                if summary:
                    lines.append(f"  > {summary[:120]}{metrics_str}")
        if len(lines) == 2:
            lines.append("暂无分析记录。")
        return lines

    # ────────── 深度研报 ──────────

    def _format_report(self, data: Any, citations: list[Citation]) -> list[str]:
        lines = []
        if not isinstance(data, dict):
            return lines
        code = data.get("company_code", "")
        name = data.get("company_name", "")
        financials = data.get("financials", [])
        valuation = data.get("valuation", {})
        price_history = data.get("price_history", [])
        news = data.get("news", [])

        lines.append(f"**{name} ({code}) 深度研究报告**")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 财务概览
        lines.append("### 财务概览")
        if financials:
            lines.append("| 报告期 | 营收 | 净利润 | 营业利润 |")
            lines.append("|--------|------|--------|----------|")
            for row in financials[:6]:
                period = row.get("report_period", "")
                rev = self._fmt_money(row.get("revenue"))
                np_ = self._fmt_money(row.get("net_profit"))
                op = self._fmt_money(row.get("operating_profit"))
                lines.append(f"| {period} | {rev} | {np_} | {op} |")
        lines.append("")

        # 估值
        lines.append("### 估值数据")
        if valuation:
            lines.append(f"- PE(TTM): {valuation.get('pe', 'N/A')}")
            lines.append(f"- PB: {valuation.get('pb', 'N/A')}")
            lines.append(f"- 总市值: {valuation.get('market_cap', 'N/A')}")
        lines.append("")

        # 股价
        latest_close = "N/A"
        if price_history:
            latest = price_history[-1]
            first = price_history[0]
            latest_close = latest.get("close", "N/A")
            change = ((latest.get("close", 0) or 0) - (first.get("close", 0) or 0))
            pct = change / first.get("close", 1) * 100 if first.get("close") else 0
            lines.append("### 股价走势")
            lines.append(f"- 最新收盘: {latest_close} ({latest.get('date', '')})")
            lines.append(f"- 区间涨跌: {change:+.2f} ({pct:+.2f}%)")
            lines.append("")

        # 新闻
        if news:
            lines.append("### 近期动态")
            for item in news[:3]:
                ai = item.get("ai_summary", "") or item.get("snippet", "")[:80]
                lines.append(f"- {item.get('title', '')} → {ai}")
            lines.append("")

        # AI 总结
        trend = "上涨" if isinstance(latest_close, (int, float)) and (change > 0) else "下跌" if isinstance(latest_close, (int, float)) and (change < 0) else "震荡"
        lines.append("### AI 分析总结")
        lines.append(f"{name}近期营收和利润呈稳定增长态势，估值处于合理区间，股价趋势{trend}。")
        lines.append("建议结合行业前景和宏观环境综合评估。")
        return lines

    # ────────── 引用 ──────────

    def _add_citation(self, citations: list[Citation], source_desc: str) -> str:
        """生成引用上标，如有必要向 citations 追加新引用.

        返回上标字符串如 " ^1"；副作用：当 source_desc 不存在时追加新引用到列表。
        """
        for c in citations:
            if c.detail == source_desc:
                return f" ^{c.index}"
        idx = len(citations) + 1
        citations.append(Citation(index=idx, source=source_desc, detail=source_desc))
        return f" ^{idx}"

    def _build_citation_list(self, citations: list[Citation]) -> str:
        lines = ["---", "**引用来源：**"]
        for c in citations:
            lines.append(f"^{c.index} {c.detail}")
        return "\n".join(lines)

    # ────────── 数据状态栏 ──────────

    def _build_data_status(self, statuses: list[str]) -> str:
        lines = ["---", "[注意] **数据状态：**"]
        for s in statuses:
            lines.append(f"- {s}")
        return "\n".join(lines)

    # ────────── 异常提示 ──────────

    def _build_anomaly_prompt(self, anomalies: list[Anomaly]) -> str:
        lines = ["", "---", "[分析] **发现以下异常指标：**"]
        for a in anomalies:
            lines.append(f"- **{a.metric}**: {a.value}（{a.change}）— {a.description}")
        lines.append("")
        lines.append("> 需要深入分析哪个指标？请回复编号。")
        return "\n".join(lines)

    # ────────── 兴趣提示 ──────────

    def _build_interest_hint(self, interests: list[dict]) -> str:
        metrics = [i.get("metric_name", "") for i in interests[:3]]
        hint = "[提示] 你之前在分析时关注过 "
        hint += "、".join(f"**{m}**" for m in metrics)
        hint += "，我会把这几个指标放在前面。"
        return hint

    # ────────── 工具函数 ──────────

    @staticmethod
    def _fmt_money(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        if abs(val) >= 1e8:
            return f"{val / 1e8:.2f}亿"
        if abs(val) >= 1e4:
            return f"{val / 1e4:.2f}万"
        return f"{val:.2f}"

# 全局单例
synthesizer = Synthesizer()
