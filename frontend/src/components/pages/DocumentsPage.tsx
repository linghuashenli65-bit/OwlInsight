'use client'

import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FileText, BookOpen, RefreshCw, Trash2, ExternalLink } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { api } from '@/lib/api'

interface DocInfo {
  doc_name: string
  company: string
  company_code: string
  doc_type: string
  chunk_count: number
}

export function DocumentsPage() {
  const [documents, setDocuments] = useState<DocInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [previewDoc, setPreviewDoc] = useState<{
    doc_name: string
    content: string
    loading: boolean
  } | null>(null)

  const fetchDocuments = async () => {
    setIsLoading(true)
    setError('')
    try {
      const res = await api.ingest.list()
      setDocuments(res.documents || [])
    } catch {
      setError('无法加载文档列表')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (docName: string) => {
    if (!window.confirm(`确定删除文档「${docName}」吗？`)) return
    try {
      await api.ingest.delete(docName)
      fetchDocuments()
    } catch { /* ignore */ }
  }

  const handlePreview = async (doc: DocInfo) => {
    setPreviewDoc({ doc_name: doc.doc_name, content: '', loading: true })
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8897'}/api/ingest/documents/${encodeURIComponent(doc.doc_name)}/content`)
      const data = await res.json()
      setPreviewDoc({ doc_name: doc.doc_name, content: data.content || '（文档内容为空）', loading: false })
    } catch {
      setPreviewDoc({ doc_name: doc.doc_name, content: '无法加载文档内容', loading: false })
    }
  }

  useEffect(() => {
    fetchDocuments()
  }, [])

  const cardStyle: React.CSSProperties = {
    background: 'var(--card)',
    border: '1px solid var(--border-faint)',
    borderRadius: '2px',
    padding: '16px',
    transition: 'border-color 0.2s',
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <PageHeader title="文档库" description="已导入的财报、研报等文档" />

      <button
        onClick={fetchDocuments}
        disabled={isLoading}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded mb-6 transition-colors"
        style={{
          color: 'var(--text-sec)',
          border: '1px solid var(--border-faint)',
          background: 'var(--card)',
          fontFamily: 'Georgia, "Noto Serif SC", serif',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--gold)' }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-faint)' }}
      >
        <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
        <span>刷新</span>
      </button>

      {isLoading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>加载中...</p>
      ) : error ? (
        <div
          className="flex flex-col items-center justify-center py-16"
          style={{ color: 'var(--text-muted)' }}
        >
          <p style={{ fontSize: '0.85rem', fontFamily: 'Georgia, "Noto Serif SC", serif' }}>
            {error}
          </p>
        </div>
      ) : documents.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center py-16"
          style={{ color: 'var(--text-muted)' }}
        >
          <BookOpen size={40} className="mb-3" style={{ opacity: 0.3 }} />
          <p style={{ fontSize: '0.85rem', fontFamily: 'Georgia, "Noto Serif SC", serif' }}>
            还没有导入文档
          </p>
          <p style={{ fontSize: '0.7rem', marginTop: '4px' }}>
            在侧边栏上传 PDF 文档后，内容将显示在此处
          </p>
        </div>
      ) : (
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
          {documents.map((doc) => (
            <div key={doc.doc_name} style={cardStyle}
              className="cursor-pointer"
              onClick={() => handlePreview(doc)}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--gold)' }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-faint)' }}
            >
              <div className="flex items-start gap-3">
                <FileText size={16} style={{ color: 'var(--gold)', flexShrink: 0, marginTop: '2px' }} />
                <div className="min-w-0 flex-1">
                  <div
                    className="truncate font-medium"
                    style={{
                      fontSize: '0.85rem',
                      color: 'var(--text)',
                      fontFamily: 'Georgia, "Noto Serif SC", serif',
                    }}
                  >
                    {doc.doc_name}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {doc.company && (
                      <span
                        className="text-xs px-2 py-0.5 rounded"
                        style={{
                          background: 'var(--jade-bg)',
                          color: 'var(--jade)',
                        }}
                      >
                        {doc.company}
                        {doc.company_code ? ` (${doc.company_code})` : ''}
                      </span>
                    )}
                    {doc.doc_type && (
                      <span
                        className="text-xs px-2 py-0.5 rounded"
                        style={{
                          background: 'var(--card-hover)',
                          color: 'var(--text-sec)',
                        }}
                      >
                        {doc.doc_type}
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      {doc.chunk_count} 个文本块
                    </span>
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <ExternalLink size={12} style={{ color: 'var(--text-muted)', opacity: 0.4 }} />
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(doc.doc_name) }}
                    className="p-1 transition-opacity rounded"
                    style={{ color: 'var(--text-muted)', opacity: 0.4 }}
                    onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                    onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.4' }}
                    title="删除文档"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 文档预览弹窗 */}
      {previewDoc && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.5)' }}
          onClick={() => setPreviewDoc(null)}
        >
          <div
            className="max-w-3xl max-h-[80vh] w-[90vw] overflow-y-auto p-6 rounded"
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
                {previewDoc.doc_name}
              </h2>
              <button
                onClick={() => setPreviewDoc(null)}
                style={{ color: 'var(--text-muted)', fontSize: '1.2rem', cursor: 'pointer' }}
              >
                &times;
              </button>
            </div>
            {previewDoc.loading ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>加载中...</p>
            ) : (
              <div className="prose prose-sm max-w-none"
                style={{
                  color: 'var(--text)',
                  fontFamily: 'Georgia, "Noto Serif SC", serif',
                  fontSize: '0.8rem',
                  lineHeight: 1.8,
                }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {previewDoc.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
