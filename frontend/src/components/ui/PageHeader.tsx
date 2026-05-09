'use client'

import { ArrowLeft } from 'lucide-react'
import { useNavStore } from '@/store/navStore'

interface PageHeaderProps {
  title: string
  description?: string
  showBack?: boolean
}

export function PageHeader({ title, description, showBack = true }: PageHeaderProps) {
  const navigate = useNavStore((s) => s.navigate)

  return (
    <div className="flex items-start gap-3 mb-6">
      {showBack && (
        <button
          onClick={() => navigate('chat')}
          className="mt-1 p-1 rounded transition-colors flex-shrink-0"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--gold)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
        >
          <ArrowLeft size={18} />
        </button>
      )}
      <div>
        <h1
          className="text-lg font-medium"
          style={{ fontFamily: 'Georgia, "Noto Serif SC", serif', color: 'var(--text)' }}
        >
          {title}
        </h1>
        {description && (
          <p className="text-xs mt-1" style={{ color: 'var(--text-sec)' }}>
            {description}
          </p>
        )}
      </div>
    </div>
  )
}
