/* 告警状态管理 — SSE 实时推送 + 事件列表 */

import { create } from 'zustand'
import { api } from '@/lib/api'
import type { AlertEvent } from '@/lib/types'

interface AlertState {
  alerts: AlertEvent[]
  unreadCount: number
  isConnected: boolean
  eventSource: EventSource | null
  panelOpen: boolean

  /** 从后端加载告警列表 */
  fetchAlerts: () => Promise<void>

  /** 标记已读 */
  markRead: (alertId?: number) => Promise<void>

  /** 切换面板 */
  togglePanel: () => void
  setPanelOpen: (open: boolean) => void

  /** SSE 连接管理 */
  connectSSE: () => void
  disconnectSSE: () => void
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  unreadCount: 0,
  isConnected: false,
  eventSource: null,
  panelOpen: false,

  fetchAlerts: async () => {
    try {
      const res = await api.alerts.getEvents()
      set({ alerts: res.events || [], unreadCount: res.unread_count || 0 })
    } catch {
      // 静默
    }
  },

  markRead: async (alertId?: number) => {
    try {
      const res = await api.alerts.markRead(alertId)
      set({ unreadCount: res.unread_count ?? 0 })
      if (alertId) {
        set((s) => ({
          alerts: s.alerts.map((a) =>
            a.id === alertId ? { ...a, is_read: 1 } : a,
          ),
        }))
      } else {
        set((s) => ({
          alerts: s.alerts.map((a) => ({ ...a, is_read: 1 })),
        }))
      }
    } catch { /* ok */ }
  },

  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  setPanelOpen: (open) => set({ panelOpen: open }),

  connectSSE: () => {
    const existing = get().eventSource
    if (existing) existing.close()

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8897'
    const es = new EventSource(`${baseUrl}/api/alerter/events/stream`)

    es.onopen = () => set({ isConnected: true })

    es.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as AlertEvent
        set((s) => ({
          alerts: [event, ...s.alerts],
          unreadCount: s.unreadCount + 1,
          panelOpen: true, // 新告警自动弹出面板
        }))
      } catch { /* ignore malformed */ }
    }

    es.onerror = () => {
      set({ isConnected: false })
      // 自动重连（EventSource 自带）
    }

    set({ eventSource: es })
  },

  disconnectSSE: () => {
    const es = get().eventSource
    if (es) {
      es.close()
      set({ eventSource: null, isConnected: false })
    }
  },
}))
