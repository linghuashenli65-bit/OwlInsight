/* ──────────── 核心类型定义 ──────────── */

export interface Citation {
  index: number
  source: string
  detail: string
}

export interface Anomaly {
  metric: string
  value: string
  change: string
  description: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  reasoning?: string[]
  citations?: Citation[]
  anomalies?: Anomaly[]
  dataStatus?: string[]
  chartData?: ChartData
  savePrompt?: SavePrompt
  timestamp?: string
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  created_at: string
  updated_at: string
  isLoading?: boolean
}

export interface WatchedCompany {
  company_code: string
  company_name: string
  analysis_count: number
}

export interface ChartData {
  type: 'line' | 'candlestick'
  data: Array<{
    symbol: string
    date: string
    open: number | null
    close: number | null
    high: number | null
    low: number | null
    volume: number
    amount: number | null
    change_pct: number | null
  }>
}

export interface ResearchNote {
  path: string
  company: string
  code: string
  created: string
  filename?: string
  content?: string
  // SQLite note fields
  id?: number
  company_code?: string
  company_name?: string
  title?: string
  preview?: string
  metrics?: string[]
  tags?: string[]
  created_at?: string
  updated_at?: string
}

export interface ConversationSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface StepEvent {
  step: string
  detail: string
}

export interface IngestionResult {
  success: boolean
  doc_name?: string
  total_pages?: number
  total_chunks?: number
  total_tables?: number
  company?: string
  company_code?: string
  errors?: string[]
  elapsed_seconds?: number
}

/* ──────────── SSE 事件类型 ──────────── */

export interface SavePrompt {
  company_code: string
  company_name: string
  title: string
  content: string
  metrics: string[]
  tags: string[]
}

export type SSEEvent =
  | { event: 'step';      data: StepEvent }
  | { event: 'token';     data: { content: string } }
  | { event: 'citation';  data: Citation }
  | { event: 'anomaly';   data: Anomaly }
  | { event: 'status';    data: { message: string } }
  | { event: 'chart';     data: ChartData }
  | { event: 'save_prompt'; data: SavePrompt }
  | { event: 'done';      data: { message_id: string } }
  | { event: 'error';     data: { error: string } };

/* ──────────── Store 类型 ──────────── */

export interface ChatState {
  conversations: Conversation[]
  currentConversationId: string | null
  isLoading: boolean

  // 流式累积
  streamingContent: string
  streamingReasoning: string[]
  streamingCitations: Citation[]
  streamingAnomalies: Anomaly[]
  streamingStatus: string[]
  streamingChartData: ChartData | null
  pendingSavePrompt: SavePrompt | null

  // 对话历史列表（侧边栏）
  conversationList: ConversationSummary[]
  isFetchingList: boolean

  // Actions
  sendMessage: (content: string) => Promise<void>
  stopGeneration: () => void
  createNewConversation: () => void
  setCurrentConversation: (id: string) => void
  deleteConversation: (id: string) => Promise<void>
  renameConversation: (id: string, title: string) => void
  exportToMarkdown: (conversationId: string) => string
  fetchConversationList: () => Promise<void>
  switchConversation: (id: string) => Promise<void>
}

export interface SidebarState {
  watchedCompanies: WatchedCompany[]
  researchNotes: ResearchNote[]
  isLoading: boolean
  fetchCompanies: () => Promise<void>
  fetchNotes: () => Promise<void>
}

export type ThemeMode = 'dark' | 'light'

export type AppView = 'dashboard' | 'chat' | 'settings' | 'companies' | 'notes' | 'documents'

export interface AppSettings {
  theme: string
  language: string
  llm_provider: string
  llm_model: string
  temperature: number
}

export interface CompanyHistory {
  company_code: string
  company_name: string
  last_analysis: string | null
  analysis_count: number
  notes_count: number
}

/* ──────────── 告警系统类型 ──────────── */

export interface AlertEvent {
  id: number
  company_code: string
  company_name: string
  event_type: string
  title: string
  message: string
  severity: 'info' | 'warning' | 'danger'
  data: Record<string, unknown>
  is_read: number
  created_at: string
}

export interface AlertConfig {
  company_code: string
  company_name?: string
  price_up_pct: number
  price_down_pct: number
  fund_flow_threshold: number
  news_enabled: number
  intraday_enabled: number
}

export interface SettingsState {
  theme: ThemeMode
  toggleTheme: () => void
  setTheme: (t: ThemeMode) => void
  hydrate: () => void
}
