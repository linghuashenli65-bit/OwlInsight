'use client'

import type { WatchedCompany } from '@/lib/types'
import { Loader2 } from 'lucide-react'

interface WatchedCompaniesProps {
  companies: WatchedCompany[]
  isLoading: boolean
  onSelect: (companyName: string) => void
}

export function WatchedCompanies({ companies, isLoading, onSelect }: WatchedCompaniesProps) {
  return (
    <div className="px-3 py-2">
      <div
        className="text-xs tracking-wider uppercase mb-2 font-medium"
        style={{ color: 'var(--text-muted)', letterSpacing: '0.06em' }}
      >
        关注的公司
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 py-2" style={{ color: 'var(--text-muted)' }}>
          <Loader2 size={12} className="animate-spin" />
          <span className="text-xs">加载中…</span>
        </div>
      ) : companies.length === 0 ? (
        <div className="text-xs py-2" style={{ color: 'var(--text-muted)' }}>
          暂无关注公司
        </div>
      ) : (
        <div className="space-y-0.5">
          {companies.map((co) => (
            <button
              key={co.company_code}
              onClick={() => onSelect(co.company_name)}
              className="w-full text-left px-2 py-1.5 text-xs transition-colors rounded"
              style={{ color: 'var(--text-sec)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--card-hover)'
                e.currentTarget.style.color = 'var(--gold)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = 'var(--text-sec)'
              }}
            >
              <span>{co.company_name}</span>
              <span className="ml-2 opacity-50">{co.analysis_count}次</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
