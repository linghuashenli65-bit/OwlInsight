'use client'

import type { Anomaly } from '@/lib/types'

interface AnomalyCardProps {
  anomalies: Anomaly[]
  onAnalyze?: (metric: string) => void
}

export function AnomalyCard({ anomalies, onAnalyze }: AnomalyCardProps) {
  if (!anomalies || anomalies.length === 0) return null

  return (
    <div className="anomaly-card rounded px-4 py-3 mt-3">
      <div
        className="flex items-center gap-2 text-sm font-medium mb-2"
        style={{ color: 'var(--brand)' }}
      >
        <span>◆</span>
        <span>发现异常指标</span>
      </div>

      {anomalies.map((a, i) => (
        <div
          key={i}
          className="flex items-center justify-between py-1.5 text-sm"
          style={{ color: 'var(--text-sec)' }}
        >
          <span>
            <b>{a.metric}</b>: {a.value}（{a.change}）— {a.description}
          </span>
          {onAnalyze && (
            <button
              onClick={() => onAnalyze(a.metric)}
              className="text-xs px-2 py-0.5 transition-colors ml-2"
              style={{
                color: 'var(--brand)',
                border: '1px solid var(--brand)',
                borderRadius: '2px',
                background: 'transparent',
                fontFamily: 'Georgia, "Noto Serif SC", serif',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--vermillion-bg)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
            >
              分析
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
