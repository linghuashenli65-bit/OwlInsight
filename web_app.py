"""FinanceBot — 投资研究助手."""

import os
# 必须在任何第三方库导入之前设置
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import re, sys, uuid, warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", message="Accessing `__path__`")

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("NO_PROXY", "eastmoney.com,push2his.eastmoney.com,emot.dfcfw.com")

from backend.logger import logger

st.set_page_config(
    page_title="FinanceBot", page_icon="📊",
    layout="wide", initial_sidebar_state="expanded",
)

# ──────────────── 主题色板 ────────────────

T = {
    "dark": {
        "bg":            "#080808",
        "bg_alt":        "#0e0c0a",
        "card":          "#161412",
        "card_hover":    "#1e1b17",
        "border":        "#2a2520",
        "border_faint":  "#1c1814",
        "text":          "#e8e4db",
        "text_sec":      "#8c867c",
        "text_muted":    "#5c5650",
        "vermillion":    "#c41e3a",
        "vermillion_bg": "rgba(196,30,58,0.08)",
        "jade":          "#2d5a4a",
        "jade_bg":       "rgba(45,90,74,0.10)",
        "gold":          "#c9a96e",
        "gold_bg":       "rgba(201,169,110,0.08)",
        "user_grad_1":   "#c41e3a",
        "user_grad_2":   "#8b1a2b",
        "shadow":        "rgba(0,0,0,0.40)",
        "input_bg":      "#0e0c0a",
        "noise_opacity": "0.03",
    },
    "light": {
        "bg":            "#f8f6f2",
        "bg_alt":        "#f2f0ea",
        "card":          "#ffffff",
        "card_hover":    "#faf9f5",
        "border":        "#e0dbd0",
        "border_faint":  "#eee9e0",
        "text":          "#2a2520",
        "text_sec":      "#6b6560",
        "text_muted":    "#a09890",
        "vermillion":    "#b71c1c",
        "vermillion_bg": "rgba(183,28,28,0.05)",
        "jade":          "#2e7d32",
        "jade_bg":       "rgba(46,125,50,0.06)",
        "gold":          "#8d6e3b",
        "gold_bg":       "rgba(141,110,59,0.06)",
        "user_grad_1":   "#c41e3a",
        "user_grad_2":   "#8b1a2b",
        "shadow":        "rgba(0,0,0,0.06)",
        "input_bg":      "#ffffff",
        "noise_opacity": "0.02",
    },
}

# ──────────────── CSS 生成 ────────────────

NOISE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">'
    '<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/></filter>'
    '<rect width="100%" height="100%" filter="url(#n)" opacity="1"/></svg>'
)
NOISE_DATA_URI = f"data:image/svg+xml;base64,{NOISE_SVG.encode()}"


