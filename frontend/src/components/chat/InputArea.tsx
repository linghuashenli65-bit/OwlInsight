'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { Send, Loader2 } from 'lucide-react'

interface InputAreaProps {
  onSend: (content: string) => void
  isLoading?: boolean
  placeholder?: string
}

export function InputArea({ onSend, isLoading, placeholder }: InputAreaProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isLoading])

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px' // max ~4 rows
  }

  return (
    <div
      className="border-t px-4 py-3 md:px-6"
      style={{
        background: 'var(--bg)',
        borderColor: 'var(--border-faint)',
      }}
    >
      <div className="max-w-chat mx-auto flex items-end gap-3">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              handleInput()
            }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || '输入问题，如"茅台最近怎么样"…'}
            disabled={isLoading}
            rows={1}
            className="w-full resize-none outline-none text-sm leading-relaxed py-2.5 px-4 transition-colors"
            style={{
              background: 'var(--input-bg)',
              color: 'var(--text)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              fontFamily: 'Georgia, "Noto Serif SC", serif',
              maxHeight: '120px',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = 'var(--brand)'
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = 'var(--border)'
            }}
          />
        </div>

        <button
          onClick={handleSend}
          disabled={isLoading || !value.trim()}
          className="flex-shrink-0 w-10 h-10 flex items-center justify-center transition-all duration-200 disabled:opacity-30"
          style={{
            background: 'var(--brand)',
            borderRadius: '2px',
            color: '#fff',
          }}
          onMouseEnter={(e) => {
            if (!isLoading && value.trim()) {
              e.currentTarget.style.opacity = '0.85'
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.opacity = '1'
          }}
        >
          {isLoading ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Send size={16} />
          )}
        </button>
      </div>

      {/* 底部提示 */}
      <div className="max-w-chat mx-auto mt-2 text-center">
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          FinanceBot 可能出现错误，请核查重要信息
        </span>
      </div>
    </div>
  )
}
