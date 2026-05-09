'use client'

import { useState } from 'react'
import { Bookmark, Check, Loader2 } from 'lucide-react'
import type { SavePrompt } from '@/lib/types'
import { api } from '@/lib/api'

interface SaveNoteButtonProps {
  prompt: SavePrompt
}

export function SaveNoteButton({ prompt }: SaveNoteButtonProps) {
  const [state, setState] = useState<'idle' | 'saving' | 'saved'>('idle')

  const handleSave = async () => {
    if (state !== 'idle') return
    setState('saving')
    try {
      await api.notes.save({
        company_code: prompt.company_code,
        company_name: prompt.company_name,
        title: prompt.title,
        content: prompt.content,
        metrics: prompt.metrics,
        tags: prompt.tags,
      })
      setState('saved')
    } catch {
      setState('idle')
    }
  }

  return (
    <div className="mt-3 pt-2" style={{ borderTop: '1px solid var(--border-faint)' }}>
      <button
        onClick={handleSave}
        disabled={state === 'saving' || state === 'saved'}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-all duration-200"
        style={{
          color: state === 'saved' ? 'var(--jade)' : 'var(--text-sec)',
          background: state === 'saved' ? 'var(--jade-bg)' : 'var(--card)',
          border: '1px solid',
          borderColor: state === 'saved' ? 'var(--jade)' : 'var(--border-faint)',
          fontFamily: 'Georgia, "Noto Serif SC", serif',
          cursor: state === 'saving' ? 'wait' : 'pointer',
          opacity: state === 'saved' ? 0.8 : 1,
        }}
        onMouseEnter={(e) => {
          if (state === 'idle') {
            e.currentTarget.style.borderColor = 'var(--gold)'
            e.currentTarget.style.color = 'var(--gold)'
          }
        }}
        onMouseLeave={(e) => {
          if (state === 'idle') {
            e.currentTarget.style.borderColor = 'var(--border-faint)'
            e.currentTarget.style.color = 'var(--text-sec)'
          }
        }}
      >
        {state === 'saving' ? (
          <Loader2 size={12} className="animate-spin" />
        ) : state === 'saved' ? (
          <Check size={12} />
        ) : (
          <Bookmark size={12} />
        )}
        <span>
          {state === 'idle' && '保存分析笔记'}
          {state === 'saving' && '保存中...'}
          {state === 'saved' && '已保存'}
        </span>
      </button>
    </div>
  )
}
