# FinanceBot — 个人投资研究 Agent 实施计划

## 一、Context

### Why this project?
个人投资者做投资决策时，信息极其分散：财报 PDF、券商研报、新闻公告、行情数据、个人笔记散落在各处。Bloomberg Terminal 门槛极高，免费的通用 RAG（如 Dify 知识库）只能做简单的文档问答，不能主动调用外部数据源做计算和分析。市面上已有的开源项目（如 ai-hedge-fund）聚焦于**自动化交易信号**，而非**投资研究辅助**，两者定位不同。

### 与现有方案的区别
| 项目 | 定位 | 区别 |
|---|---|---|
| Dify 知识库 | 通用文档问答 | 无工具调用，无计算分析能力 |
| ai-hedge-fund | 自动化交易 Agent | 目标是下单交易，多 Agent 做决策 |
| **本项目 (FinanceBot)** | **个人研究助手** | **RAG + 工具调用，辅助人的决策，不做交易** |

### 设计原则（来自用户视角）
1. **问得舒服** — 听得懂模糊问题，接得住复杂问题
2. **答得透明** — 思考过程可见，不搞黑箱
3. **结果可信** — 每句话有来源，数据缺失不隐瞒
4. **越用越懂你** — 记得你做过的分析，关注过的公司
5. **输出好用** — 表格直观，引用清爽，可导出可回顾

---

## 二、整体架构

```
用户提问
    │
    ▼
┌──────────────────────────┐
│  Intent Classifier        │ ← 模糊 → 反问澄清
│  + User Interest Matcher  │ ← 多意图 → 拆解并行
│  (匹配历史关注点)         │ ← 匹配到 → 前置用户关心的指标
└──────────┬───────────────┘
           │
           ▼ (流式输出思考过程)
┌──────────────────────────┐
│  Tool Executor            │ 并行调用多个工具 + RAG（时间感知）
│  (含中间结论展示)         │ ← 关键步骤暂停，问用户是否深入
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Synthesizer              │
│  ├ 学术引用格式           │ ← 正文 ¹²，末尾集中引用列表
│  ├ Streamlit Tooltip      │ ← 悬停看来源详情
│  ├ RAG 原文可折叠         │ ← "展开阅读原文" 2-3句上下文
│  ├ 表格化呈现             │ ← 对比类强制表格
│  └ 数据状态栏             │ ← 缺失数据诚实告知
└──────────────────────────┘
```

---

## 三、核心流程

```
[用户输入："茅台最近怎么样？"]
    │
    ▼
[Intent Classifier]
    ├→ 明确意图 → 直接路由
    └→ 模糊意图 → 反问："你是想了解股价走势、最近一期财务数据、还是新闻动态？"
                    │
                    ▼ 用户回答后
               [Intent Classifier] 再次判断
    │
    ▼ (匹配历史关注点)
[User Interest Matcher]
    "历史分析记录显示，你最近 3 次关注茅台时都在问毛利率和销售费用，
    我会把这两个指标放在前面。"
    │
    ▼ (流式输出思考过程)
[Tool Executor — 时间感知]
    步骤 1: query_financials(茅台, period_rank=[-3,-2,-1])  → "最近三期"自动取排序
    步骤 2: get_stock_price(茅台, 近1月)
    步骤 3: search_news(茅台)
    │
    ▼ (发现异常指标，暂停)
[HITL Checkpoint] "我注意到销售费用环比增长了30%，要深入分析原因吗？
                  另外营收增长5%低于行业平均12%，要展开看吗？
                  PS: 你之前几次也在关注成本端，所以把毛利率变化也放在前面了。"
    │
    ▼ 用户选择
[Synthesizer]
    正文输出：
      贵州茅台 2024 年营收同比增长 5%¹，毛利率 72.3%²，
      较去年同期下降 3 个百分点³。销售费用环比增长 30%⁴...
    
    末尾引用列表：
      ¹ [来源: 茅台2024年报, 利润表, p12]
      ² [来源: akshare 财务数据]
      ³ [来源: 茅台2024年报 vs 2023年报, 毛利率对比]
      ⁴ [来源: 茅台2024年报, 销售费用明细, p34]
      ⚠ 数据状态: 2024Q4现金流量表未获取到，已用Q3数据替代
    
    └─ [自动保存研究笔记] + [更新历史关注点: 毛利率、销售费用]
```

---

## 四、模块拆分

### Module 1: Data Ingestion Pipeline（数据导入管线）

**功能**：将各类投资文档导入向量库

| 数据源 | 格式 | 解析方式 | 分块策略 |
|---|---|---|---|
| 财报 PDF | PDF | PyMuPDF / Unstructured | 按章节（资产负债表/利润表/现金流）|
| 券商研报 | PDF | PyMuPDF | 按段落 + 表格单独提取 |
| 个人研究笔记 | Markdown | 直接解析 | 按标题层级分块 |
| 公告TXT | TXT | 直接解析 | 按段落 |

