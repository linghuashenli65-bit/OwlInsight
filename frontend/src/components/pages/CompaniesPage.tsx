'use client'

import { useEffect, useState } from 'react'
import { TrendingUp, BarChart3, Trash2 } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { useSidebarStore } from '@/store/sidebarStore'
import { useChatStore } from '@/store/chatStore'
import { useNavStore } from '@/store/navStore'
import { api } from '@/lib/api'

export function CompaniesPage() {
  const watchedCompanies = useSidebarStore((s) => s.watchedCompanies)
  const isLoading = useSidebarStore((s) => s.isLoading)
  const fetchCompanies = useSidebarStore((s) => s.fetchCompanies)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const navigate = useNavStore((s) => s.navigate)
  const [deleting, setDeleting] = useState<string | null>(null)

  useEffect(() => {
    fetchCompanies()
  }, [])

  const handleAnalyze = (companyName: string) => {
    navigate('chat')
    setTimeout(() => sendMessage(`分析${companyName}最新财务`), 100)
  }

  const handleDelete = async (code: string) => {
    if (deleting === code) {
      try {
        await api.companies.delete(code)
        fetchCompanies()
      } catch { /* ignore */ }
      setDeleting(null)
    } else {
      setDeleting(code)
      setTimeout(() => setDeleting(null), 2000)
    }
  }

  // 按分析次数降序排列
  const sorted = [...watchedCompanies].sort((a, b) => b.analysis_count - a.analysis_count)

  const cardStyle: React.CSSProperties = {
    background: 'var(--card)',
    border: '1px solid var(--border-faint)',
    borderRadius: '2px',
    padding: '16px',
    transition: 'border-color 0.2s',
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <PageHeader title="关注公司" description="跟踪关注的上市公司与最新分析" />

      {isLoading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>加载中...</p>
      ) : sorted.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center py-16"
          style={{ color: 'var(--text-muted)' }}
        >
          <BarChart3 size={40} className="mb-3" style={{ opacity: 0.3 }} />
          <p style={{ fontSize: '0.85rem', fontFamily: 'Georgia, "Noto Serif SC", serif' }}>
            还没有关注的公司
          </p>
          <p style={{ fontSize: '0.7rem', marginTop: '4px' }}>
            在对话中分析公司后会自动添加到列表
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sorted.map((company) => (
            <div key={company.company_code} style={cardStyle}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--gold)' }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-faint)' }}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3
                    style={{
                      fontSize: '0.9rem',
                      fontWeight: 500,
                      color: 'var(--text)',
                      fontFamily: 'Georgia, "Noto Serif SC", serif',
                    }}
                  >
                    {company.company_name}
                  </h3>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      color: 'var(--text-muted)',
                      fontFamily: 'monospace',
                    }}
                  >
                    {company.company_code}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <TrendingUp size={16} style={{ color: 'var(--gold)', opacity: 0.6 }} />
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(company.company_code) }}
                    className="p-1 transition-colors rounded"
                    style={{
                      color: deleting === company.company_code ? 'var(--vermillion)' : 'var(--text-muted)',
                      opacity: 0.5,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                    onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.5' }}
                    title={deleting === company.company_code ? '确认删除' : '取消关注'}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              <div className="mt-3 flex items-center gap-3">
                <span
                  style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-sec)',
                  }}
                >
                  分析次数: {company.analysis_count}
                </span>
              </div>

              <button
                onClick={() => handleAnalyze(company.company_name)}
                className="mt-3 w-full py-1.5 text-xs transition-all rounded"
                style={{
                  background: 'transparent',
                  color: 'var(--gold)',
                  border: '1px solid var(--gold)',
                  cursor: 'pointer',
                  fontFamily: 'Georgia, "Noto Serif SC", serif',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--gold)'
                  e.currentTarget.style.color = '#fff'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'var(--gold)'
                }}
              >
                分析最新财务
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