def css(t: str) -> str:
    c = T[t]
    return f"""<style>
:root {{
    --v: {c["vermillion"]}; --g: {c["jade"]}; --au: {c["gold"]};
}}

/* ── 全局 ── */
.stApp, .main {{ background: {c["bg"]} !important; color: {c["text"]}; }}
.stApp::before {{
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    opacity: {c["noise_opacity"]}; background-image: url("{NOISE_DATA_URI}");
}}
.block-container {{ padding: 1rem 2rem !important; max-width: 720px; margin: 0 auto; position: relative; z-index: 1; }}
#MainMenu, header, footer {{ display: none !important; }}
.stDeployButton, .stToolbar, .stAppToolbar {{ display: none !important; }}
div[data-testid="stDecoration"], div[data-testid="stHeader"], div[data-testid="stToolbar"] {{ display: none !important; }}

/* ── 品牌头 ── */
.brand-header {{
    display: flex; align-items: center; gap: 14px;
    padding: 8px 0 16px; margin-bottom: 20px;
    border-bottom: 1px solid {c["gold"]}22;
}}
.brand-mark {{
    width: 42px; height: 42px; border-radius: 4px;
    background: {c["vermillion"]};
    display: flex; align-items: center; justify-content: center;
    font-size: 1.3rem; color: #fff; font-family: Georgia, "Noto Serif SC", serif;
    font-weight: 700; flex-shrink: 0;
}}
.brand-text h1 {{
    font-family: Georgia, "Noto Serif SC", serif;
    font-size: 1.25rem; font-weight: 700; color: {c["text"]};
    margin: 0; letter-spacing: 0.02em;
}}
.brand-text p {{
    font-size: 0.75rem; color: {c["text_muted"]};
    margin: 2px 0 0 0; letter-spacing: 0.04em; text-transform: uppercase;
}}

/* ── 消息行 ── */
.msg-row {{
    display: flex; margin: 16px 0; gap: 12px;
    animation: fadeUp 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}}
@keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.msg-row.user {{ flex-direction: row-reverse; }}
.msg-avatar {{
    width: 32px; height: 32px; border-radius: 2px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.85rem; font-family: Georgia, serif;
}}
.msg-avatar.user {{ background: {c["vermillion_bg"]}; color: {c["vermillion"]}; }}
.msg-avatar.ai  {{ background: {c["card"]}; border: 1px solid {c["border"]}; color: {c["text_sec"]}; }}
.msg-bubble {{
    padding: 14px 20px; border-radius: 2px; line-height: 1.72;
    max-width: 82%; font-size: 0.93rem;
    position: relative;
}}
.msg-bubble::before {{
    content: ""; position: absolute; left: 0; top: 0; bottom: 0;
    width: 2px; background: {c["vermillion"]}; opacity: 0;
    transition: opacity 0.3s;
}}
.msg-bubble:hover::before {{ opacity: 1; }}
.msg-bubble.user {{
    background: linear-gradient(160deg, {c["user_grad_1"]}, {c["user_grad_2"]});
    color: #faf8f4; border-radius: 2px 2px 0 2px;
}}
.msg-bubble.user::before {{ display: none; }}
.msg-bubble.ai {{
    background: {c["card"]}; color: {c["text"]};
    border: 1px solid {c["border_faint"]};
    border-radius: 2px 2px 2px 0;
    box-shadow: 0 1px 4px {c["shadow"]};
}}
.msg-bubble.ai table {{
    font-size: 0.82em; border-collapse: collapse; margin: 10px 0;
    width: 100%; background: {c["bg_alt"]};
}}
.msg-bubble.ai th {{
    background: transparent; color: {c["vermillion"]};
    padding: 8px 12px; border-bottom: 2px solid {c["vermillion"]};
    font-weight: 600; text-align: left; font-family: Georgia, "Noto Serif SC", serif;
    font-size: 0.85em; letter-spacing: 0.03em;
}}
.msg-bubble.ai td {{
    padding: 7px 12px; border-bottom: 1px solid {c["border_faint"]};
    font-variant-numeric: tabular-nums; font-family: Georgia, serif;
}}
.msg-bubble.ai tr:last-child td {{ border-bottom: none; }}

/* ── 引用上标 Tooltip ── */
.cite-sup {{
    color: {c["vermillion"]}; font-weight: 600; cursor: help;
    font-size: 0.68em; vertical-align: super; position: relative;
    text-decoration: none; font-family: Georgia, serif;
}}
.cite-tip {{
    visibility: hidden; opacity: 0; position: absolute; bottom: 160%; left: 50%;
    transform: translateX(-50%); background: {c["card"]}; color: {c["text"]};
    padding: 6px 14px; border: 1px solid {c["border"]};
    font-size: 13px; white-space: nowrap; transition: all 0.25s;
    z-index: 9999; font-weight: 400; pointer-events: none;
    box-shadow: 0 4px 16px {c["shadow"]}; border-radius: 2px;
    font-family: Georgia, "Noto Serif SC", serif;
}}
.cite-sup:hover .cite-tip {{ visibility: visible; opacity: 1; }}

/* ── 思考过程 ── */
.think-wrap {{ margin: 6px 0 12px; }}
.think-step {{
    display: flex; align-items: center; gap: 10px;
    padding: 6px 12px; font-size: 0.8em; color: {c["text_sec"]};
    position: relative;
}}
.think-step::before {{
    content: ""; width: 6px; height: 6px; border-radius: 50%;
    background: {c["vermillion"]}; flex-shrink: 0; opacity: 0.5;
}}
.think-step:not(:last-child)::after {{
    content: ""; position: absolute; left: 14px; top: 18px;
    width: 1px; height: calc(100% - 2px);
    background: {c["border"]};
}}

/* ── 辅助卡片 ── */
.aux-card {{
    padding: 10px 16px; margin: 8px 0; font-size: 0.84em;
    border-radius: 2px; line-height: 1.6;
}}
.aux-card.hint  {{ background: {c["gold_bg"]};  border-left: 2px solid {c["gold"]};  color: {c["text_sec"]}; }}
.aux-card.status {{ background: {c["gold_bg"]};  border-left: 2px solid {c["gold"]}; }}
.aux-card.anomaly {{ background: {c["vermillion_bg"]}; border-left: 2px solid {c["vermillion"]}; }}
.aux-card.refs {{ background: {c["card"]}; border: 1px solid {c["border_faint"]}; }}
.aux-card.ingest {{ background: {c["card"]}; border: 1px solid {c["border"]}; border-left: 2px solid {c["vermillion"]}; }}

/* ── 欢迎页 ── */
.welcome {{
    text-align: center; padding: 60px 20px 32px;
    position: relative; z-index: 1;
}}
.welcome h2 {{
    font-family: Georgia, "Noto Serif SC", serif;
    font-size: 2.4rem; font-weight: 700;
    color: {c["vermillion"]}; margin: 0 0 8px;
    letter-spacing: 0.03em;
}}
.welcome .sub {{
    color: {c["text_sec"]}; font-size: 0.95rem;
    max-width: 460px; margin: 0 auto; line-height: 1.6;
}}
.welcome .features {{
    display: flex; justify-content: center; gap: 24px;
    margin: 20px 0 32px; font-size: 0.8em;
    color: {c["text_muted"]}; letter-spacing: 0.05em;
    text-transform: uppercase;
}}
.suggest-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
    max-width: 480px; margin: 0 auto;
}}
.suggest-grid button {{
    font-family: Georgia, "Noto Serif SC", serif !important;
    font-size: 0.88rem !important;
    text-align: left !important;
}}

/* ── 输入区 ── */
.input-area {{
    position: fixed; bottom: 0; left: 280px; right: 0;
    padding: 12px 24px 18px; background: {c["bg"]};
    border-top: 1px solid {c["border_faint"]}; z-index: 100;
}}
.block-container {{ padding-bottom: 90px !important; }}

/* ── Streamlit 组件覆盖 ── */
.stTextInput input {{
    background: {c["input_bg"]} !important; color: {c["text"]} !important;
    border: 1px solid {c["border"]} !important; border-radius: 2px !important;
    padding: 10px 16px !important; font-size: 0.92rem !important;
    font-family: Georgia, "Noto Serif SC", serif !important;
    transition: border-color 0.2s !important;
}}
.stTextInput input:focus {{
    border-color: {c["vermillion"]} !important;
    box-shadow: 0 0 0 1px {c["vermillion"]}22 !important;
}}
.stSpinner > div {{ border-color: {c["vermillion"]} !important; border-bottom-color: transparent !important; }}

/* ── 侧栏 ── */
section[data-testid="stSidebar"] {{
    background: {c["bg_alt"]} !important;
    border-right: 1px solid {c["border_faint"]}; width: 280px !important;
}}
section[data-testid="stSidebar"] .block-container {{ padding: 1.2rem 1rem !important; max-width: 100%; }}
section[data-testid="stSidebar"] hr {{ border-color: {c["border_faint"]} !important; }}
section[data-testid="stSidebar"] .stButton button {{
    background: transparent !important; color: {c["text_sec"]} !important;
    border: 1px solid {c["border_faint"]} !important; border-radius: 2px !important;
    font-size: 0.82rem !important; transition: all 0.2s !important;
    font-family: Georgia, "Noto Serif SC", serif !important;
    text-align: left !important; padding: 6px 12px !important;
}}
section[data-testid="stSidebar"] .stButton button:hover {{
    border-color: {c["gold"]} !important; color: {c["gold"]} !important;
    background: {c["gold_bg"]} !important;
}}
section[data-testid="stSidebar"] .stFileUploader {{
    background: {c["bg"]} !important; border: 1px dashed {c["border"]} !important;
    border-radius: 2px !important; padding: 6px !important;
}}
section[data-testid="stSidebar"] .stFileUploader:hover {{ border-color: {c["vermillion"]} !important; }}

/* ── 侧栏品牌 ── */
.sb-brand {{
    display: flex; align-items: center; gap: 10px;
    padding: 8px 4px 16px; margin-bottom: 12px;
    border-bottom: 1px solid {c["gold"]}22;
}}
.sb-mark {{
    width: 34px; height: 34px; border-radius: 2px;
    background: {c["vermillion"]};
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; color: #fff;
    font-family: Georgia, serif; font-weight: 700;
}}
.sb-name {{ font-size: 1rem; font-weight: 700; color: {c["text"]}; }}
.sb-sub  {{ font-size: 0.68rem; color: {c["text_muted"]}; letter-spacing: 0.04em; text-transform: uppercase; }}

/* ── 滚动条 ── */
::-webkit-scrollbar {{ width: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: {c["border"]}; border-radius: 0; }}
::-webkit-scrollbar-thumb:hover {{ background: {c["text_muted"]}; }}

/* ── Expander ── */
[data-testid="stExpander"] {{
    border: 1px solid {c["border_faint"]} !important;
    border-radius: 2px !important;
}}
[data-testid="stExpander"] details summary {{
    font-family: Georgia, "Noto Serif SC", serif !important;
    font-size: 0.82rem !important; color: {c["text_sec"]} !important;
}}
</style>"""


