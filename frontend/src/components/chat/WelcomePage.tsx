'use client'

import { motion } from 'motion/react'

const SUGGESTIONS = [
  { query: '茅台最近怎么样？', desc: '模糊意图反问' },
  { query: '对比茅台和五粮液', desc: '多公司对比分析' },
  { query: '分析宁德时代估值', desc: '估值 + 行业对比' },
  { query: '回顾上次分析', desc: '从历史中回顾' },
]

interface WelcomePageProps {
  onSuggestion: (query: string) => void
}

export function WelcomePage({ onSuggestion }: WelcomePageProps) {
  return (
    <motion.div
      className="flex-1 flex flex-col items-center justify-center px-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {/* Logo */}
      <div
        className="w-16 h-16 flex items-center justify-center mb-4"
        style={{ borderRadius: '4px', overflow: 'hidden' }}
      >
        <img src="/logo.png" alt="枭研" className="w-full h-full object-cover" />
      </div>

      <h2
        className="text-4xl font-bold mb-2"
        style={{ color: 'var(--brand)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
      >
        枭研
      </h2>

      <p className="text-sm mb-8" style={{ color: 'var(--text-sec)' }}>
        OwlInsight — 有来源、可追溯、懂你的投资研究
      </p>

      <div className="flex gap-6 mb-10 text-xs tracking-widest uppercase" style={{ color: 'var(--text-muted)' }}>
        <span>模糊问答</span>
        <span>学术引用</span>
        <span>越用越懂</span>
      </div>

      <div className="grid grid-cols-2 gap-3 w-full max-w-md">
        {SUGGESTIONS.map((item) => (
          <button
            key={item.query}
            onClick={() => onSuggestion(item.query)}
            className="text-left px-4 py-3 transition-all duration-200 hover:scale-[1.02]"
            style={{
              background: 'var(--card)',
              border: '1px solid var(--border-faint)',
              borderRadius: '2px',
              color: 'var(--text)',
              fontFamily: 'Georgia, "Noto Serif SC", serif',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--gold)'
              e.currentTarget.style.color = 'var(--gold)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--border-faint)'
              e.currentTarget.style.color = 'var(--text)'
            }}
          >
            <div className="text-sm font-medium">{item.query}</div>
            <div className="text-xs mt-1 opacity-60">{item.desc}</div>
          </button>
        ))}
      </div>
    </motion.div>
  )
}
