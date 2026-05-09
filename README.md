# 枭研 (OwlInsight) — 金融投资研究助手

A股/港股智能分析助手，基于 LLM Agent + RAG 架构，支持多轮对话分析、文档导入检索、实时行情监控与分时段告警推送。

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                   前端 (Next.js 15)                    │
│  Chat UI · 图表渲染 · 文档管理 · 告警面板 · 设置页    │
└───────────────┬──────────────────┬──────────────────┘
                │ SSE (流式响应)    │ WebSocket (行情)
┌───────────────▼──────────────────▼──────────────────┐
│              后端 (FastAPI + uvicorn)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ Chat API  │ │ Data API │ │ 告警调度 (APScheduler)│ │
│  │ SSE 流式  │ │ CRUD     │ │ 盘前/盘中/盘后 三段  │ │
│  └─────┬────┘ └──────────┘ └──────────────────────┘ │
└───────┬──────────────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────────────┐
│            LLM Agent (LangGraph)                      │
│  意图分类 → 关注提取 → 工具执行 → 检查点 → 综合回答 │
│  工具: 股价查询 · 财报分析 · 新闻搜索 · RAG 检索 ·   │
│        笔记存储 · 估值数据                            │
└───────┬──────────────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────────────┐
│              数据层                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ Milvus   │ │  SQLite  │ │ Redis (缓存)          │ │
│  │ 向量检索  │ │  持久化   │ │ GET 缓存 60s 失效      │ │
│  │ 文档chunk │ │  对话/笔记│ │ documents_list/notes  │ │
│  └──────────┘ └──────────┘ └──────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

## 核心功能

### 1. 智能对话分析 (LLM Agent)
- **意图分类**：自动判断用户意图（股价查询、财报分析、新闻检索、闲聊等）
- **工具编排**：根据意图自动调用金融数据工具，多步推理
- **流式输出**：SSE 实时推送 token/推理过程/引用来源/数据异常
- **上下文记忆**：自动跟踪关注公司，支持多轮追问

### 2. 金融数据工具
| 工具 | 数据源 | 覆盖 |
|------|--------|------|
| 股价查询 | akshare (腾讯/东方财富) | A股 + 港股日线/周线/月线，含 K 线图 |
| 财报分析 | akshare | 利润表/资产负债表/现金流量表 |
| 新闻搜索 | NewsData.io / 新浪 | 实时财经新闻 + AI 摘要 |
| 估值数据 | akshare | PE/PB/ROE 等 |
| RAG 文档检索 | Milvus + bge-m3 | 上传文档的语义检索 |

### 3. 文档导入与检索
- PDF 上传解析：pyMuPDF 提取文本 + 表格结构识别
- 智能元数据提取：自动识别公司名、代码、文档类型
- 向量化存储：bge-m3 嵌入 + Milvus 向量库
- 重排序：bge-reranker-v2-m3 提升召回精度

### 4. 分时段告警系统
| 时段 | 时间 | 内容 |
|------|------|------|
| 盘前 | 08:30 | 隔夜新闻摘要 + 大盘指数 + 热门板块 + 关注公司新闻 |
| 盘中 | 09:30-15:00 | 价格异动检测(±5%) + 资金流异常 + SSE 实时弹窗 |
| 盘后 | 15:30 | 当日行情总结 + 涨跌排行 + 重大事件回顾 |

通知方式：邮件 (SMTP) + 前端 SSE 弹窗

### 5. 研究笔记
- 自动保存分析结果到 SQLite，按公司聚合
- 模糊搜索（内容/公司/标签）
- 前端高亮匹配关键词

### 6. 对话历史持久化
- 所有对话自动保存，刷新不丢失
- 侧边栏对话列表，支持切换/删除/重命名
- LLM 自动生成对话标题

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 前端框架 | Next.js 15 + React 19 | UI 渲染 |
| 状态管理 | Zustand | 全局状态 (chat/alert/sidebar) |
| 样式 | Tailwind CSS 3.4 | 响应式设计 |
| 图标 | Lucide React | UI 图标 |
| 后端框架 | FastAPI + uvicorn | REST + SSE + WebSocket |
| LLM Agent | LangGraph | 多步推理编排 |
| LLM | GPT-4o / Claude | 语义理解与生成 |
| 嵌入模型 | BAAI/bge-m3 | 文本向量化 |
| 重排序 | BAAI/bge-reranker-v2-m3 | 检索精排 |
| 向量库 | Milvus | 语义检索 |
| 缓存 | Redis | GET 接口缓存 (60s TTL) |
| 持久化 | SQLite | 对话/笔记/配置存储 |
| 调度 | APScheduler | 告警定时任务 |
| 行情数据 | akshare (腾讯/东方财富) | 股价/财报/估值 |
| 新闻 | NewsData.io / 新浪 | 实时财经新闻 |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Redis 7+（可选，缓存降级不影响核心功能）
- Milvus 2.4+（向量库，用于文档检索）
- 至少 8GB 可用内存（本地嵌入模型约占用 4GB）

