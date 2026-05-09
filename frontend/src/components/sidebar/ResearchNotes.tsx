'use client'

import { useState, useEffect, useCallback } from 'react'
import type { ResearchNote } from '@/lib/types'
import { Loader2, FileText, X, Search } from 'lucide-react'
import { formatDate, truncate } from '@/lib/utils'
import { api } from '@/lib/api'

interface ResearchNotesProps {
  notes: ResearchNote[]
  isLoading: boolean
  onSelect: (note: ResearchNote) => void
}

export function ResearchNotes({ notes, isLoading, onSelect }: ResearchNotesProps) {
  const [expanded, setExpanded] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ResearchNote[] | null>(null)
  const [isSearching, setIsSearching] = useState(false)

  const handleSearch = useCallback(async (q: string) => {
    setSearchQuery(q)
    if (!q.trim()) {
      setSearchResults(null)
      return
    }
    setIsSearching(true)
    try {
      const res = await api.notes.search(q.trim())
      setSearchResults(res.notes || [])
    } catch {
      setSearchResults([])
    } finally {
      setIsSearching(false)
    }
  }, [])

  const displayNotes = searchResults ?? notes

  return (
    <div className="px-3 py-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full text-xs tracking-wider uppercase font-medium mb-1 transition-colors"
        style={{ color: 'var(--text-muted)', letterSpacing: '0.06em' }}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-sec)' }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
      >
        <span>研究笔记</span>
        <span>{expanded ? '−' : '+'}</span>
      </button>

      {expanded && (
        <>
          {/* 搜索框 */}
          <div className="relative mb-2">
            <Search size={10} className="absolute left-2 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="搜索..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full text-[0.65rem] pl-6 pr-5 py-1 rounded transition-colors"
              style={{
                background: 'var(--card)',
                border: '1px solid var(--border-faint)',
                color: 'var(--text)',
                outline: 'none',
              }}
              onFocus={(e) => e.currentTarget.style.borderColor = 'var(--gold)'}
              onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-faint)'}
            />
            {searchQuery && (
              <button onClick={() => handleSearch('')} className="absolute right-1 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }}>
                <X size={10} />
              </button>
            )}
          </div>

          {isSearching ? (
            <div className="flex items-center gap-2 py-2" style={{ color: 'var(--text-muted)' }}>
              <Loader2 size={12} className="animate-spin" />
              <span className="text-xs">搜索中…</span>
            </div>
          ) : displayNotes.length === 0 ? (
            <div className="text-xs py-2" style={{ color: 'var(--text-muted)' }}>
              {searchQuery ? '无匹配结果' : '暂无笔记'}
            </div>
          ) : (
            <div className="space-y-0.5 max-h-48 overflow-y-auto">
              {displayNotes.slice(0, 15).map((note) => (
                <button
                  key={note.id || note.path}
                  onClick={() => onSelect(note)}
                  className="w-full text-left px-2 py-1.5 text-xs transition-colors rounded flex items-center gap-2"
                  style={{ color: 'var(--text-sec)' }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--card-hover)'
                    e.currentTarget.style.color = 'var(--gold)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'var(--text-sec)'
                  }}
                >
                  <FileText size={10} className="flex-shrink-0 opacity-50" />
                  <span className="truncate flex-1">{note.company_name || note.company || note.code}</span>
                  <span className="opacity-40 flex-shrink-0">{formatDate(note.created || note.updated_at || '')}</span>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
