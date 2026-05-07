"""答案合成器 — 学术引用格式输出 + 数据状态栏.

输出格式：
  正文使用上标数字标注来源 ¹²³
  末尾集中展示引用列表
  数据缺失时在状态栏诚实告知
"""

import logging
import re
from typing import Any, Optional

from src.agent.state import Anomaly, Citation

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

        # ── 正文（暂时用简单摘要，Phase 4 集成 LLM 生成） ──
        body = self._build_body(user_query, tool_results, citations)
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

    # ────────── 正文 ──────────

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
        if isinstance(data, list):
            for i, item in enumerate(data[:5]):
                title = item.get("title", "")
                source = item.get("source", "")
                date_str = item.get("date", "")
                lines.append(f"{i+1}. **{title}** — {source} ({date_str})")
        return lines

    def _format_comparison(self, data: Any, citations: list[Citation]) -> list[str]:
        lines = ["| 指标 | 本公司 | 行业平均 | 差异 |"]
        lines.append("|------|--------|----------|------|")
        if isinstance(data, dict):
            for key, val in data.items():
                lines.append(f"| {key} | {val.get('company', 'N/A')} | {val.get('industry', 'N/A')} | {val.get('diff', 'N/A')} |")
        return lines

    def _format_rag_result(self, data: Any, citations: list[Citation]) -> list[str]:
        lines = []
        if isinstance(data, list):
            for item in data:
                text = item.get("text", "")
                source = f"{item.get('doc_name', '')} 第{item.get('page_number', '?')}页"
                idx = self._add_citation(citations, source)
                lines.append(f"- {text[:120]}...{idx}")
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
