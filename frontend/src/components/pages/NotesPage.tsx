'use client'

import { useEffect, useState, useCallback } from 'react'
import { FileText, ExternalLink, Search, X, Trash2 } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { useSidebarStore } from '@/store/sidebarStore'
import { api } from '@/lib/api'
import type { ResearchNote } from '@/lib/types'

interface GroupedNotes {
  [company: string]: ResearchNote[]
}

export function NotesPage() {
  const researchNotes = useSidebarStore((s) => s.researchNotes)
  const isLoading = useSidebarStore((s) => s.isLoading)
  const fetchNotes = useSidebarStore((s) => s.fetchNotes)
  const [previewNote, setPreviewNote] = useState<{
    filename: string
    content: string
  } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ResearchNote[] | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  useEffect(() => {
    fetchNotes()
  }, [])

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

  const handlePreview = async (note: ResearchNote) => {
    try {
      const detail = await api.notes.get(note.path)
      setPreviewNote({
        filename: note.filename || note.path.split('/').pop() || '笔记',
        content: detail.content || '',
      })
    } catch {
      setPreviewNote({
        filename: note.filename || '笔记',
        content: '无法加载笔记内容',
      })
    }
  }

  const handleDeleteNote = async (noteId: number) => {
    if (deletingId === noteId) {
      try {
        await api.notes.delete(noteId)
        fetchNotes()
      } catch { /* ignore */ }
      setDeletingId(null)
    } else {
      setDeletingId(noteId)
      setTimeout(() => setDeletingId(null), 2000)
    }
  }

  // 按公司分组
  const displayNotes = searchResults ?? researchNotes
  const grouped: GroupedNotes = {}
  displayNotes.forEach((note) => {
    const key = note.company_name || note.company || '未分类'
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(note)
  })

  const groupHeaderStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: 'var(--text-sec)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    paddingBottom: '8px',
    borderBottom: '1px solid var(--border-faint)',
    marginBottom: '8px',
    fontFamily: 'Georgia, "Noto Serif SC", serif',
  }

  const highlightText = (text: string, keyword: string) => {
    if (!keyword.trim()) return text
    const parts = text.split(new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))
    return parts.map((part, i) =>
      part.toLowerCase() === keyword.toLowerCase()
        ? <span key={i} style={{ color: 'var(--gold)', fontWeight: 600 }}>{part}</span>
        : part
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <PageHeader title="研究笔记" description="所有分析报告与研究记录" />

      {/* 搜索框 */}
      <div className="relative max-w-md mb-6">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: 'var(--text-muted)' }}
        />
        <input
          type="text"
          placeholder="搜索笔记..."
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          className="w-full text-sm pl-9 pr-8 py-2 rounded transition-colors"
          style={{
            background: 'var(--card)',
            border: '1px solid var(--border-faint)',
            color: 'var(--text)',
            fontFamily: 'Georgia, "Noto Serif SC", serif',
            outline: 'none',
          }}
          onFocus={(e) => e.currentTarget.style.borderColor = 'var(--gold)'}
          onBlur={(e) => e.currentTarget.style.borderColor = 'var(--border-faint)'}
        />
        {searchQuery && (
          <button
            onClick={() => handleSearch('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1"
            style={{ color: 'var(--text-muted)' }}
          >
            <X size={14} />
          </button>
        )}
      </div>

      {isSearching ? (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>搜索中...</p>
      ) : isLoading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>加载中...</p>
      ) : displayNotes.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center py-16"
          style={{ color: 'var(--text-muted)' }}
        >
          <FileText size={40} className="mb-3" style={{ opacity: 0.3 }} />
          <p style={{ fontSize: '0.85rem', fontFamily: 'Georgia, "Noto Serif SC", serif' }}>
            {searchQuery ? '未找到匹配的笔记' : '还没有研究笔记'}
          </p>
          <p style={{ fontSize: '0.7rem', marginTop: '4px' }}>
            {searchQuery ? '试试其他关键词' : '完成分析后笔记会自动生成'}
          </p>
        </div>
      ) : (
        <div className="space-y-6 max-w-2xl">
          {searchQuery && searchResults && (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              找到 {searchResults.length} 条结果
            </p>
          )}
          {Object.entries(grouped).map(([company, notes]) => (
            <div key={company}>
              <div style={groupHeaderStyle}>{company}</div>
              <div className="space-y-1">
                {notes.map((note, idx) => (
                  <div
                    key={note.id || note.path + idx}
                    className="group flex items-center gap-1 rounded transition-colors"
                    style={{
                      background: 'transparent',
                    }}
                  >
                    <button
                      onClick={() => handlePreview(note)}
                      className="flex-1 flex items-center gap-3 px-3 py-2 text-left rounded transition-colors"
                      style={{ color: 'var(--text-sec)' }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'var(--card-hover)'
                        e.currentTarget.style.color = 'var(--text)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent'
                        e.currentTarget.style.color = 'var(--text-sec)'
                      }}
                    >
                      <FileText size={14} style={{ flexShrink: 0, color: 'var(--gold)' }} />
                      <div className="flex-1 min-w-0">
                        <div
                          className="truncate"
                          style={{
                            fontSize: '0.8rem',
                            fontFamily: 'Georgia, "Noto Serif SC", serif',
                          }}
                        >
                          {searchQuery ? highlightText(note.company_name || note.company || '', searchQuery) : (note.filename || note.path?.split('/').pop())}
                        </div>
                        {note.preview && (
                          <div
                            className="truncate mt-0.5 text-[0.65rem]"
                            style={{ color: 'var(--text-muted)' }}
                          >
                            {searchQuery ? highlightText(note.preview, searchQuery) : note.preview}
                          </div>
                        )}
                      </div>
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', flexShrink: 0 }}>
                        {note.created?.split('T')[0] || note.updated_at?.split('T')[0] || ''}
                      </span>
                      <ExternalLink size={12} style={{ flexShrink: 0, opacity: 0.4 }} />
                    </button>
                    {note.id != null && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteNote(note.id!) }}
                        className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity rounded"
                        style={{
                          color: deletingId === note.id ? 'var(--vermillion)' : 'var(--text-muted)',
                        }}
                        title={deletingId === note.id ? '确认删除' : '删除笔记'}
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 预览弹窗 */}
      {previewNote && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.5)' }}
          onClick={() => setPreviewNote(null)}
        >
          <div
            className="max-w-2xl max-h-[80vh] w-[90vw] overflow-y-auto p-6 rounded"
            style={{
              background: 'var(--card)',
              border: '1px solid var(--border-faint)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2
                style={{
                  fontSize: '0.9rem',
                  fontWeight: 500,
                  color: 'var(--text)',
                  fontFamily: 'Georgia, "Noto Serif SC", serif',
                }}
              >
                {previewNote.filename}
              </h2>
              <button
                onClick={() => setPreviewNote(null)}
                style={{ color: 'var(--text-muted)', fontSize: '1.2rem', cursor: 'pointer' }}
              >
                &times;
              </button>
            </div>
            <pre
              style={{
                fontSize: '0.75rem',
                lineHeight: 1.8,
                color: 'var(--text)',
                whiteSpace: 'pre-wrap',
                fontFamily: 'Georgia, "Noto Serif SC", serif',
              }}
            >
              {previewNote.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
