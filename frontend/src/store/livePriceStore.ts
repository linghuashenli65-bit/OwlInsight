/* 实时股价 Store — 单例 WebSocket，跨页面共享 */

import { create } from 'zustand'

const WS_URL = (process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8897') + '/ws/prices'

interface LivePrice {
  price: number
  change_pct: number
}

interface LivePriceState {
  livePrices: Record<string, LivePrice>
}

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let retryCount = 0

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return

  try {
    ws = new WebSocket(WS_URL)
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'snapshot' || msg.type === 'update') {
          const updates: Record<string, LivePrice> = {}
          const items = Array.isArray(msg.data) ? msg.data : []
          for (const item of items) {
            if (item.code && item.price != null) {
              updates[item.code] = { price: item.price, change_pct: item.change_pct ?? 0 }
            }
          }
          if (Object.keys(updates).length > 0) {
            useLivePriceStore.setState((s) => ({ livePrices: { ...s.livePrices, ...updates } }))
          }
        }
      } catch { /* ignore */ }
      retryCount = 0
    }
    ws.onopen = () => { retryCount = 0 }
    ws.onclose = () => {
      ws = null
      const delay = Math.min(5000 * Math.pow(1.5, retryCount), 30000)
      retryCount++
      reconnectTimer = setTimeout(connect, delay)
    }
    ws.onerror = () => ws?.close()
  } catch {
    ws = null
    const delay = Math.min(5000 * Math.pow(1.5, retryCount), 30000)
    retryCount++
    reconnectTimer = setTimeout(connect, delay)
  }
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (ws) {
    ws.onclose = null  // 阻止触发重连
    ws.close()
    ws = null
  }
}

export const useLivePriceStore = create<LivePriceState>(() => ({
  livePrices: {},
}))

// 启动连接（应用初始化时调用一次）
export function initLivePrices() {
  connect()
}

// 关闭连接（应用销毁时调用）
export function stopLivePrices() {
  disconnect()
}
