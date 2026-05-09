'use client'

import { Bell } from 'lucide-react'
import { useAlertStore } from '@/store/alertStore'

export function AlertBell() {
  const unreadCount = useAlertStore((s) => s.unreadCount)
  const isConnected = useAlertStore((s) => s.isConnected)
  const togglePanel = useAlertStore((s) => s.togglePanel)

  return (
    <button
      onClick={togglePanel}
      className="relative p-1.5 transition-colors rounded"
      style={{ color: 'var(--text-muted)' }}
      onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)' }}
      onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
      title={isConnected ? '告警已连接' : '告警未连接'}
    >
      <Bell size={16} />
      {unreadCount > 0 && (
        <span
          className="absolute -top-0.5 -right-0.5 flex items-center justify-center rounded-full text-[0.55rem] font-bold min-w-[14px] h-[14px] px-0.5"
          style={{
            background: unreadCount > 0 ? 'var(--vermillion)' : 'var(--gold)',
            color: '#fff',
          }}
        >
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  )
}
