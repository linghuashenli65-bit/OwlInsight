'use client'

import { Download } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import toast from 'react-hot-toast'

export function ExportButton() {
  const currentId = useChatStore((s) => s.currentConversationId)
  const exportMd = useChatStore((s) => s.exportToMarkdown)

  const handleExport = () => {
    if (!currentId) return
    const md = exportMd(currentId)
    if (!md) {
      toast.error('没有可导出的内容')
      return
    }

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `financebot_${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('已导出')
  }

  return (
    <button
      onClick={handleExport}
      className="flex items-center gap-2 w-full px-3 py-2 text-xs transition-colors rounded"
      style={{ color: 'var(--text-sec)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--card-hover)'
        e.currentTarget.style.color = 'var(--text)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'var(--text-sec)'
      }}
    >
      <Download size={12} />
      <span>导出 Markdown</span>
    </button>
  )
}
