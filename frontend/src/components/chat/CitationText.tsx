'use client'

import type { Citation } from '@/lib/types'

interface CitationTextProps {
  text: string
  citations: Citation[]
}

/**
 * 将正文中的 [N] 标记渲染为上标引用，并展示引用列表。
 */
export function CitationText({ text, citations }: CitationTextProps) {
  if (!citations || citations.length === 0) {
    return <span>{text}</span>
  }

  // 把 [N] 替换为带 tooltip 的上标
  const parts: React.ReactNode[] = []
  let remaining = text
  let key = 0

  while (remaining.length > 0) {
    const match = remaining.match(/\[(\d+)\]/)
    if (!match) {
      parts.push(<span key={key++}>{remaining}</span>)
      break
    }

    const idx = match.index!
    const num = parseInt(match[1], 10)
    const citation = citations.find((c) => c.index === num)

    // 匹配前文本
    if (idx > 0) {
      parts.push(<span key={key++}>{remaining.slice(0, idx)}</span>)
    }

    parts.push(
      <span
        key={key++}
        className="citation-sup group inline-flex items-center"
      >
        [{num}]
        <span
          className="invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-all duration-200 absolute bottom-full left-1/2 -translate-x-1/2 px-3 py-1.5 text-xs whitespace-nowrap z-50 pointer-events-none"
          style={{
            background: 'var(--card)',
            color: 'var(--text)',
            border: '1px solid var(--border)',
            borderRadius: '2px',
            boxShadow: '0 4px 16px var(--shadow)',
            fontFamily: 'Georgia, "Noto Serif SC", serif',
            fontWeight: 400,
          }}
        >
          {citation?.detail || match[1]}
        </span>
      </span>,
    )

    remaining = remaining.slice(idx + match[0].length)
  }

  return <>{parts}</>
}

/** 引用列表（放在消息末尾） */
export function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations || citations.length === 0) return null

  return (
    <div className="refs-card rounded px-4 py-3 mt-3 text-xs">
      <div
        className="text-xs tracking-wider uppercase mb-2"
        style={{ color: 'var(--text-muted)', letterSpacing: '0.06em' }}
      >
        引用来源
      </div>
      {citations.map((c) => (
        <div
          key={c.index}
          className="py-0.5"
          style={{ color: 'var(--text-sec)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
        >
          <span style={{ color: 'var(--brand)' }}>[{c.index}]</span>
          &ensp;{c.detail}
        </div>
      ))}
    </div>
  )
}
