"""通知分发 — 邮件发送 + SSE 弹窗推送.

邮件配置从 app_settings 读取（用户在前端设置页面填写）。
"""

import json
import smtplib
from backend.logger import logger
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Optional

from backend.memory.store import memory_store


# ────────── SSE 连接管理 ──────────

class SSEManager:
    """管理 SSE 告警推送的连接."""

    def __init__(self) -> None:
        self._connections: list[Any] = []

    def add(self, response: Any) -> None:
        self._connections.append(response)

    def remove(self, response: Any) -> None:
        if response in self._connections:
            self._connections.remove(response)

    async def broadcast(self, event: dict[str, Any]) -> None:
        """向所有连接的 SSE 客户端推送事件."""
        dead = []
        for conn in self._connections:
            try:
                data = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                await conn.write(data.encode("utf-8"))
            except Exception:
                dead.append(conn)
        for conn in dead:
            self._connections.remove(conn)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


sse_manager = SSEManager()


# ────────── 邮件发送 ──────────

def _get_email_settings() -> dict[str, str]:
    """从 SQLite alert_preferences 读取邮件配置."""
    all_prefs = memory_store.get_all_preferences()
    return {k: v for k, v in all_prefs.items() if k.startswith("alert_email_")}


def is_email_enabled() -> bool:
    """检查邮件推送是否开启."""
    s = _get_email_settings()
    return s.get("alert_email_enabled", "false").lower() == "true"


def get_email_time(setting_key: str, default: str) -> str:
    """获取邮件推送时间配置."""
    s = _get_email_settings()
    return s.get(setting_key, default)


