'use client'

import { useState, useRef } from 'react'
import { Upload, File, Loader2, CheckCircle, XCircle } from 'lucide-react'
import type { IngestionResult } from '@/lib/types'
import toast from 'react-hot-toast'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8897'

export function PdfUploader() {
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<IngestionResult | null>(null)
  const [expanded, setExpanded] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleUpload = async (file: File) => {
    if (!file.name.endsWith('.pdf')) {
      toast.error('仅支持 PDF 格式')
      return
    }

    setUploading(true)
    setResult(null)

    try {
      const form = new FormData()
      form.append('file', file)

      const res = await fetch(`${BASE_URL}/api/ingest/pdf`, {
        method: 'POST',
        body: form,
      })

      if (!res.ok) throw new Error(`上传失败: ${res.status}`)

      const data: IngestionResult = await res.json()
      setResult(data)
      toast.success('解析完成')
    } catch (err) {
      toast.error((err as Error).message)
      setResult({ success: false, errors: [(err as Error).message] })
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }

  return (
    <div className="px-3 py-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full text-xs tracking-wider uppercase font-medium mb-1 transition-colors"
        style={{ color: 'var(--text-muted)', letterSpacing: '0.06em' }}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-sec)' }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
      >
        <span className="flex items-center gap-1.5">
          <Upload size={10} />
          导入 PDF
        </span>
        <span>{expanded ? '−' : '+'}</span>
      </button>

      {expanded && (
        <div
          className="border border-dashed rounded p-3 text-center transition-colors cursor-pointer"
          style={{ borderColor: 'var(--border)' }}
          onDragOver={(e) => {
            e.preventDefault()
            e.currentTarget.style.borderColor = 'var(--brand)'
          }}
          onDragLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
          }}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleUpload(file)
              e.target.value = ''
            }}
          />

          {uploading ? (
            <div className="flex flex-col items-center gap-2 py-2">
              <Loader2 size={18} className="animate-spin" style={{ color: 'var(--brand)' }} />
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                解析中…
              </span>
            </div>
          ) : result ? (
            <div className="text-left text-xs" style={{ color: 'var(--text-sec)' }}>
              {result.success ? (
                <>
                  <div className="flex items-center gap-1.5 mb-1" style={{ color: 'var(--jade)' }}>
                    <CheckCircle size={12} />
                    <span className="font-medium">导入完成</span>
                  </div>
                  <div>{result.doc_name}</div>
                  <div className="opacity-60">
                    {result.total_pages}页 · {result.total_chunks}块
                    {result.total_tables ? ` · ${result.total_tables}表格` : ''}
                  </div>
                  <div className="opacity-60">
                    ⏱ {result.elapsed_seconds?.toFixed(1)}s
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-1.5 mb-1" style={{ color: 'var(--brand)' }}>
                    <XCircle size={12} />
                    <span className="font-medium">导入失败</span>
                  </div>
                  {result.errors?.map((e, i) => (
                    <div key={i}>• {e}</div>
                  ))}
                </>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1 py-2">
              <File size={16} style={{ color: 'var(--text-muted)' }} />
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                拖拽或点击上传 PDF
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
