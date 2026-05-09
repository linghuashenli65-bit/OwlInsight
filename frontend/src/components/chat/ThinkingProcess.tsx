'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { ChevronDown, Loader2 } from 'lucide-react'

interface ThinkingProcessProps {
  steps: string[]
  isStreaming?: boolean
}

export function ThinkingProcess({ steps, isStreaming }: ThinkingProcessProps) {
  const [expanded, setExpanded] = useState(false)

  if (!steps || steps.length === 0) return null

  return (
    <div className="mb-3" style={{ fontFamily: 'Georgia, "Noto Serif SC", serif' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs tracking-wider uppercase w-full py-1 transition-colors"
        style={{ color: 'var(--text-sec)' }}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)' }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-sec)' }}
      >
        <motion.span
          animate={{ rotate: expanded ? 0 : -90 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown size={12} />
        </motion.span>
        <span>分析过程</span>
        {isStreaming && <Loader2 size={10} className="animate-spin" />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-1 ml-4">
              {steps.map((step, i) => (
                <motion.div
                  key={i}
                  className="flex items-start gap-3 py-1.5 text-xs"
                  style={{ color: 'var(--text-sec)' }}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0"
                    style={{ background: 'var(--brand)', opacity: 0.5 }}
                  />
                  <span>{step}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