# ──────────────── Session State ────────────────

def init_state():
    for key, default in [
        ("messages", []), ("thread_id", str(uuid.uuid4())),
        ("theme", "dark"), ("ingest_result", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


# ──────────────── 后端 ────────────────

def _run_agent(text: str) -> dict:
    """调用 Agent，携带对话历史以实现上下文记忆。"""
    try:
        from backend.agent.graph import run_agent
        # 构造 LangGraph 格式的历史消息
        history = []
        for m in st.session_state.messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                history.append({"role": role, "content": content})
        return run_agent(
            text,
            thread_id=st.session_state.thread_id,
            history=history,
        )
    except Exception as e:
        return {"final_answer": f"分析异常: {e}", "streaming_steps": [],
                "citations": [], "anomalies": [], "data_status": []}


def _ingest_pdf(data: bytes, name: str) -> dict:
    from backend.ingestion.pipeline import ingest_document
    tmp = Path(__file__).parent / "data" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    fp = tmp / name
    fp.write_bytes(data)
    try:
        code = re.search(r"(\d{6})", name)
        code = code.group(1) if code else ""
        r = ingest_document(
            filepath=str(fp), company_code=code,
            doc_type="年报" if "年报" in name else "研报",
            doc_name=name.replace(".pdf", ""),
        )
        return {
            "success": r.success, "doc_name": r.doc_name,
            "total_pages": r.total_pages, "total_chunks": r.total_chunks,
            "total_tables": r.total_tables, "company": r.company,
            "company_code": r.company_code, "errors": r.errors,
            "elapsed_seconds": r.elapsed_seconds, "inserted_ids": r.inserted_ids,
        }
    finally:
        if fp.exists():
            fp.unlink()


# ──────────────── 渲染 ────────────────

def _render_body(text: str, citations: list[dict]) -> str:
    for c in citations:
        idx = c.get("index", 0)
        sup = (
            f'<sup class="cite-sup">[{idx}]'
            f'<span class="cite-tip">{c.get("detail", "")}</span></sup>'
        )
        text = text.replace(f"[{idx}]", sup)
    return text


def _render_ai_msg(idx: int, content: str, steps: list[str],
                   citations: list[dict], anomalies: list[dict],
                   status_list: list[str], hint: str):
    # 兴趣提示
    if hint:
        st.markdown(f'<div class="aux-card hint">◆ {hint}</div>', unsafe_allow_html=True)

    # 思考过程
    if steps:
        with st.expander("— 分析过程", expanded=False):
            st.markdown(
                '<div class="think-wrap">' +
                "".join(f'<div class="think-step">{s}</div>' for s in steps) +
                "</div>",
                unsafe_allow_html=True,
            )

    # 正文
    body = _render_body(content, citations)
    st.markdown(
        f'<div class="msg-row">'
        f'<div class="msg-avatar ai">B</div>'
        f'<div class="msg-bubble ai">{body}</div>'
        f"</div>", unsafe_allow_html=True,
    )

    # 引用
    if citations:
        refs = "".join(f"<br>[{c['index']}] {c['detail']}" for c in citations)
        st.markdown(
            f'<div class="aux-card refs">'
            f'<span style="color:{T[st.session_state.theme]["text_muted"]};'
            f'font-size:0.78em;letter-spacing:0.06em;text-transform:uppercase;">'
            f'引用来源</span>{refs}</div>',
            unsafe_allow_html=True,
        )

    # 数据状态
    if status_list:
        items = "".join(f"<br>• {s}" for s in status_list)
        st.markdown(
            f'<div class="aux-card status">⚠ 数据状态{items}</div>',
            unsafe_allow_html=True,
        )

    # 异常
    if anomalies:
        items = "".join(
            f'<br>• <b>{a["metric"]}</b>: {a.get("value","")}'
            f'（{a.get("change","")}）— {a.get("description","")}'
            for a in anomalies
        )
        st.markdown(
            f'<div class="aux-card anomaly">◆ 发现异常指标{items}</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(len(anomalies[:3]))
        for ai, a in enumerate(anomalies[:3]):
            with cols[ai]:
                if st.button(f"分析 {a['metric']}", key=f"ano_{idx}_{ai}"):
                    st.session_state.quick_input = f"详细分析{a['metric']}变化原因"

    # 导出
    if st.button("导出 Markdown", key=f"exp_{idx}"):
        md = _build_md(content, steps, citations, status_list)
        st.download_button(
            "下载", md,
            file_name=f"financebot_{datetime.now():%Y%m%d_%H%M%S}.md",
            mime="text/markdown", key=f"dl_{idx}",
        )


def _build_md(content: str, steps: list[str],
              citations: list[dict], status_list: list[str]) -> str:
    parts = [
        f"# FinanceBot 分析报告",
        f"*{datetime.now():%Y-%m-%d %H:%M}*\n",
    ]
    if steps:
        parts.append("## 分析过程")
        parts.extend(f"- {s}" for s in steps)
        parts.append("")
    parts.append("## 分析结果\n" + content + "\n")
    if citations:
        parts.append("## 引用来源")
        parts.extend(f"[{c['index']}] {c['detail']}" for c in citations)
    if status_list:
        parts.append("\n## 数据状态")
        parts.extend(f"- {s}" for s in status_list)
    return "\n".join(parts)


# ──────────────── 侧栏 ────────────────

def sidebar():
    t = st.session_state.theme
    c = T[t]
    with st.sidebar:
        st.markdown(
            f'<div class="sb-brand">'
            f'<div class="sb-mark">B</div>'
            f'<div><div class="sb-name">FinanceBot</div>'
            f'<div class="sb-sub">Investment Research</div></div>'
            f"</div>",
            unsafe_allow_html=True,
        )

        # 主题
        label = "☀ 浅色" if t == "dark" else "◉ 暗色"
        if st.button(label, use_container_width=True, key="theme_btn"):
            st.session_state.theme = "light" if t == "dark" else "dark"
            st.rerun()

        # 新建对话
        if st.button("＋ 新建对话", use_container_width=True, key="new_chat"):
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()

        st.divider()

        # PDF 导入
        with st.expander("导入 PDF", expanded=False):
            uploaded = st.file_uploader("上传 PDF", type=["pdf"], label_visibility="collapsed")
            if uploaded:
                with st.spinner("解析中..."):
                    r = _ingest_pdf(uploaded.getvalue(), uploaded.name)
                    st.session_state.ingest_result = r
                    st.markdown(_ingest_html(r), unsafe_allow_html=True)

        # 关注公司
        with st.expander("关注的公司", expanded=True):
            try:
                from backend.memory.store import memory_store
                memory_store.connect()
                companies = memory_store.get_all_watched_companies()
                if companies:
                    for co in companies[:8]:
                        label = f"{co['company_name']} {co['analysis_count']}次"
                        if st.button(label, key=f"co_{co['company_code']}",
                                     use_container_width=True):
                            st.session_state.quick_input = f"分析{co['company_name']}最新财务"
                else:
                    st.caption("暂无关注公司")
            except Exception:
                st.caption("暂无数据")

        # 笔记
        with st.expander("研究笔记", expanded=False):
            try:
                from backend.tools.note_tools import list_research_notes
                notes = list_research_notes(limit=10)
                if notes:
                    for n in notes[:6]:
                        name = n.get("company", n.get("code", ""))
                        created = str(n.get("created", ""))[:10] if n.get("created") else ""
                        label = f"{name}  {created}" if created else name
                        if st.button(label, key=f"note_{n.get('path','')}",
                                     use_container_width=True):
                            try:
                                ct = Path(n["path"]).read_text("utf-8")
                                with st.expander("预览", expanded=True):
                                    st.markdown(ct[:400])
                            except Exception:
                                pass
                else:
                    st.caption("暂无笔记")
            except Exception:
                st.caption("暂无数据")

        st.divider()
        st.caption(f"v1.0 · {st.session_state.thread_id[:6]}")


def _ingest_html(r: dict) -> str:
    if r.get("success"):
        return (
            f'<div class="aux-card ingest">'
            f'✓ 导入完成 {r.get("doc_name","")}<br>'
            f'{r.get("total_pages",0)}页 · {r.get("total_chunks",0)}块'
            f'{" · " + str(r.get("total_tables",0)) + "表格" if r.get("total_tables") else ""}'
            f'<br>⏱ {r.get("elapsed_seconds",0):.1f}s'
            f'</div>'
        )
    errs = "".join(f"<br>• {e}" for e in r.get("errors", []))
    return f'<div class="aux-card ingest">✗ 导入失败{errs}</div>'


# ──────────────── 主区域 ────────────────

def main_area():
    t = st.session_state.theme
    c = T[t]

    # 品牌头
    st.markdown(
        '<div class="brand-header">'
        '<div class="brand-mark">B</div>'
        '<div class="brand-text"><h1>FinanceBot</h1>'
        '<p>Investment Research</p></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    # 欢迎页
    if not st.session_state.messages:
        st.markdown(
            f'<div class="welcome">'
            f'<h2>墨与朱</h2>'
            f'<p class="sub">个人投资研究助手 — 有来源、可追溯、懂你的分析</p>'
            f'<div class="features"><span>模糊问答</span><span>学术引用</span><span>越用越懂</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        suggestions = [
            ("茅台最近怎么样", "模糊意图反问"),
            ("对比茅台和五粮液", "多公司对比分析"),
            ("分析宁德时代估值", "估值 + 行业对比"),
            ("回顾上次分析", "从历史中回顾"),
        ]
        cols = st.columns(2)
        for i, (query, desc) in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(f"{query}\n— {desc}", key=f"sg_{i}",
                             use_container_width=True):
                    _submit(query)

    # 消息流
    for i, msg in enumerate(st.session_state.messages):
        if msg.get("role") == "user":
            st.markdown(
                f'<div class="msg-row user">'
                f'<div class="msg-avatar user">U</div>'
                f'<div class="msg-bubble user">{msg["content"]}</div>'
                f"</div>", unsafe_allow_html=True,
            )
        else:
            _render_ai_msg(
                i, msg.get("content", ""), msg.get("steps", []),
                msg.get("citations", []), msg.get("anomalies", []),
                msg.get("data_status", []), msg.get("hint", ""),
            )

    # 输入栏
    st.markdown('<div class="input-area">', unsafe_allow_html=True)
    c1, c2 = st.columns([6, 1])
    with c1:
        inp = st.text_input(
            "发送消息", placeholder="输入问题…",
            label_visibility="collapsed", key="chat_input",
        )
    with c2:
        sent = st.button("发送", type="primary", use_container_width=True)
    if sent and inp.strip():
        _submit(inp.strip())
    st.markdown("</div>", unsafe_allow_html=True)

    # 导入结果（一次性展示）
    if st.session_state.ingest_result:
        st.markdown(_ingest_html(st.session_state.ingest_result), unsafe_allow_html=True)
        st.session_state.ingest_result = None


def _submit(text: str):
    st.session_state.messages.append({"role": "user", "content": text})
    with st.spinner("…"):
        result = _run_agent(text)

    answer = result.get("final_answer") or "(暂未获取到数据)"
    steps = result.get("streaming_steps", [])
    raw_c = result.get("citations", [])
    raw_a = result.get("anomalies", [])
    status = result.get("data_status", [])

    citations = []
    for c in raw_c:
        if hasattr(c, "index"):
            citations.append({"index": c.index, "source": c.source, "detail": c.detail})
        elif isinstance(c, dict) and "index" in c:
            citations.append(c)
    anomalies = []
    for a in raw_a:
        if hasattr(a, "metric"):
            anomalies.append({"metric": a.metric, "value": a.value,
                              "change": a.change, "description": a.description})
        elif isinstance(a, dict):
            anomalies.append(a)

    hint = ""
    if answer.startswith("[提示]"):
        parts = answer.split("\n", 1)
        hint = parts[0].replace("[提示]", "").strip()
        answer = parts[1] if len(parts) > 1 else ""

    st.session_state.messages.append({
        "role": "assistant", "content": answer, "steps": steps,
        "citations": citations, "anomalies": anomalies,
        "data_status": status, "hint": hint,
    })
    st.rerun()


# ──────────────── 入口 ────────────────

def main():
    init_state()
    st.markdown(css(st.session_state.theme), unsafe_allow_html=True)
    try:
        from backend.config import settings
        settings.ensure_dirs()
    except Exception:
        pass
    sidebar()
    main_area()


if __name__ == "__main__":
    main()
