'use client'

import { useRef, useEffect } from 'react'
import { Menu } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { MessageItem } from './MessageItem'
import { InputArea } from './InputArea'
import { WelcomePage } from './WelcomePage'
import toast from 'react-hot-toast'

interface ChatMainProps {
  onMenuClick: () => void
}

export function ChatMain({ onMenuClick }: ChatMainProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const conversations = useChatStore((s) => s.conversations)
  const currentId = useChatStore((s) => s.currentConversationId)
  const isLoading = useChatStore((s) => s.isLoading)
  const sendMessage = useChatStore((s) => s.sendMessage)

  const currentConv = conversations.find((c) => c.id === currentId)
  const messages = currentConv?.messages || []
  const hasMessages = messages.length > 0

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, messages[messages.length - 1]?.content])

  const handleSend = (content: string) => {
    sendMessage(content)
  }

  const handleSuggestion = (query: string) => {
    sendMessage(query)
  }

  const handleAnalyze = (metric: string) => {
    sendMessage(`详细分析${metric}变化原因`)
  }

  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content)
      toast.success('已复制到剪贴板')
    } catch {
      toast.error('复制失败')
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* 顶部栏 */}
      <div
        className="flex items-center justify-between px-4 py-3 md:px-6 border-b"
        style={{ borderColor: 'var(--border-faint)' }}
      >
        <button
          onClick={onMenuClick}
          className="md:hidden p-2 -ml-2 transition-colors"
          style={{ color: 'var(--text-sec)' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-sec)' }}
        >
          <Menu size={20} />
        </button>

        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 flex items-center justify-center"
            style={{ borderRadius: '2px', overflow: 'hidden' }}
          >
            <img src="/logo.png" alt="枭研" className="w-full h-full object-cover" />
          </div>
          <div>
            <div className="text-sm font-bold" style={{ color: 'var(--text)' }}>
              枭研
            </div>
            <div className="text-xs tracking-widest uppercase" style={{ color: 'var(--text-muted)' }}>
              OwlInsight
            </div>
          </div>
        </div>

        <div className="w-8" /> {/* spacer */}
      </div>

      {/* 消息区域 */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-chat mx-auto py-4">
          {!hasMessages ? (
            <WelcomePage onSuggestion={handleSuggestion} />
          ) : (
            <>
              {messages.map((msg, i) => (
                <MessageItem
                  key={msg.id}
                  message={msg}
                  isStreaming={isLoading && i === messages.length - 1 && msg.role === 'assistant'}
                  onAnalyze={handleAnalyze}
                  onCopy={handleCopy}
                />
              ))}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 输入栏 */}
      <InputArea
        onSend={handleSend}
        isLoading={isLoading}
      />
    </div>
  )
}