def send_email(subject: str, html_body: str) -> bool:
    """通过 SMTP 发送 HTML 邮件.

    从 app_settings 读取 SMTP 配置，用户在前端设置页面填写。

    Returns:
        True 发送成功, False 失败。
    """
    s = _get_email_settings()
    host = s.get("alert_email_smtp_host", "")
    port = int(s.get("alert_email_smtp_port", "587"))
    user = s.get("alert_email_user", "")
    password = s.get("alert_email_password", "")
    from_addr = s.get("alert_email_from", user)
    to_addr = s.get("alert_email_to", user)

    if not host or not user or not password:
        logger.warning("SMTP 未完整配置，跳过邮件发送")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        logger.info("正在连接 SMTP %s:%s ...", host, port)
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(user, password)
                server.sendmail(from_addr, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(from_addr, [to_addr], msg.as_string())

        logger.info("邮件发送成功: %s -> %s", subject[:40], to_addr)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.warning("邮件认证失败 (%s): 请检查用户名/授权码是否正确", subject[:30])
        return False
    except smtplib.SMTPServerDisconnected:
        logger.warning("邮件服务器断开连接 (%s): 服务器主动关闭连接，请检查端口是否正确 (QQ邮箱用 465)", subject[:30])
        return False
    except TimeoutError:
        logger.warning("邮件连接超时 (%s): %s:%s 无法连接，请检查网络或 SMTP 地址", subject[:30], host, port)
        return False
    except Exception as e:
        logger.warning("邮件发送失败 (%s): %s", subject[:30], e)
        return False


# ────────── 邮件模板 ──────────

def render_pre_market_html(report: dict[str, Any], date_str: str) -> str:
    """渲染盘前邮件 HTML（含宏观经济、公司新闻、行业动态、风险提示）. """

    # ── AI 总览 ──
    overview = report.get("overview", "")
    overview_html = f'<div style="background:#fef8e7;border-left:4px solid #f0c040;padding:10px 14px;margin:0 0 16px 0;border-radius:4px;font-size:14px;color:#333;">📌 {overview}</div>' if overview else ""

    # ── 宏观新闻 ──
    macro_rows = ""
    for item in report.get("macro_news", []):
        desc = item.get("ai_summary", "") or item.get("snippet", "")[:200]
        macro_rows += f"""
        <tr><td style="padding:6px 8px;border-bottom:1px solid #eee;font-size:13px;">
            <div style="font-weight:bold;color:#333;">{item.get('title', '')}</div>
            <div style="color:#666;margin-top:2px;font-size:12px;">{desc}</div>
        </td></tr>"""

    # ── 公司新闻 ──
    company_rows = ""
    for item in report.get("company_alerts", []):
        news_html = ""
        for n in item.get("news", []):
            summary = n.get("ai_summary", "")
            title = n.get("title", "")
            news_html += f"""<div style="font-size:12px;color:#555;margin-top:4px;">
                <div style="font-weight:bold;">• {title}</div>
                {f'<div style="color:#888;margin:2px 0 0 12px;font-size:11px;">{summary}</div>' if summary else ''}
            </div>"""
        company_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold;font-size:13px;">{item.get('company_name', '')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;font-size:12px;color:#888;">{item.get('code', '')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;font-size:12px;">
                <div style="color:#555;">{item.get('summary', '')}</div>
                {news_html}
            </td>
        </tr>"""

    # ── 行业新闻 ──
    industry_rows = ""
    for item in report.get("industry_news", []):
        snippet = item.get("snippet", "")
        industry_rows += f"""
        <tr><td style="padding:6px 8px;border-bottom:1px solid #eee;font-size:13px;">
            <div style="color:#333;">{item.get('title', '')}</div>
            {f'<div style="color:#888;font-size:12px;margin-top:2px;">{snippet[:400]}</div>' if snippet else ''}
        </td></tr>"""

    # ── 风险提示 ──
    risk_html = ""
    for w in report.get("risk_warnings", []):
        risk_html += f"""<div style="font-size:12px;color:#c41e3a;margin-top:4px;">⚠ {w}</div>"""

    # ── 大盘指数 ──
    market_index = report.get("market_index", {})
    if market_index:
        idx_name = market_index.get("index_name", "")
        idx_val = market_index.get("value", 0)
        idx_chg = market_index.get("change_pct", 0)
        clr = "#e74c3c" if idx_chg < 0 else "#27ae60"
        arr = "▼" if idx_chg < 0 else "▲"
        market_index_html = f"""<h3 style="color:#333;font-size:15px;margin:20px 0 8px 0;padding-bottom:4px;border-bottom:2px solid #f0c040;">📊 昨日大盘表现</h3>
<table style="width:100%;border-collapse:collapse;">
<tr><td style="padding:8px;font-size:14px;color:#333;">{idx_name}</td>
<td style="padding:8px;font-size:14px;color:#333;">{idx_val}</td>
<td style="padding:8px;font-size:14px;color:{clr};font-weight:bold;">{arr} {abs(idx_chg):.2f}%</td></tr>
</table>"""
    else:
        market_index_html = ""

    # ── 热门板块 ──
    sectors = report.get("hot_sectors", [])
    if sectors:
        sector_rows = ""
        for s in sectors:
            sn = s.get("name", "")
            sc = s.get("change_pct", 0)
            s_clr = "#e74c3c" if sc < 0 else "#27ae60"
            s_arr = "▼" if sc < 0 else "▲"
            sector_rows += f"""<tr><td style="padding:6px 8px;border-bottom:1px solid #eee;font-size:13px;color:#333;">{sn}</td>
<td style="padding:6px 8px;border-bottom:1px solid #eee;font-size:13px;color:{s_clr};font-weight:bold;">{s_arr} {abs(sc):.2f}%</td></tr>"""
        hot_sectors_html = f"""<h3 style="color:#333;font-size:15px;margin:20px 0 8px 0;padding-bottom:4px;border-bottom:2px solid #f0c040;">🔥 今日热门板块</h3>
<table style="width:100%;border-collapse:collapse;">
<tr style="background:#f8f9fa;"><th style="padding:8px;text-align:left;font-size:12px;">板块</th><th style="padding:8px;text-align:left;font-size:12px;">涨跌幅</th></tr>
{sector_rows}
</table>"""
    else:
        hot_sectors_html = ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:'Microsoft YaHei',sans-serif;padding:20px;background:#f5f5f5;">
<div style="max-width:620px;margin:0 auto;background:white;border-radius:8px;padding:28px;">

<h2 style="color:#222;margin:0 0 4px 0;">📊 盘前简报</h2>
<p style="color:#888;font-size:13px;margin:0 0 8px 0;">{date_str} · 关注公司今日重要新闻与公告</p>

{overview_html}

<!-- 宏观经济 -->
<h3 style="color:#333;font-size:15px;margin:16px 0 8px 0;padding-bottom:4px;border-bottom:2px solid #f0c040;">📌 宏观经济 / 市场提示</h3>
<table style="width:100%;border-collapse:collapse;">{macro_rows}</table>

{market_index_html}

{hot_sectors_html}

<!-- 关注公司 -->
<h3 style="color:#333;font-size:15px;margin:20px 0 8px 0;padding-bottom:4px;border-bottom:2px solid #f0c040;">🏢 用户关注公司重要事件</h3>
<table style="width:100%;border-collapse:collapse;">
<tr style="background:#f8f9fa;">
<th style="padding:8px;text-align:left;font-size:12px;">公司</th>
<th style="padding:8px;text-align:left;font-size:12px;">代码</th>
<th style="padding:8px;text-align:left;font-size:12px;">摘要</th>
</tr>
{company_rows}
</table>

<!-- 行业新闻 -->
<h3 style="color:#333;font-size:15px;margin:20px 0 8px 0;padding-bottom:4px;border-bottom:2px solid #f0c040;">📈 行业新闻</h3>
<table style="width:100%;border-collapse:collapse;">{industry_rows or '<tr><td style="padding:8px;color:#888;font-size:12px;">暂无行业新闻</td></tr>'}</table>

<!-- 风险提示 -->
<h3 style="color:#333;font-size:15px;margin:20px 0 8px 0;padding-bottom:4px;border-bottom:2px solid #f0c040;">⚠ 风险提示</h3>
{risk_html or '<div style="font-size:12px;color:#888;">暂无风险提示</div>'}

<p style="color:#aaa;font-size:11px;margin-top:24px;padding-top:12px;border-top:1px solid #eee;">本邮件由 FinanceBot 自动生成</p>
</div></body></html>"""


def render_post_market_html(
    summaries: list[dict[str, Any]],
    date_str: str,
) -> str:
    """渲染盘后总结邮件 HTML."""
    items_html = ""
    for item in summaries:
        change = item.get("change_pct", 0)
        color = "#e74c3c" if change < 0 else "#27ae60"
        arrow = "▼" if change < 0 else "▲"
        items_html += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold">{item.get('company_name', '')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{item.get('code', '')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;color:{color};font-weight:bold">{arrow} {abs(change):.2f}%</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{item.get('close', '-')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{item.get('events', '无异常')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:'Microsoft YaHei',sans-serif;padding:20px;background:#f5f5f5;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;padding:24px;">
<h2 style="color:#333;margin-top:0;">📈 盘后总结 — {date_str}</h2>
<p style="color:#666;font-size:14px;">关注公司今日表现与事件回顾</p>
<table style="width:100%;border-collapse:collapse;margin-top:16px;">
<tr style="background:#f8f9fa;">
<th style="padding:8px;text-align:left;">公司</th><th style="padding:8px;text-align:left;">代码</th><th style="padding:8px;text-align:left;">涨跌幅</th><th style="padding:8px;text-align:left;">收盘价</th><th style="padding:8px;text-align:left;">事件</th>
</tr>
{items_html}
</table>
<p style="color:#999;font-size:12px;margin-top:20px;">本邮件由 FinanceBot 自动生成</p>
</div></body></html>"""
