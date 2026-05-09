'use client'

interface DataStatusBarProps {
  statuses: string[]
}

export function DataStatusBar({ statuses }: DataStatusBarProps) {
  if (!statuses || statuses.length === 0) return null

  return (
    <div className="status-card rounded px-4 py-3 mt-3">
      <div
        className="flex items-center gap-2 text-sm font-medium mb-1"
        style={{ color: 'var(--gold)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
      >
        <span>⚠</span>
        <span>数据状态</span>
      </div>
      {statuses.map((s, i) => (
        <div
          key={i}
          className="text-xs py-0.5"
          style={{ color: 'var(--text-sec)' }}
        >
          • {s}
        </div>
      ))}
    </div>
  )
}
