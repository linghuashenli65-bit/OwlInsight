'use client'

import { useEffect, useState, useMemo } from 'react'
import { X, TrendingUp, TrendingDown } from 'lucide-react'
import { api } from '@/lib/api'
import { StockChart } from './StockChart'

interface StockDetailProps {
  code: string
  name: string
  price?: number | null
  changePct?: number | null
  onClose: () => void
}

type ViewTab = 'kline' | 'fund'
type Period = 'intraday' | 'minute' | 'daily' | 'weekly' | 'monthly'

export function StockDetail({ code, name, price, changePct, onClose }: StockDetailProps) {
  const [viewTab, setViewTab] = useState<ViewTab>('kline')
  const [period, setPeriod] = useState<Period>('daily')
  const [minuteInterval, setMinuteInterval] = useState(5)
  const [chartData, setChartData] = useState<any[]>([])
  const [fundData, setFundData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const isUp = (changePct ?? 0) >= 0

  useEffect(() => {
    setLoading(true)
    if (viewTab === 'kline') {
      if (period === 'intraday') {
        api.stock.intraday(code).then((r) => { setChartData(r.data || []); setLoading(false) })
          .catch(() => setLoading(false))
      } else if (period === 'minute') {
        api.stock.minuteKline(code, minuteInterval).then((r) => { setChartData(r.data || []); setLoading(false) })
          .catch(() => setLoading(false))
      } else {
        api.stock.kline(code, period).then((r) => { setChartData(r.data || []); setLoading(false) })
          .catch(() => setLoading(false))
      }
    } else {
      api.stock.fundFlow(code).then((r) => { setFundData(r.data || []); setLoading(false) })
        .catch(() => setLoading(false))
    }
  }, [viewTab, period, minuteInterval, code])

  // 分时图预处理
  const intradayPoints = useMemo(() => {
    if (viewTab !== 'kline' || period !== 'intraday' || chartData.length === 0) return []
    const prices = chartData.map((d) => d.price).filter((v: any) => v != null)
    if (prices.length === 0) return []
    const firstPrice = prices[0]
    return chartData.map((d) => ({
      time: d.time,
      price: d.price,
      volume: d.volume,
      change_pct: firstPrice && d.price ? ((d.price - firstPrice) / firstPrice * 100) : 0,
    }))
  }, [chartData, viewTab, period])

  // K线图数据
  const candleData = useMemo(() => {
    if (viewTab !== 'kline' || period === 'intraday' || chartData.length === 0) return null
    return {
      type: 'candlestick' as const,
      data: chartData.map((d) => ({
        symbol: code,
        date: d.date,
        open: d.open,
        close: d.close,
        high: d.high,
        low: d.low,
        volume: d.volume || 0,
        amount: null,
        change_pct: null,
      })),
    }
  }, [chartData, viewTab, period, code])

  const periodLabels: Record<Period, string> = {
    intraday: '分时', minute: '分钟', daily: '日K', weekly: '周K', monthly: '月K',
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl max-h-[85vh] overflow-y-auto rounded"
        style={{ background: 'var(--bg)', border: '1px solid var(--border-faint)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b sticky top-0 z-10" style={{ borderColor: 'var(--border-faint)', background: 'var(--bg)' }}>
          <div className="flex items-center gap-3">
            <div>
              <div className="text-base font-bold" style={{ color: 'var(--text)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}>{name}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{code}</div>
            </div>
            {price != null && (
              <div className="text-right ml-4">
                <div className="text-xl font-bold" style={{ color: 'var(--text)' }}>{price.toFixed(2)}</div>
                <div className="flex items-center gap-1 text-xs" style={{ color: isUp ? 'var(--vermillion)' : 'var(--jade)' }}>
                  {isUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                  <span>{changePct != null ? `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%` : '--'}</span>
                </div>
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1 rounded transition-colors" style={{ color: 'var(--text-muted)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)' }}
          ><X size={18} /></button>
        </div>

        {/* 一级 Tab：K线 / 资金流向 / 机构持仓 */}
        <div className="flex border-b" style={{ borderColor: 'var(--border-faint)' }}>
          {([
            { key: 'kline' as ViewTab, label: 'K线图' },
            { key: 'fund' as ViewTab, label: '资金流向' },
          ]).map((t) => (
            <button key={t.key} onClick={() => setViewTab(t.key)}
              className="px-4 py-2.5 text-xs font-medium transition-colors"
              style={{
                color: viewTab === t.key ? 'var(--gold)' : 'var(--text-muted)',
                borderBottom: viewTab === t.key ? '2px solid var(--gold)' : '2px solid transparent',
              }}
            >{t.label}</button>
          ))}
        </div>

        {viewTab === 'kline' ? (
          /* ── K线图 ── */
          <>
            {/* 二级周期栏 */}
            <div className="flex items-center border-b px-2" style={{ borderColor: 'var(--border-faint)' }}>
              {(Object.entries(periodLabels) as [Period, string][]).map(([key, label]) => (
                <button key={key} onClick={() => setPeriod(key)}
                  className="px-3 py-2 text-xs font-medium transition-colors"
                  style={{
                    color: period === key ? 'var(--gold)' : 'var(--text-muted)',
                    borderBottom: period === key ? '2px solid var(--gold)' : '2px solid transparent',
                  }}
                >{label}</button>
              ))}
              {period === 'minute' && (
                <div className="flex items-center gap-1 ml-auto">
                  {[1, 5, 15, 30, 60].map((iv) => (
                    <button key={iv} onClick={() => setMinuteInterval(iv)}
                      className="text-[0.6rem] px-1.5 py-0.5 rounded"
                      style={{
                        background: minuteInterval === iv ? 'var(--gold)' : 'transparent',
                        color: minuteInterval === iv ? '#fff' : 'var(--text-muted)',
                      }}
                    >{iv}分</button>
                  ))}
                </div>
              )}
            </div>

            <div className="p-4">
              {loading && chartData.length === 0 ? (
                <div className="text-xs py-8 text-center" style={{ color: 'var(--text-muted)' }}>加载中...</div>
              ) : chartData.length === 0 ? (
                <div className="text-xs py-8 text-center" style={{ color: 'var(--text-muted)' }}>暂无数据</div>
              ) : period === 'intraday' ? (
                <IntradayChart points={intradayPoints} data={chartData} />
              ) : (
                  candleData && <StockChart data={candleData} mode="candlestick" />
              )}
            </div>
          </>
        ) : viewTab === 'fund' ? (
          /* ── 资金流向 ── */
          <div className="p-4">
            {loading && fundData.length === 0 ? (
              <div className="text-xs py-8 text-center" style={{ color: 'var(--text-muted)' }}>加载中...</div>
            ) : fundData.length === 0 ? (
              <div className="text-xs py-8 text-center" style={{ color: 'var(--text-muted)' }}>暂无资金流向数据</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs" style={{ color: 'var(--text)' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-faint)' }}>
                      <th className="text-left py-2 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>日期</th>
                      <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>主力净额</th>
                      <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>超大单</th>
                      <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>大单</th>
                      <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>中单</th>
                      <th className="text-right py-2 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>小单</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fundData.map((row, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border-faint)' }}>
                        <td className="py-2 px-2">{row.date}</td>
                        <td className="text-right py-2 px-2" style={{ color: (row.main_net ?? 0) >= 0 ? 'var(--vermillion)' : 'var(--jade)' }}>{formatMoney(row.main_net)}</td>
                        <td className="text-right py-2 px-2" style={{ color: (row.super_large_net ?? 0) >= 0 ? 'var(--vermillion)' : 'var(--jade)' }}>{formatMoney(row.super_large_net)}</td>
                        <td className="text-right py-2 px-2" style={{ color: (row.large_net ?? 0) >= 0 ? 'var(--vermillion)' : 'var(--jade)' }}>{formatMoney(row.large_net)}</td>
                        <td className="text-right py-2 px-2" style={{ color: (row.medium_net ?? 0) >= 0 ? 'var(--vermillion)' : 'var(--jade)' }}>{formatMoney(row.medium_net)}</td>
                        <td className="text-right py-2 px-2" style={{ color: (row.small_net ?? 0) >= 0 ? 'var(--vermillion)' : 'var(--jade)' }}>{formatMoney(row.small_net)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/* ── 分时图 ── */

function IntradayChart({ points, data }: { points: any[]; data: any[] }) {
  if (points.length === 0) return <div className="text-xs py-8 text-center" style={{ color: 'var(--text-muted)' }}>暂无日内数据</div>
  const prices = points.map((p) => p.price).filter((v: any) => v != null)
  const mn = Math.min(...prices)
  const mx = Math.max(...prices)
  const range = mx - mn || 1
  const pad = range * 0.08

  return (
    <>
      <div className="rounded p-3" style={{ background: 'var(--card)', border: '1px solid var(--border-faint)' }}>
        <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-sec)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}>日内分时走势</div>
        <svg viewBox="0 0 600 200" className="w-full" style={{ maxHeight: '220px' }}>
          <defs><linearGradient id="ig" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--gold)" stopOpacity={0.15} /><stop offset="100%" stopColor="var(--gold)" stopOpacity={0.01} /></linearGradient></defs>
          {(() => {
            const w = 480, h = 160, left = 60, top = 20
            const toY = (v: number) => top + h - ((v - (mn - pad)) / (range + 2 * pad)) * h
            const toX = (i: number) => left + (i / Math.max(points.length - 1, 1)) * w
            const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(p.price).toFixed(1)}`).join(' ')
            const gridLines = []
            for (let i = 0; i <= 4; i++) { const val = mn - pad + (range + 2 * pad) * (i / 4); gridLines.push({ y: top + h - (i / 4) * h, label: val.toFixed(2) }) }
            return (<>{gridLines.map((gl, gi) => (<g key={gi}><line x1={left} y1={gl.y} x2={left + w} y2={gl.y} stroke="var(--border-faint)" strokeWidth={0.5} /><text x={left - 6} y={gl.y + 3} textAnchor="end" fill="var(--text-muted)" fontSize={9} fontFamily="Georgia, serif">{gl.label}</text></g>))}<path d={`${path} L${toX(points.length - 1)},${top + h} L${toX(0)},${top + h} Z`} fill="url(#ig)" /><path d={path} fill="none" stroke="var(--gold)" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" /></>)
          })()}
        </svg>
        <div className="flex justify-between text-[0.6rem] mt-0.5" style={{ color: 'var(--text-muted)' }}><span>{points[0]?.time || ''}</span><span>{points[points.length - 1]?.time || ''}</span></div>
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-xs" style={{ color: 'var(--text)' }}>
          <thead><tr style={{ borderBottom: '1px solid var(--border-faint)' }}><th className="text-left py-1.5 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>时间</th><th className="text-right py-1.5 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>价格</th><th className="text-right py-1.5 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>涨跌幅</th><th className="text-right py-1.5 px-2 font-medium" style={{ color: 'var(--text-muted)' }}>成交量</th></tr></thead>
          <tbody>{data.map((row, i) => { const chg = points[i]?.change_pct ?? 0; return (<tr key={i} style={{ borderBottom: '1px solid var(--border-faint)' }}><td className="py-1.5 px-2 whitespace-nowrap">{row.time}</td><td className="text-right py-1.5 px-2 font-mono">{row.price?.toFixed(2) ?? '--'}</td><td className="text-right py-1.5 px-2 font-mono" style={{ color: chg >= 0 ? 'var(--vermillion)' : 'var(--jade)' }}>{chg >= 0 ? '+' : ''}{chg.toFixed(2)}%</td><td className="text-right py-1.5 px-2 font-mono" style={{ color: 'var(--text-muted)' }}>{formatVolume(row.volume)}</td></tr>) })}</tbody>
        </table>
      </div>
    </>
  )
}

/* ── 格式化工具 ── */

function formatMoney(val: number | null): string {
  if (val == null) return '--'
  const abs = Math.abs(val)
  const sign = val >= 0 ? '+' : '-'
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(2)}万`
  return `${sign}${abs.toFixed(0)}`
}

function formatVolume(val: number | null | undefined): string {
  if (val == null) return '--'
  if (val >= 1e8) return `${(val / 1e8).toFixed(2)}亿`
  if (val >= 1e4) return `${(val / 1e4).toFixed(2)}万`
  return val.toLocaleString()
}