**元数据增强（核心）**：
- 每个 chunk 携带：company、doc_type、doc_name
- **报告期排序字段**：财报在导入时自动计算 `period_rank`（2024Q4=0, 2024Q3=-1, 2024Q2=-2...），支持按排序取"最近 N 期"
- **日期排序**：研报按 report_date，新闻按 publish_date
- **表格标志**：table_flag + 列名列表，支持按列名搜索

**上传 PDF 的反馈闭环**：
```
用户拖入 PDF → 解析完成 → 回显解析摘要：
  ✅ 成功导入 200 页年报
  ✅ 提取到 15 张财务表格
  ✅ 识别为：贵州茅台 2024 年度合并报表
  ✅ 报告期归类：2024Q4（自动标注 period_rank=0）
  ❌ 第 45-52 页为扫描图片，仅支持文字搜索，不支持表格提取
  你可以试试问："茅台2024年营收多少"
```

**技术选型**：Unstructured.io（主）+ Camelot（表格）

### Module 2: RAG Engine（检索增强）

**功能**：混合检索 + 结构化数据查询 + 时间感知

**检索策略**：
```
用户问题 → LLM 提取 query + 过滤器(公司/时间范围/报告期排序)
         │
         ├── 语义检索 → Milvus (嵌入模型: bge-m3)
         ├── 关键字检索 → BM25 (配合 jieba 中文分词)
         ├── 表格检索 → 单独索引表格数据，按列名匹配
         ├── 结构化查询 → akshare API 获取实时数据
         └── 时间感知 → "最近三期" → period_rank=[-3,-2,-1]
                         "2024年报" → doc_type=年报 & date=2024
```

**时间感知核心逻辑**：
- "最近三期财报" → LLM 提取过滤器 `{period_rank: {gte: -3}}` → 直接取 collection 元数据排序
- 不需要 LLM 猜测具体季度名称，避免因"三季报 vs Q3 报告"命名不一致漏检
- 研报按 report_date DESC，取最近 N 篇
- 新闻按 publish_date DESC，取最近 N 天

**重排序**：用 Cross-encoder 对召回的 chunks 重排序（`BAAI/bge-reranker-v2-m3`）

### Module 3: Agent + Tools（Agent 与工具）

#### 工具清单（LangChain Tool）

| 工具名 | 功能 | 数据源 | 备注 |
|---|---|---|---|
| `query_financials` | 获取营收/利润/资产负债/现金流 | akshare | 按季度/年度 |
| `get_stock_price` | 获取历史股价 + 技术指标 | akshare / yfinance | 支持区间、复权 |
| `calculate_valuation` | 计算 PE/PB/PS/股息率 | akshare | 历史分位数对比 |
| `industry_comparison` | 同行业多公司财务对比 | akshare | 自动找同行业公司 |
| `search_news` | 搜索相关新闻 | DuckDuckGo / RSS | 限定时间范围 |
| `read_financial_report` | RAG 检索导入的财报（时间感知） | Milvus | 支持 period_rank 过滤 |
| `search_research_reports` | 搜索导入的券商研报 | Milvus | 按公司/日期过滤 |
| `calculate_ratios` | 自定义财务指标计算 | 基于 akshare 数据 | ROE/毛利率/净利率等 |
| `write_research_note` | 自动保存分析结果 | 本地文件系统 | Markdown 格式 |

#### Agent 工作流（LangGraph，含完整 UX 增强）

```
[用户输入]
    │
    ▼
[Intent Classifier] 
    ├→ 置信度高 → 直接路由
    ├→ 置信度中 → 反问澄清 → 重新判断
    └→ 多意图 → 拆解为并行子任务
    │
    ▼
[User Interest Matcher]
    查询 SQLite 历史记录 →
    如果用户多次关注相同指标 → 前置展示 + 个性化提示
    如果首次分析 → 无特殊行为
    │
    ▼
[Tool Executor — 流式输出思考过程]
    "正在获取 茅台 最近三期利润表（period_rank=-1,-2,-3）..."
    "正在获取 茅台 近1月股价数据..."
    "正在搜索相关新闻..."
    │
    ▼ (检测到异常 / 复杂分析)
[HITL Checkpoint]  ← 中断，展示中间结论，等待用户选择方向
    │  "发现3个异常指标：①销售费用+30% ②毛利率-3pp ③应收帐款+50%
    │   想深入分析哪个？"
    ▼ 用户反馈
[Synthesizer]
    1. 正文用上标数字标注引用 ¹²³
    2. 末尾集中展示引用列表（来源文件 + 页码）
    3. Streamlit 中关键数据可悬停 Tooltip 看来源
    4. RAG 原文提供可折叠区域，展示前后 2-3 句上下文
    5. 对比类问题强制用表格模板
    6. 数据状态栏（告知缺失/替代的数据）
    │
    ├─ → [更新兴趣画像] 记录本次高频指标
    │
    └─ → [自动保存研究笔记] 写入 data/research_notes/
```

