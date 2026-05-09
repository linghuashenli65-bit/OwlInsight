'use client'

import { useEffect, useState } from 'react'
import { X, CheckCheck, AlertTriangle, Info, ArrowDown, ArrowUp, Bell } from 'lucide-react'
import { useAlertStore } from '@/store/alertStore'
import { formatDate } from '@/lib/utils'
import type { AlertEvent } from '@/lib/types'

const SEVERITY_CONFIG: Record<string, { color: string; icon: React.ReactNode }> = {
  danger: { color: 'var(--vermillion)', icon: <ArrowDown size={12} /> },
  warning: { color: 'var(--gold)', icon: <AlertTriangle size={12} /> },
  info: { color: 'var(--text-muted)', icon: <Info size={12} /> },
}

export function AlertPanel() {
  const alerts = useAlertStore((s) => s.alerts)
  const panelOpen = useAlertStore((s) => s.panelOpen)
  const setPanelOpen = useAlertStore((s) => s.setPanelOpen)
  const fetchAlerts = useAlertStore((s) => s.fetchAlerts)
  const markRead = useAlertStore((s) => s.markRead)
  const connectSSE = useAlertStore((s) => s.connectSSE)
  const disconnectSSE = useAlertStore((s) => s.disconnectSSE)
  const isConnected = useAlertStore((s) => s.isConnected)

  useEffect(() => {
    fetchAlerts()
    connectSSE()
    return () => disconnectSSE()
  }, [])

  if (!panelOpen) return null

  const unreadAlerts = alerts.filter((a) => !a.is_read)

  return (
    <>
      {/* 遮罩 */}
      <div
        className="fixed inset-0 z-50"
        onClick={() => setPanelOpen(false)}
      />

      {/* 面板 */}
      <div
        className="fixed top-12 right-4 z-50 w-[420px] max-h-[85vh] flex flex-col rounded shadow-xl"
        style={{
          background: 'var(--bg-alt)',
          border: '1px solid var(--border-faint)',
          maxWidth: 'calc(100vw - 80px)',
        }}
      >
        {/* 头部 */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: '1px solid var(--border-faint)' }}
        >
          <div className="flex items-center gap-2">
            <span
              className="text-xs font-medium"
              style={{ color: 'var(--text)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
            >
              告警通知
            </span>
            <span
              className="text-[0.6rem] px-1.5 py-0.5 rounded-full"
              style={{
                background: isConnected ? 'rgba(39,174,96,0.15)' : 'rgba(231,76,60,0.15)',
                color: isConnected ? 'var(--green)' : 'var(--vermillion)',
              }}
            >
              {isConnected ? '实时' : '离线'}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {unreadAlerts.length > 0 && (
              <button
                onClick={() => markRead()}
                className="flex items-center gap-1 px-2 py-1 text-[0.65rem] transition-colors rounded"
                style={{ color: 'var(--text-muted)' }}
                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)' }}
                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
              >
                <CheckCheck size={12} />
                全部已读
              </button>
            )}
            <button
              onClick={() => setPanelOpen(false)}
              className="p-1 transition-colors rounded"
              style={{ color: 'var(--text-muted)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* 列表 */}
        <div className="flex-1 overflow-y-auto">
          {alerts.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center py-12 text-xs"
              style={{ color: 'var(--text-muted)' }}
            >
              <Bell className="mb-2" size={20} />
              <span>暂无告警</span>
            </div>
          ) : (
            alerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onMarkRead={() => markRead(alert.is_read ? undefined : alert.id)}
              />
            ))
          )}
        </div>

        {/* 底部 */}
        <div
          className="px-4 py-2 text-[0.6rem] text-center"
          style={{ color: 'var(--text-muted)', borderTop: '1px solid var(--border-faint)' }}
        >
          共 {alerts.length} 条告警，{unreadAlerts.length} 条未读
        </div>
      </div>
    </>
  )
}

// ────────── 单条告警卡片 ──────────

function AlertCard({ alert, onMarkRead }: { alert: AlertEvent; onMarkRead: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const sev = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.info
  const isUnread = !alert.is_read

  const handleClick = () => {
    if (isUnread) onMarkRead()
    setExpanded(!expanded)
  }

  return (
    <div
      className="px-4 py-3 transition-colors cursor-pointer"
      style={{
        background: isUnread ? 'var(--card-hover)' : 'transparent',
        borderBottom: '1px solid var(--border-faint)',
      }}
      onClick={handleClick}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0" style={{ color: sev.color }}>
          {sev.icon}
        </span>
        <div className="flex-1 min-w-0">
          <div
            className="text-xs font-medium truncate"
            style={{ color: isUnread ? 'var(--text)' : 'var(--text-sec)' }}
          >
            {alert.title}
          </div>
          {/* 未展开时最多显示 2 行 */}
          {!expanded && (
            <div
              className="text-[0.65rem] mt-0.5 line-clamp-2"
              style={{ color: 'var(--text-muted)' }}
            >
              {alert.message}
            </div>
          )}
          {/* 展开后显示完整信息 */}
          {expanded && (
            <div className="mt-1 space-y-1">
              <div
                className="text-[0.65rem] whitespace-pre-wrap break-words"
                style={{ color: 'var(--text-sec)' }}
              >
                {alert.message}
              </div>
              {alert.data && Object.keys(alert.data).length > 0 && (
                <div
                  className="text-[0.6rem] p-2 rounded space-y-0.5"
                  style={{ background: 'var(--bg)', color: 'var(--text-muted)' }}
                >
                  {Object.entries(alert.data).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span>{k}:</span>
                      <span className="font-mono">{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="flex items-center gap-2 mt-1">
            {alert.company_name && (
              <span
                className="text-[0.55rem] px-1 py-0.5 rounded"
                style={{
                  background: 'var(--card-hover)',
                  color: 'var(--text-muted)',
                }}
              >
                {alert.company_name}
              </span>
            )}
            <span className="text-[0.55rem]" style={{ color: 'var(--text-muted)' }}>
              {formatDate(alert.created_at)}
            </span>
          </div>
        </div>
        {isUnread && (
          <span
            className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
            style={{ background: sev.color }}
          />
        )}
      </div>
    </div>
  )
}
