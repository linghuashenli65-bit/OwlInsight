"""FinanceBot Web UI — Streamlit 应用.

功能：
- 对话式问询
- 流式输出思考过程
- 学术引用格式（上标 + 悬停来源）
- RAG 原文可折叠展示
- 文档拖拽上传
"""

import logging
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.agent.graph import run_agent
from src.agent.synthesizer import synthesizer
from src.config import settings
from src.tools.note_tools import list_research_notes

logger = logging.getLogger(__name__)

# ────────── 页面配置 ──────────

st.set_page_config(
    page_title="FinanceBot - 投资研究助手",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────── 初始化 Session State ──────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    import uuid
    st.session_state.thread_id = str(uuid.uuid4())

# ────────── 侧边栏 ──────────

with st.sidebar:
    st.title("📊 FinanceBot")
    st.caption("个人投资研究助手")

    st.divider()

    # 新建对话
    if st.button("🔄 新建对话", use_container_width=True):
        st.session_state.messages = []
        import uuid
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

    st.divider()

    # 研究笔记
    with st.expander("📝 研究笔记历史"):
        notes = list_research_notes(limit=10)
        if notes:
            for n in notes:
                st.caption(f"**{n['company']}** ({n['created'][:10] if n['created'] else '未知'})")
        else:
            st.caption("暂无研究笔记")

    st.divider()
    st.caption(f"LLM: {settings.LLM_MODEL}")
    st.caption(f"嵌入: {settings.EMBEDDING_MODEL}")

# ────────── 主界面 ──────────

st.title("📊 FinanceBot")
st.caption("问你的投资研究问题，我会检索数据、分析并给出有来源的答案")

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # 如果有思考步骤，展示为可折叠
        if "steps" in msg and msg["steps"]:
            with st.expander("🔍 思考过程", expanded=False):
                for step in msg["steps"]:
                    st.text(step)

        # 如果有引用，显示为可悬停
        if "citations" in msg and msg["citations"]:
            for c in msg["citations"]:
                st.caption(f"^{c['index']} {c['detail']}")

# ────────── 聊天输入 ──────────

if prompt := st.chat_input("输入你的投资问题..."):
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 处理
    with st.chat_message("assistant"):
        placeholder = st.empty()
        step_placeholder = st.empty()

        # 运行 Agent
        result = run_agent(prompt, thread_id=st.session_state.thread_id)

        final_answer = result.get("final_answer", "")
        steps = result.get("streaming_steps", [])
        citations = [{"index": c.index, "detail": c.detail}
                     for c in result.get("citations", [])]
        anomalies = result.get("anomalies", [])

        # 显示思考过程
        if steps:
            with st.expander("🔍 思考过程", expanded=True):
                for step in steps:
                    st.text(step)

        # 显示答案
        if final_answer:
            placeholder.markdown(final_answer)
        else:
            placeholder.info("暂未获取到数据。请确保已配置 API Key 且网络连接正常。")

        # 显示异常提示
        if anomalies:
            for a in anomalies:
                st.warning(f"**{a.metric}**: {a.description}")

    # 保存到历史
    st.session_state.messages.append({
        "role": "assistant",
        "content": final_answer or "(无输出)",
        "steps": steps,
        "citations": citations,
    })