### Module 4: Memory & Persistence（记忆与持久化）

| 存储 | 用途 | 技术 | 用户感知 |
|---|---|---|---|
| 向量库 | RAG 文档（含 period_rank 元数据） | Milvus | 无感 |
| 对话记忆 | 多轮上下文 | LangGraph MemoryStore | "那个公司"能指代 |
| 长期记忆 | 关注标的、分析历史、**关注的指标** | SQLite | 下次优先展示你关心的指标 |
| 研究笔记 | Agent 分析报告存档 | 本地文件系统 | 回顾/分享/对比新旧分析 |

**SQLite 长期记忆结构**：
```sql
-- 关注的公司
CREATE TABLE watched_companies (
    company_code TEXT PRIMARY KEY,
    company_name TEXT,
    first_analyzed DATE,
    last_analyzed DATE,
    analysis_count INTEGER
);

-- 分析历史
CREATE TABLE analysis_history (
    id INTEGER PRIMARY KEY,
    company_code TEXT,
    question TEXT,
    summary TEXT,
    key_metrics_mentioned TEXT, -- JSON array: ["毛利率","销售费用"]
    created_at DATE
);

-- 高频关注指标（自动学习）
CREATE TABLE user_interests (
    metric_name TEXT PRIMARY KEY,
    mention_count INTEGER,
    last_mentioned DATE,
    related_companies TEXT -- JSON array
);
```

---

## 五、项目结构

```
finance_bot/
├── data/                       # 数据存储
│   ├── vector_store/           # 向量存储（Milvus Lite 数据文件）
│   ├── research_notes/         # Agent 自动生成的研究笔记
│   └── knowledge_base/         # 用户导入的文档（PDF/MD）
│       ├── financial_reports/  # 财报
│       └── research_reports/   # 研报
├── src/
│   ├── ingestion/              # 数据导入管线
│   │   ├── pdf_parser.py       # PDF 解析 + 表格提取
│   │   ├── chunker.py          # 文档分块 + period_rank 计算
│   │   ├── pipeline.py         # 完整导入管线编排
│   │   └── report.py           # 导入后的解析摘要生成
│   ├── rag/                    # RAG 引擎
│   │   ├── retriever.py        # 混合检索（语义+BM25+表格+时间感知）
│   │   ├── reranker.py         # 重排序
│   │   └── vector_store.py     # Milvus 封装（MilvusClient）
│   ├── agent/                  # Agent 编排
│   │   ├── graph.py            # LangGraph 图定义
│   │   ├── router.py           # 意图路由（含不确定性检测）
│   │   ├── state.py            # Graph 状态定义
│   │   └── synthesizer.py      # 答案合成（学术引用+表格+状态栏）
│   ├── tools/                  # 工具定义
│   │   ├── financial_data.py   # akshare 封装
│   │   ├── valuation.py        # 估值计算
│   │   ├── news_search.py      # 新闻搜索
│   │   ├── rag_tools.py        # RAG 检索工具（时间感知）
│   │   └── note_tools.py       # 笔记工具
│   ├── memory/                 # 记忆管理
│   │   ├── store.py            # SQLite 长期记忆
│   │   └── interest_tracker.py # 关注指标自动学习
│   ├── models/                 # 数据模型
│   │   └── schemas.py          # Pydantic schema
│   └── config.py               # 配置（模型选择/API key）
├── main.py                     # CLI 入口（交互式问答）
├── web_app.py                  # Web UI（Streamlit，含 Tooltip/可折叠）
└── requirements.txt
```

---

## 六、技术栈

| 组件 | 选型 | 理由 |
|---|---|---|
| Agent 框架 | LangGraph | 状态机编排，支持分支/HITL/并行 |
| 向量库 | Milvus | 混合检索（稠密+稀疏）、全文 BM25、元数据过滤、生产级 |
| 嵌入模型 | BAAI/bge-m3 | 中文效果好，支持多语言 |
| 重排序 | BAAI/bge-reranker-v2-m3 | 中文 reranker |
| BM25 | rank_bm25 + jieba 分词 | 中文关键字检索 |
| 金融数据 | akshare | 免费，覆盖 A股/港股/美股/基金/行业 |
| 美股数据 | yfinance | 补充美股行情 |
| PDF 解析 | Unstructured + Camelot | 表格提取能力 |
| LLM | Claude / GPT-4o | 工具调用能力强 |
| 前端 | Streamlit | 支持 Tooltip、可折叠、流式文本 |

