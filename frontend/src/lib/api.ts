/* API 封装层 — 所有后端接口 */

import type { WatchedCompany, ResearchNote, IngestionResult, ChatMessage, CompanyHistory, ConversationSummary } from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8897'

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${res.statusText}${body ? ` — ${body.slice(0, 100)}` : ''}`)
  }
  return res.json()
}

export const api = {
  health: () => fetchJson<{ status: string }>('/api/health'),

  settings: {
    get: (): Promise<Record<string, string | number>> =>
      fetchJson('/api/settings'),
    save: (data: Record<string, string | number>): Promise<{ status: string }> =>
      fetchJson('/api/settings', { method: 'POST', body: JSON.stringify(data) }),
  },

  companies: {
    list: (): Promise<{ companies: WatchedCompany[] }> =>
      fetchJson('/api/data/companies'),
    detail: (code: string): Promise<CompanyHistory> =>
      fetchJson(`/api/data/companies/${encodeURIComponent(code)}`),
    delete: (code: string): Promise<{ status: string }> =>
      fetchJson(`/api/data/companies/${encodeURIComponent(code)}`, { method: 'DELETE' }),
  },

  chat: {
    /** SSE 流式对话 */
    stream(
      message: string,
      threadId: string,
      history: Pick<ChatMessage, 'role' | 'content'>[],
    ): EventSource {
      const url = new URL(`${BASE_URL}/api/chat/stream`)
      throw new Error('Use streamChat service instead')
    },
  },

  notes: {
    list: (): Promise<{ notes: ResearchNote[] }> =>
      fetchJson('/api/data/notes'),
    get: (path: string): Promise<{ content: string } & { error?: string }> =>
      fetchJson(`/api/data/notes/${encodeURIComponent(path)}`),
    getById: (id: number): Promise<{ content: string } & { error?: string }> =>
      fetchJson(`/api/data/notes/detail/${id}`),
    search: (q: string): Promise<{ notes: ResearchNote[] }> =>
      fetchJson(`/api/data/notes/search?q=${encodeURIComponent(q)}`),
    save: (data: {
      company_code: string
      company_name?: string
      title?: string
      content: string
      metrics?: string[]
      tags?: string[]
    }): Promise<{ status: string; note_id: number }> =>
      fetchJson('/api/data/notes/save', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    delete: (noteId: number): Promise<{ status: string }> =>
      fetchJson(`/api/data/notes/${noteId}`, { method: 'DELETE' }),
  },

  conversations: {
    list: (): Promise<{ conversations: ConversationSummary[] }> =>
      fetchJson('/api/chat/conversations'),
    get: (id: string): Promise<{ conversation: ConversationSummary; messages: any[] }> =>
      fetchJson(`/api/chat/conversations/${encodeURIComponent(id)}`),
    create: (title = '新对话'): Promise<{ conversation: any }> =>
      fetchJson('/api/chat/conversations', {
        method: 'POST',
        body: JSON.stringify({ title }),
      }),
    update: (id: string, title: string): Promise<{ status: string }> =>
      fetchJson(`/api/chat/conversations/${encodeURIComponent(id)}`, {
        method: 'PUT',
        body: JSON.stringify({ title }),
      }),
    delete: (id: string): Promise<{ status: string }> =>
      fetchJson(`/api/chat/conversations/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      }),
    addMessage: (id: string, msg: {
      role: string
      content: string
      reasoning?: string[]
      citations?: any[]
      anomalies?: any[]
      chart_data?: string | null
    }): Promise<{ message_id: number }> =>
      fetchJson(`/api/chat/conversations/${encodeURIComponent(id)}/messages`, {
        method: 'POST',
        body: JSON.stringify(msg),
      }),
    generateTitle: (id: string): Promise<{ title: string }> =>
      fetchJson(`/api/chat/conversations/${encodeURIComponent(id)}/generate-title`, {
        method: 'POST',
      }),
  },

  ingest: {
    list: (): Promise<{ documents: Array<{ doc_name: string; company: string; company_code: string; doc_type: string; chunk_count: number }> }> =>
      fetchJson('/api/ingest/documents'),
    pdf: async (file: File): Promise<IngestionResult> => {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${BASE_URL}/api/ingest/pdf`, { method: 'POST', body: form })
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
      return res.json()
    },
    delete: (docName: string): Promise<{ status: string }> =>
      fetchJson(`/api/ingest/documents?doc_name=${encodeURIComponent(docName)}`, { method: 'DELETE' }),
  },

  alerts: {
    getConfig: (): Promise<{ configs: any[]; preferences: Record<string, string> }> =>
      fetchJson('/api/alerter/config'),
    saveConfig: (configs: any[]): Promise<{ status: string }> =>
      fetchJson('/api/alerter/config', { method: 'PUT', body: JSON.stringify({ configs }) }),
    getPreferences: (): Promise<{ preferences: Record<string, string> }> =>
      fetchJson('/api/alerter/preferences'),
    savePreferences: (preferences: Record<string, string>): Promise<{ status: string }> =>
      fetchJson('/api/alerter/preferences', { method: 'PUT', body: JSON.stringify({ preferences }) }),
    getEvents: (unreadOnly = false): Promise<{ events: any[]; unread_count: number }> =>
      fetchJson(`/api/alerter/events?unread_only=${unreadOnly}`),
    triggerJob: (jobName: string): Promise<{ status: string; message: string }> =>
      fetchJson(`/api/alerter/trigger/${jobName}`, { method: 'POST' }),
    markRead: (alertId?: number): Promise<{ status: string; unread_count: number }> => {
      const url = alertId ? `/api/alerter/events/read?alert_id=${alertId}` : '/api/alerter/events/read'
      return fetchJson(url, { method: 'PUT' })
    },
  },

  stock: {
    kline: (code: string, period = 'daily'): Promise<{ code: string; period: string; data: Array<{ date: string; open: number | null; close: number | null; high: number | null; low: number | null; volume: number }> }> =>
      fetchJson(`/api/data/stock/${encodeURIComponent(code)}/kline?period=${period}`),
    minuteKline: (code: string, interval = 5): Promise<{ code: string; interval: number; data: Array<{ date: string; open: number | null; close: number | null; high: number | null; low: number | null; volume: number }> }> =>
      fetchJson(`/api/data/stock/${encodeURIComponent(code)}/minute-kline?interval=${interval}`),
    intraday: (code: string): Promise<{ code: string; data: Array<{ time: string; price: number | null; volume: number; change_pct: number | null }> }> =>
      fetchJson(`/api/data/stock/${encodeURIComponent(code)}/intraday`),
    fundFlow: (code: string): Promise<{ code: string; data: Array<{ date: string; main_net: number | null; main_pct: number | null; super_large_net: number | null; large_net: number | null; medium_net: number | null; small_net: number | null }> }> =>
      fetchJson(`/api/data/stock/${encodeURIComponent(code)}/fund-flow`),
    institution: (code: string): Promise<{ code: string; data: Array<{ name: string; hold_shares: number | null; hold_value: number | null; hold_pct: number | null }> }> =>
      fetchJson(`/api/data/stock/${encodeURIComponent(code)}/institution`),
    refresh: (): Promise<{ prices: Record<string, { price: number | null; change_pct: number | null; open: number | null; high: number | null; low: number | null }> }> =>
      fetchJson('/api/data/companies/refresh'),
  },
}