### 1. 后端

```bash
# 克隆后进入项目根目录
cd FinanceBot

# Python 虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\activate

# 安装依赖
pip install -r backend/requirements.txt

# 注意：以下依赖可能需要单独安装（akshare 常用的数据源依赖）
pip install akshare langgraph pymilvus redis apscheduler

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 等配置

# 启动 Milvus（Docker）
docker run -d --name milvus-standalone -p 19530:19530 milvusdb/milvus:latest

# 启动 Redis（Docker，端口已映射到 6380）
docker run -d --name redis-finance -p 6380:6379 redis:7-alpine

# 启动后端（开发模式）
python -m backend.main
# 或
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8897
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`。

### 3. 验证

```bash
# 后端健康检查
curl http://localhost:8897/api/health
# → {"status":"ok","name":"枭研","version":"1.0.0"}
```

在浏览器打开 `http://localhost:3000`，即可进入对话界面。

## 项目结构

```
FinanceBot/
├── backend/
│   ├── main.py                    # FastAPI 入口 + 路由注册 + 生命周期
│   ├── config.py                  # 全局配置 (Pydantic BaseSettings)
│   ├── logger.py                  # 日志配置
│   ├── stock_map.py               # 股票代码映射 (43+ 常用公司)
│   ├── cache.py                   # Redis 缓存工具
│   ├── database/                  # MySQL 模型（可选）
│   ├── agent/
│   │   ├── graph.py               # LangGraph Agent 编排 (5 节点)
│   │   ├── router.py              # 意图分类 + 工具路由
│   │   ├── synthesizer.py         # 综合回答生成
│   │   └── state.py               # Agent 状态定义
│   ├── tools/
│   │   ├── financial_data.py      # 股价/财报/估值工具
│   │   ├── news_search.py         # 新闻搜索工具
│   │   ├── rag_tools.py           # RAG 文档检索工具
│   │   ├── note_tools.py          # 笔记存储工具
│   │   └── valuation.py           # 估值数据工具
│   ├── memory/
│   │   ├── store.py               # SQLite 持久化 (对话/笔记/配置)
│   │   └── interest_tracker.py    # 关注公司跟踪
│   ├── rag/
│   │   ├── vector_store.py        # Milvus 向量存储
│   │   ├── embeddings.py          # bge-m3 嵌入
│   │   ├── retriever.py           # 检索 + 重排序
│   │   └── reranker.py            # bge-reranker-v2-m3
│   ├── ingestion/
│   │   ├── pipeline.py            # 文档导入流程编排
│   │   ├── pdf_parser.py          # PDF 解析 + 元数据提取
│   │   └── chunker.py             # 文本分块策略
│   ├── alerter/
│   │   ├── engine.py              # APScheduler 调度引擎
│   │   ├── detector.py            # 事件检测 (价格/新闻/资金流)
│   │   └── notifier.py            # 通知分发 (邮件/SSE)
│   ├── routers/
│   │   ├── chat.py                # 对话 API + SSE 流式
│   │   ├── data.py                # 数据 CRUD (公司/笔记)
│   │   ├── ingest.py              # 文档上传/列表/删除
│   │   ├── alerter.py             # 告警配置/事件/SSE
│   │   └── settings.py            # 应用设置
│   └── websocket_handler.py       # WebSocket 行情推送
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx           # 主页面 (侧边栏 + 告警面板 + 主内容)
│   │   │   └── layout.tsx         # 根布局
│   │   ├── components/
│   │   │   ├── chat/              # 对话组件
│   │   │   │   ├── ChatMain.tsx   # 对话主区域
│   │   │   │   ├── ChatSidebar.tsx # 侧边栏 (对话列表/关注/笔记/上传)
│   │   │   │   ├── MessageItem.tsx # 消息项 (Markdown/图表/引用)
│   │   │   │   ├── InputArea.tsx   # 输入框
│   │   │   │   ├── StockChart.tsx  # SVG 折线图 / K 线图
│   │   │   │   ├── StockDetail.tsx # 股价详情卡片
│   │   │   │   ├── CitationText.tsx # 引用来源
│   │   │   │   ├── AnomalyCard.tsx  # 数据异常卡片
│   │   │   │   └── ... 
│   │   │   ├── sidebar/           # 侧边栏子组件
│   │   │   ├── pages/             # 页面组件
│   │   │   ├── alerter/           # 告警 UI
│   │   │   │   ├── AlertBell.tsx   # 铃铛图标 + 未读计数
│   │   │   │   └── AlertPanel.tsx  # 通知列表面板
│   │   │   └── ui/                # 通用 UI 组件
│   │   ├── store/                 # Zustand 状态
│   │   │   ├── chatStore.ts       # 对话状态 + SSE 同步
│   │   │   ├── alertStore.ts      # 告警状态 + SSE 连接
│   │   │   ├── navStore.ts        # 导航状态
│   │   │   └── settingsStore.ts   # 设置状态
│   │   ├── lib/
│   │   │   ├── api.ts             # HTTP API 封装
│   │   │   └── types.ts           # TypeScript 类型定义
│   │   └── services/
│   │       └── chatService.ts     # SSE 事件分发
│   └── package.json
├── data/                          # 数据目录 (gitignored)
│   ├── memory.db                  # SQLite 数据库
│   ├── vector_store/              # Milvus 持久化
│   ├── research_notes/            # 文件笔记 (旧格式)
│   └── tmp/                       # 临时上传文件
├── .env.example                   # 环境变量模板
├── .gitignore
└── README.md
```

