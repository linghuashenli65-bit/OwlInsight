'use client'

import { motion } from 'motion/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '@/lib/types'
import { ThinkingProcess } from './ThinkingProcess'
import { CitationText, CitationList } from './CitationText'
import { AnomalyCard } from './AnomalyCard'
import { DataStatusBar } from './DataStatusBar'
import { StockChart } from './StockChart'
import { SaveNoteButton } from './SaveNoteButton'

interface MessageItemProps {
  message: ChatMessage
  isStreaming?: boolean
  onAnalyze?: (metric: string) => void
  onCopy?: (content: string) => void
}

export function MessageItem({ message, isStreaming, onAnalyze, onCopy }: MessageItemProps) {
  const isUser = message.role === 'user'
  const hasContent = message.content || (isStreaming && !isUser)

  if (!hasContent && !isStreaming) return null

  return (
    <motion.div
      className={`flex gap-3 px-4 md:px-0 ${isUser ? 'flex-row-reverse' : ''}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      style={{ margin: '16px 0', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
    >
      {/* 头像 */}
      <div
        className="w-8 h-8 flex-shrink-0 flex items-center justify-center text-sm"
        style={{
          background: isUser ? 'var(--vermillion-bg)' : 'var(--card)',
          border: isUser ? 'none' : '1px solid var(--border-faint)',
          color: isUser ? 'var(--brand)' : 'var(--text-sec)',
          borderRadius: '2px',
          fontFamily: 'Georgia, serif',
        }}
      >
        {isUser ? 'U' : 'B'}
      </div>

      {/* 气泡 */}
      <div
        className={`max-w-[82%] ${isUser ? '' : 'flex-1 min-w-0'}`}
      >
        {/* 用户消息 */}
        {isUser && (
          <div
            className="message-bubble-user px-5 py-3.5 inline-block"
            style={{ maxWidth: '100%' }}
          >
            <div className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</div>
          </div>
        )}

        {/* AI 消息 */}
        {!isUser && (
          <div className="message-bubble-ai px-5 py-3.5">
            {/* 思考过程 */}
            <ThinkingProcess
              steps={message.reasoning || []}
              isStreaming={isStreaming}
            />

            {/* 正文 */}
            <div className="prose-custom text-sm leading-relaxed">
              {message.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    table: ({ children }) => (
                      <div className="overflow-x-auto">
                        <table className="min-w-full">{children}</table>
                      </div>
                    ),
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--brand)' }}>
                        {children}
                      </a>
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              ) : isStreaming ? (
                <span className="inline-flex gap-0.5">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--text-muted)', animation: 'pulse 1.4s ease-in-out infinite' }} />
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--text-muted)', animation: 'pulse 1.4s ease-in-out 0.2s infinite' }} />
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--text-muted)', animation: 'pulse 1.4s ease-in-out 0.4s infinite' }} />
                </span>
              ) : null}
            </div>

            {/* 股价图表 */}
            {message.chartData && message.chartData.data?.length > 0 && (
              <StockChart data={message.chartData} />
            )}

            {/* 保存笔记按钮 */}
            {message.savePrompt && !isStreaming && (
              <SaveNoteButton prompt={message.savePrompt} />
            )}

            {/* 引用列表 */}
            {message.citations && message.citations.length > 0 && (
              <CitationList citations={message.citations} />
            )}

            {/* 数据状态 */}
            {message.dataStatus && message.dataStatus.length > 0 && (
              <DataStatusBar statuses={message.dataStatus} />
            )}

            {/* 异常卡片 */}
            {message.anomalies && message.anomalies.length > 0 && (
              <AnomalyCard
                anomalies={message.anomalies}
                onAnalyze={onAnalyze}
              />
            )}

            {/* 操作按钮 */}
            {message.content && (
              <div className="flex gap-4 mt-3 pt-2" style={{ borderTop: '1px solid var(--border-faint)' }}>
                <button
                  onClick={() => onCopy?.(message.content)}
                  className="text-xs transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                  onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-sec)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
                >
                  复制
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  )
}