---

## 七、实施步骤

### Phase 1: 基础设施（1-2天）
- [ ] 项目骨架搭建，`config.py` 配置管理
- [ ] Milvus 封装（MilvusClient），完成基础的增删查
- [ ] akshare 数据获取模块，封装 3~5 个核心接口
- [ ] SQLite 长期记忆表结构（watched_companies + analysis_history + user_interests）
- [ ] 验证：`python -c "from src.tools.financial_data import get_financials; print(get_financials('600519'))"` 能跑通

### Phase 2: RAG 管线 + 时间感知（3天）
- [ ] PDF 解析 + 表格提取（处理一份真实财报 PDF）
- [ ] 文档分块策略 + 元数据标记
- [ ] **报告期排序预计算**：导入时自动计算 period_rank，写入 Milvus metadata
- [ ] 混合检索（语义 + BM25）
- [ ] Reranker 集成
- [ ] **时间感知检索**：LLM 提取 `{period_rank: {gte: -3}}` 过滤器
- [ ] 上传 PDF 后的解析摘要生成
- [ ] 验证：导入 3 份不同季度的财报 → 问"最近三期利润表" → 返回正确的 3 个 chunk

### Phase 3: Agent 核心 + 体验增强（4天）
- [ ] LangGraph 状态定义 + 图搭建
- [ ] Intent Router（含不确定性检测 + 反问澄清逻辑）
- [ ] 多意图拆解（"对比财务+看新闻"自动拆成并行任务）
- [ ] 逐个实现 Tools（先做 5 个核心工具）
- [ ] **Synthesizer 学术引用**：正文 ¹² 格式 + 末尾引用列表 + 数据状态栏
- [ ] **HITL Checkpoint**（检测到异常指标时暂停确认）
- [ ] 思考过程流式输出（Streamlit 逐行显示）
- [ ] 验证：`"茅台最近怎么样"` → 反问澄清 → 执行 → 流式显示步骤 → 输出学术引用格式结果

### Phase 4: 记忆 + 兴趣学习（2天）
- [ ] 长期记忆：关注公司记录、分析历史追踪
- [ ] **User Interest Tracker**：从分析历史中学习高频指标
- [ ] **个性化提示**：匹配到关注点时，前置展示 + "你一直关注XX，以下是变化"
- [ ] 分析结束后自动保存研究笔记（结构化 Markdown）
- [ ] 回顾功能："回顾上周对美团的分析"
- [ ] 验证：连续 3 次问不同公司的毛利率 → 第 4 次分析另一家公司时 → 提示"你一直关注毛利率"并前置展示

### Phase 5: 前端完善（2天）
- [ ] Streamlit 对话界面
- [ ] **引用 Tooltip 实现**：关键数据悬停看来源详情
- [ ] **RAG 原文可折叠**："展开阅读原文" 嵌入前后 2-3 句上下文
- [ ] 文档拖拽上传 + 解析摘要展示
- [ ] 历史对话 + 历史研究笔记浏览
- [ ] 一键导出分析报告为 Markdown（保留引用格式）
- [ ] 验证：全流程：上传 PDF → 解析摘要 → 提问 → Agent 流式分析 → 悬停看来源 → 展开原文 → 导出

---

## 八、验证方案

| 验收维度 | 测试问题 | 预期表现 |
|---|---|---|
| 模糊理解 | "茅台最近怎么样？" | 反问"股价/财务/新闻？"而非直接猜 |
| 时间感知 | "最近三期利润表有什么变化" | 按 period_rank 准确取三期，不靠猜季度名 |
| 多任务拆解 | "对比宁王和迪王的财务，顺便看看新闻" | 并行执行对比 + 搜索，综合回复 |
| 过程可见 | "分析海康威视估值" | 流式展示每一步，Streamlit 逐行输出 |
| 中间确认 | 检测到销售费用异常 | 暂停并列出异常项，问是否深入 |
| 学术引用 | "毛利率多少" | 正文 ¹²，末尾集中来源，Streamlit 可悬停 |
| 原文可读 | 回答中引用 RAG 内容 | 关键引用旁有 "展开阅读原文" 可折叠区域 |
| 数据诚实 | akshare 某接口挂了 | 数据状态栏告知缺失 + 用替代数据 |
| 兴趣学习 | 连续问多次毛利率 | 后续分析自动前置毛利率 + 个性化提示 |
| 记忆连续性 | 先分析茅台，再问"那个公司" | 正确识别为茅台 |
| 笔记沉淀 | 完成分析后 | 自动生成研究笔记并存档 |
| 导出可用 | 点击导出 | 完整 Markdown（含时间、来源引用、表格） |