## 配置说明

所有配置通过环境变量或 `.env` 文件管理，前缀均为 `FINANCEBOT_`。详见 `.env.example`。

### 关键配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FINANCEBOT_LLM_API_KEY` | — | LLM API 密钥 |
| `FINANCEBOT_LLM_MODEL` | `gpt-4o` | 模型名称 |
| `FINANCEBOT_LLM_API_BASE` | — | API 代理地址 |
| `FINANCEBOT_MILVUS_URI` | `http://localhost:19530` | Milvus 地址 |
| `FINANCEBOT_EMBEDDING_MODEL` | `BAAI/bge-m3` | 嵌入模型 |
| `FINANCEBOT_BACKEND_PORT` | `8897` | 后端端口 |

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/chat/stream` | 对话 SSE 流 |
| `GET` | `/api/chat/conversations` | 对话历史列表 |
| `POST` | `/api/chat/conversations` | 创建对话 |
| `GET` | `/api/chat/conversations/{id}` | 对话详情 |
| `DELETE` | `/api/chat/conversations/{id}` | 删除对话 |
| `POST` | `/api/chat/conversations/{id}/generate-title` | AI 生成标题 |
| `POST` | `/api/ingest/pdf` | 上传 PDF 文档 |
| `GET` | `/api/ingest/documents` | 文档列表 |
| `DELETE` | `/api/ingest/documents` | 删除文档 |
| `GET` | `/api/data/notes` | 笔记列表 |
| `GET` | `/api/data/notes/search` | 笔记搜索 |
| `DELETE` | `/api/data/notes/{id}` | 删除笔记 |
| `GET` | `/api/data/companies` | 关注公司列表 |
| `DELETE` | `/api/data/companies/{code}` | 删除关注公司 |
| `GET` | `/api/alerter/config` | 告警配置 |
| `PUT` | `/api/alerter/config` | 保存告警配置 |
| `GET` | `/api/alerter/events` | 告警事件列表 |
| `GET` | `/api/alerter/events/stream` | SSE 告警推送 |
| `WS` | `/ws/prices` | WebSocket 实时行情 |

## 开发说明

### 提交规范

提交信息遵循 `<type>: <description>` 格式：

- `feat`: 新功能
- `fix`: 修复
- `refactor`: 重构
- `docs`: 文档
- `chore`: 杂项

### 提示

- 本地嵌入模型首次运行时会自动从 HuggingFace 下载，约 2GB
- 港股数据通过腾讯财经 API (`ak.stock_zh_a_hist_tx`) 获取，无需代理
- Redis 不可用时缓存降级为内存，不影响核心功能
- 告警功能依赖 SMTP 邮箱配置，未配置时只走 SSE 前端推送
