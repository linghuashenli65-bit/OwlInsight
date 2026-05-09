'use client'

import { useEffect, useState } from 'react'
import { X, Plus, MessageSquare, Settings, Building2, FileText, Trash2, BarChart3, BookOpen } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { useNavStore } from '@/store/navStore'
import { SidebarBrand } from '@/components/sidebar/SidebarBrand'
import { PdfUploader } from '@/components/sidebar/PdfUploader'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { AlertBell } from '@/components/alerter/AlertBell'
import { ExportButton } from '@/components/ui/ExportButton'
import { formatDate } from '@/lib/utils'
import type { AppView } from '@/lib/types'

interface ChatSidebarProps {
  open: boolean
  onToggle: () => void
  onClose: () => void
}

const NAV_ITEMS: { view: AppView; label: string; icon: React.ReactNode }[] = [
  { view: 'dashboard', label: '盯盘', icon: <BarChart3 size={14} /> },
  { view: 'chat', label: '对话', icon: <MessageSquare size={14} /> },
  { view: 'settings', label: '设置', icon: <Settings size={14} /> },
  { view: 'companies', label: '关注公司', icon: <Building2 size={14} /> },
  { view: 'notes', label: '笔记', icon: <FileText size={14} /> },
  { view: 'documents', label: '文档库', icon: <BookOpen size={14} /> },
]

export function ChatSidebar({ open, onToggle, onClose }: ChatSidebarProps) {
  const createNewConversation = useChatStore((s) => s.createNewConversation)
  const switchConversation = useChatStore((s) => s.switchConversation)
  const deleteConversation = useChatStore((s) => s.deleteConversation)
  const conversationList = useChatStore((s) => s.conversationList)
  const currentId = useChatStore((s) => s.currentConversationId)
  const fetchConversationList = useChatStore((s) => s.fetchConversationList)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const currentView = useNavStore((s) => s.currentView)
  const navigate = useNavStore((s) => s.navigate)

  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    fetchConversationList()
  }, [])

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 md:hidden"
          style={{ background: 'rgba(0,0,0,0.4)' }}
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed md:relative inset-y-0 left-0 z-40
          w-[260px] flex flex-col
          transition-transform duration-300 ease-out
          ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          md:flex
        `}
        style={{
          background: 'var(--bg-alt)',
          borderRight: '1px solid var(--border-faint)',
        }}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-2 pt-3 pb-1">
          <SidebarBrand />
          <button
            onClick={onClose}
            className="md:hidden p-1 transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* 新建对话 + 主题 */}
        <div className="px-3 space-y-1 mb-2">
          <button
            onClick={() => {
              createNewConversation()
              navigate('chat')
              onClose()
            }}
            className="flex items-center gap-2 w-full px-3 py-2 text-xs transition-colors rounded"
            style={{
              color: 'var(--text-sec)',
              border: '1px solid var(--border-faint)',
              fontFamily: 'Georgia, "Noto Serif SC", serif',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--gold)'
              e.currentTarget.style.color = 'var(--gold)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--border-faint)'
              e.currentTarget.style.color = 'var(--text-sec)'
            }}
          >
            <Plus size={12} />
            <span>新建对话</span>
          </button>
          <div className="flex items-center gap-1">
            <AlertBell />
            <ThemeToggle />
          </div>
        </div>

        {/* 导航区 */}
        <div className="px-3 space-y-0.5 mb-2">
          {NAV_ITEMS.map((item) => {
            const active = currentView === item.view
            return (
              <button
                key={item.view}
                onClick={() => {
                  navigate(item.view)
                  onClose()
                }}
                className="flex items-center gap-2 w-full px-3 py-1.5 text-xs transition-colors rounded"
                style={{
                  color: active ? 'var(--gold)' : 'var(--text-sec)',
                  background: active ? 'var(--card-hover)' : 'transparent',
                  fontFamily: 'Georgia, "Noto Serif SC", serif',
                }}
                onMouseEnter={(e) => {
                  if (!active) {
                    e.currentTarget.style.background = 'var(--card-hover)'
                    e.currentTarget.style.color = 'var(--text)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!active) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'var(--text-sec)'
                  }
                }}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            )
          })}
        </div>

        {/* ── 对话历史列表 ── */}
        <div style={{ borderTop: '1px solid var(--border-faint)' }} />
        <div className="flex-1 overflow-y-auto py-1">
          {/* 对话列表 */}
          {conversationList.length > 0 && (
            <div className="px-2 space-y-0.5 mb-3">
              <div
                className="px-2 py-1 text-[0.6rem] tracking-wider uppercase font-medium"
                style={{ color: 'var(--text-muted)', letterSpacing: '0.06em' }}
              >
                历史对话
              </div>
              {conversationList.map((conv) => {
                const active = conv.id === currentId
                return (
                  <div
                    key={conv.id}
                    className="group flex items-center gap-1 rounded transition-colors"
                    style={{
                      background: active ? 'var(--card-hover)' : 'transparent',
                    }}
                  >
                    <button
                      onClick={() => {
                        switchConversation(conv.id)
                        navigate('chat')
                        onClose()
                      }}
                      className="flex-1 text-left px-2 py-1.5 text-xs truncate transition-colors rounded"
                      style={{
                        color: active ? 'var(--gold)' : 'var(--text-sec)',
                        fontFamily: 'Georgia, "Noto Serif SC", serif',
                      }}
                      onMouseEnter={(e) => {
                        if (!active) e.currentTarget.style.color = 'var(--text)'
                      }}
                      onMouseLeave={(e) => {
                        if (!active) e.currentTarget.style.color = 'var(--text-sec)'
                      }}
                    >
                      <span className="block truncate">{conv.title}</span>
                      <span className="block text-[0.6rem] opacity-50 mt-0.5">
                        {conv.message_count}条消息 · {formatDate(conv.updated_at)}
                      </span>
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation()
                        if (deletingId === conv.id) {
                          await deleteConversation(conv.id)
                          setDeletingId(null)
                        } else {
                          setDeletingId(conv.id)
                          setTimeout(() => setDeletingId(null), 2000)
                        }
                      }}
                      className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity rounded"
                      style={{
                        color: deletingId === conv.id ? 'var(--vermillion)' : 'var(--text-muted)',
                      }}
                      title={deletingId === conv.id ? '确认删除' : '删除'}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}

        </div>

        {/* 底部区域 */}
        <div style={{ borderTop: '1px solid var(--border-faint)' }}>
          <PdfUploader />
          <div className="px-3 py-2">
            <ExportButton />
          </div>
          <div
            className="px-3 py-2 text-[0.6rem] tracking-wider"
            style={{ color: 'var(--text-muted)' }}
          >
            枭研 v1.0
          </div>
        </div>
      </aside>
    </>
  )
}
