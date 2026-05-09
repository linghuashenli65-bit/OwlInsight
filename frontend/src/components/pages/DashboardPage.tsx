'use client'

import { useEffect, useState, useCallback } from 'react'
import { TrendingUp, TrendingDown, BarChart3, MessageSquare, BookOpen, Newspaper, ArrowUpDown } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { useNavStore } from '@/store/navStore'
import { useLivePriceStore } from '@/store/livePriceStore'
import { StockDetail } from '@/components/chat/StockDetail'
import type { AppView } from '@/lib/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8897'

interface DashboardData {
  companies: Array<{
    company_code: string
    company_name: string
    analysis_count: number
    price_info: { price: number | null; change_pct: number; date: string }
  }>
  conversation_count: number
  notes_count: number
}

type SortMode = 'default' | 'gain' | 'loss'

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [sortMode, setSortMode] = useState<SortMode>('default')
  const livePrices = useLivePriceStore((s) => s.livePrices)
  const [selectedStock, setSelectedStock] = useState<{ code: string; name: string; price: number | null; changePct: number | null } | null>(null)
  const navigate = useNavStore((s) => s.navigate)
  const createNewConversation = useChatStore((s) => s.createNewConversation)
  const sendMessage = useChatStore((s) => s.sendMessage)

  useEffect(() => {
    fetch(`${BASE_URL}/api/data/dashboard`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
  }, [])

  // 合并实时价格
  const getDisplayPrice = useCallback((code: string, fallback: { price: number | null; change_pct: number }) => {
    const live = livePrices[code]
    if (live) {
      return { price: live.price, change_pct: live.change_pct }
    }
    return fallback
  }, [livePrices])

  const handleAnalyze = (name: string) => {
    createNewConversation()
    navigate('chat')
    setTimeout(() => sendMessage(`分析${name}最新财务`), 100)
  }

  const handleNewChat = () => {
    createNewConversation()
    navigate('chat')
  }

  const handleCardClick = (code: string, name: string, price: number | null, changePct: number | null) => {
    setSelectedStock({ code, name, price, changePct })
  }

  // 排序后的公司列表
  const sortedCompanies = (() => {
    const list = data?.companies || []
    if (sortMode === 'default') return list
    return [...list].sort((a, b) => {
      const pa = getDisplayPrice(a.company_code, a.price_info)
      const pb = getDisplayPrice(b.company_code, b.price_info)
      const pctA = pa.change_pct ?? 0
      const pctB = pb.change_pct ?? 0
      return sortMode === 'gain' ? pctB - pctA : pctA - pctB
    })
  })()

  const stats = [
    { icon: BarChart3, label: '关注公司', value: data?.companies.length ?? '-' },
    { icon: MessageSquare, label: '对话', value: data?.conversation_count ?? '-' },
    { icon: BookOpen, label: '研究笔记', value: data?.notes_count ?? '-' },
  ]

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-10">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--text)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}>
          枭研
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--text-muted)' }}>OwlInsight — 投资研究助手</p>

        {/* 统计 */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {stats.map((item, i) => (
            <div key={i} className="p-4 rounded" style={{ background: 'var(--card)', border: '1px solid var(--border-faint)' }}>
              <div className="flex items-center gap-2 mb-2">
                <item.icon size={16} style={{ color: 'var(--gold)' }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{item.label}</span>
              </div>
              <div className="text-2xl font-bold" style={{ color: 'var(--text)' }}>{item.value}</div>
            </div>
          ))}
        </div>

        {/* 快捷操作 */}
        <div className="flex gap-3 mb-8 flex-wrap">
          {[
            { label: '新建对话', onClick: handleNewChat, icon: MessageSquare },
            { label: '搜索新闻', onClick: () => { createNewConversation(); navigate('chat'); setTimeout(() => sendMessage('搜索一下最近财经新闻'), 100) }, icon: Newspaper },
          ].map((btn, i) => (
            <button
              key={i}
              onClick={btn.onClick}
              className="flex items-center gap-2 px-4 py-2 text-sm rounded transition-all"
              style={{ background: 'var(--card)', border: '1px solid var(--border-faint)', color: 'var(--text)' }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--gold)'; e.currentTarget.style.color = 'var(--gold)' }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-faint)'; e.currentTarget.style.color = 'var(--text)' }}
            >
              <btn.icon size={14} />
              <span>{btn.label}</span>
            </button>
          ))}
        </div>

        {/* 盯盘 */}
        {sortedCompanies.length > 0 && (
          <>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold" style={{ color: 'var(--text)' }}>关注公司</h2>
              <div className="flex items-center gap-1">
                <ArrowUpDown size={12} style={{ color: 'var(--text-muted)' }} />
                {(['default', 'gain', 'loss'] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setSortMode(m)}
                    className="text-[0.65rem] px-2 py-0.5 rounded transition-colors"
                    style={{
                      background: sortMode === m ? 'var(--gold)' : 'transparent',
                      color: sortMode === m ? '#fff' : 'var(--text-muted)',
                    }}
                  >
                    {m === 'default' ? '默认' : m === 'gain' ? '涨幅↑' : '跌幅↑'}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {sortedCompanies.map((c) => {
                const display = getDisplayPrice(c.company_code, c.price_info)
                const isUp = (display.change_pct ?? 0) >= 0
                return (
                  <div
                    key={c.company_code}
                    className="p-4 rounded cursor-pointer transition-all duration-200 hover:scale-[1.01]"
                    style={{ background: 'var(--card)', border: '1px solid var(--border-faint)' }}
                    onClick={() => handleCardClick(c.company_code, c.company_name, display.price, display.change_pct)}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>{c.company_name}</div>
                        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{c.company_code}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold" style={{ color: 'var(--text)' }}>{display.price ?? '--'}</div>
                        <div className="flex items-center gap-1 text-xs" style={{ color: isUp ? 'var(--vermillion)' : 'var(--jade)' }}>
                          {isUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                          <span>{display.change_pct != null ? `${display.change_pct >= 0 ? '+' : ''}${display.change_pct.toFixed(2)}%` : '--'}</span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleAnalyze(c.company_name) }}
                      className="mt-3 text-xs px-3 py-1 rounded transition-colors"
                      style={{ color: 'var(--gold)', border: '1px solid var(--border-faint)' }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--card-hover)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                    >
                      快速分析
                    </button>
                  </div>
                )
              })}
            </div>
          </>
        )}

        {(!data?.companies || data.companies.length === 0) && (
          <div className="text-center py-16" style={{ color: 'var(--text-muted)' }}>
            <BarChart3 size={40} className="mx-auto mb-3" style={{ opacity: 0.3 }} />
            <p style={{ fontSize: '0.85rem' }}>还没有关注公司</p>
            <p style={{ fontSize: '0.7rem', marginTop: '4px' }}>开始对话分析公司后会自动出现在这里</p>
          </div>
        )}
      </div>

      {/* Stock Detail Modal */}
      {selectedStock && (
        <StockDetail
          code={selectedStock.code}
          name={selectedStock.name}
          price={selectedStock.price}
          changePct={selectedStock.changePct}
          onClose={() => setSelectedStock(null)}
        />
      )}
    </div>
  )
}
