'use client'

import { useMemo, useState } from 'react'
import type { ChartData } from '@/lib/types'

interface StockChartProps {
  data: ChartData
  mode?: 'line' | 'candlestick'
}

const MARGIN = { top: 20, right: 20, bottom: 40, left: 60 }
const WIDTH = 600
const HEIGHT = 280
const INNER_W = WIDTH - MARGIN.left - MARGIN.right
const INNER_H = HEIGHT - MARGIN.top - MARGIN.bottom

export function StockChart({ data, mode = 'line' }: StockChartProps) {
  const [tooltip, setTooltip] = useState<{
    x: number
    y: number
    date: string
    open: string
    close: string
    high: string
    low: string
    change: string
  } | null>(null)

  const { points, min, max, gridLines } = useMemo(() => {
    if (mode === 'candlestick') {
      return buildCandlestick(data)
    }
    return buildLine(data)
  }, [data, mode])

  if (points.length < 2) {
    return (
      <div
        className="text-xs py-3 px-4 rounded"
        style={{ color: 'var(--text-muted)', background: 'var(--card)', border: '1px solid var(--border-faint)' }}
      >
        股价数据不足，无法绘制图表
      </div>
    )
  }

  const firstClose = points[0]?.close ?? 0
  const lastClose = points[points.length - 1]?.close ?? 0
  const change = lastClose - firstClose
  const changePct = firstClose ? (change / firstClose) * 100 : 0
  const isUp = change >= 0

  return (
    <div
      className="rounded py-3 px-4 my-2"
      style={{
        background: 'var(--card)',
        border: '1px solid var(--border-faint)',
      }}
    >
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-1">
        <span
          className="text-xs font-medium"
          style={{ color: 'var(--text-sec)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
        >
          {mode === 'candlestick' ? 'K线走势' : '股价走势'}
        </span>
        <span
          className="text-xs font-bold"
          style={{
            color: isUp ? 'var(--vermillion)' : 'var(--jade)',
            fontFamily: 'Georgia, serif',
          }}
        >
          {lastClose.toFixed(2)} ({isUp ? '+' : ''}{change.toFixed(2)}, {isUp ? '+' : ''}{changePct.toFixed(2)}%)
        </span>
      </div>

      {/* SVG 图表 */}
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full"
        style={{ maxHeight: '300px' }}
        onMouseLeave={() => setTooltip(null)}
      >
        {/* 网格线 */}
        {gridLines.map((gl, i) => (
          <g key={i}>
            <line
              x1={MARGIN.left}
              y1={gl.y}
              x2={MARGIN.left + INNER_W}
              y2={gl.y}
              stroke="var(--border-faint)"
              strokeWidth={0.5}
            />
            <text
              x={MARGIN.left - 6}
              y={gl.y + 3}
              textAnchor="end"
              fill="var(--text-muted)"
              fontSize={9}
              fontFamily="Georgia, serif"
            >
              {gl.label}
            </text>
          </g>
        ))}

        {mode === 'candlestick' ? (
          /* K线蜡烛图 */
          <CandlestickLayer points={points as CandlePoint[]} setTooltip={setTooltip} firstClose={firstClose} />
        ) : (
          <>
            {/* 面积填充 */}
            <defs>
              <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={isUp ? '#c41e3a' : '#2d5a4a'} stopOpacity={0.15} />
                <stop offset="100%" stopColor={isUp ? '#c41e3a' : '#2d5a4a'} stopOpacity={0.01} />
              </linearGradient>
            </defs>
            <path
              d={`${buildLinePath(points)} L${points[points.length - 1].x},${MARGIN.top + INNER_H} L${points[0].x},${MARGIN.top + INNER_H} Z`}
              fill="url(#chartGrad)"
            />
            {/* 折线 */}
            <path
              d={buildLinePath(points)}
              fill="none"
              stroke={isUp ? 'var(--vermillion)' : 'var(--jade)'}
              strokeWidth={1.5}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {/* 数据点 + 交互热区 */}
            {points.map((p, i) => (
              <g key={i}>
                <rect
                  x={p.x - 8}
                  y={MARGIN.top}
                  width={16}
                  height={INNER_H}
                  fill="transparent"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={(e) => {
                    const changeFromFirst = ((p.close ?? 0) - firstClose)
                    const changeFromFirstPct = firstClose ? (changeFromFirst / firstClose) * 100 : 0
                    setTooltip({
                      x: p.x,
                      y: p.y,
                      date: p.date,
                      open: (p.open ?? 0).toFixed(2),
                      close: (p.close ?? 0).toFixed(2),
                      high: (p.high ?? 0).toFixed(2),
                      low: (p.low ?? 0).toFixed(2),
                      change: `${changeFromFirst >= 0 ? '+' : ''}${changeFromFirst.toFixed(2)} (${changeFromFirstPct >= 0 ? '+' : ''}${changeFromFirstPct.toFixed(2)}%)`,
                    })
                  }}
                />
                {(i === 0 || i === points.length - 1) && (
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={2.5}
                    fill={isUp ? 'var(--vermillion)' : 'var(--jade)'}
                    stroke="var(--card)"
                    strokeWidth={1}
                  />
                )}
              </g>
            ))}
          </>
        )}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="text-xs rounded px-2 py-1 mt-1 inline-block"
          style={{
            background: 'var(--bg-alt)',
            border: '1px solid var(--border-faint)',
            color: 'var(--text)',
            fontFamily: 'Georgia, "Noto Serif SC", serif',
          }}
        >
          {tooltip.date} — 开 {tooltip.open} 收 {tooltip.close} 高 {tooltip.high} 低 {tooltip.low} ({tooltip.change})
        </div>
      )}

      {/* 日期轴标签 */}
      <div className="flex justify-between text-[0.6rem] mt-0.5" style={{ color: 'var(--text-muted)' }}>
        <span>{data.data[0]?.date || ''}</span>
        <span>{data.data[data.data.length - 1]?.date || ''}</span>
      </div>
    </div>
  )
}

/* ── K线蜡烛图层 ── */

interface CandlePoint {
  x: number
  date: string
  open: number | null
  close: number | null
  high: number | null
  low: number | null
}

function CandlestickLayer({
  points,
  setTooltip,
  firstClose,
}: {
  points: CandlePoint[]
  setTooltip: (t: any) => void
  firstClose: number
}) {
  const bodyWidth = Math.max(Math.min(INNER_W / points.length * 0.6, 8), 2)

  return (
    <>
      {points.map((p, i) => {
        const o = p.open ?? 0
        const c = p.close ?? 0
        const h = p.high ?? Math.max(o, c)
        const l = p.low ?? Math.min(o, c)
        const isBull = c >= o
        const color = isBull ? 'var(--vermillion)' : 'var(--jade)'

        // 计算 Y 坐标 (复用点的 y 作为收盘价位置)
        const pMin = Math.min(...points.map((pt) => Math.min(pt.low ?? Infinity, pt.open ?? Infinity, pt.close ?? Infinity)))
        const pMax = Math.max(...points.map((pt) => Math.max(pt.high ?? -Infinity, pt.open ?? -Infinity, pt.close ?? -Infinity)))
        const range = pMax - pMin || 1
        const pad = range * 0.08
        const toY = (val: number) => MARGIN.top + INNER_H - ((val - (pMin - pad)) / (range + 2 * pad)) * INNER_H

        const bodyTop = toY(Math.max(o, c))
        const bodyBot = toY(Math.min(o, c))
        const bodyH = Math.max(bodyBot - bodyTop, 1)
        const wickTop = toY(h)
        const wickBot = toY(l)

        return (
          <g key={i}>
            {/* 影线 */}
            <line
              x1={p.x}
              y1={wickTop}
              x2={p.x}
              y2={wickBot}
              stroke={color}
              strokeWidth={1}
            />
            {/* 实体 */}
            <rect
              x={p.x - bodyWidth / 2}
              y={bodyTop}
              width={bodyWidth}
              height={bodyH}
              fill={isBull ? color : color}
              stroke={color}
              strokeWidth={0.5}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => {
                const changeFromFirst = ((p.close ?? 0) - firstClose)
                const changeFromFirstPct = firstClose ? (changeFromFirst / firstClose) * 100 : 0
                setTooltip({
                  x: p.x,
                  y: bodyTop,
                  date: p.date,
                  open: o.toFixed(2),
                  close: c.toFixed(2),
                  high: h.toFixed(2),
                  low: l.toFixed(2),
                  change: `${changeFromFirst >= 0 ? '+' : ''}${changeFromFirst.toFixed(2)} (${changeFromFirstPct >= 0 ? '+' : ''}${changeFromFirstPct.toFixed(2)}%)`,
                })
              }}
            />
          </g>
        )
      })}
    </>
  )
}

/* ── 辅助 ── */

interface LinePoint {
  x: number
  y: number
  date: string
  close: number | null
  open: number | null
  high: number | null
  low: number | null
}

function buildLine(data: ChartData) {
  const prices = data.data.map((d) => d.close ?? 0).filter((v) => v > 0)
  if (prices.length === 0) return { points: [] as LinePoint[], min: 0, max: 100, gridLines: [] }

  const mn = Math.min(...prices)
  const mx = Math.max(...prices)
  const range = mx - mn || 1
  const pad = range * 0.08

  const pts: LinePoint[] = data.data.map((d, i) => ({
    x: MARGIN.left + (i / Math.max(data.data.length - 1, 1)) * INNER_W,
    y: MARGIN.top + INNER_H - ((d.close ?? mn) - (mn - pad)) / (range + 2 * pad) * INNER_H,
    date: d.date,
    close: d.close,
    open: d.open,
    high: d.high,
    low: d.low,
  }))

  const step = (mx - mn) / 4
  const gl: { y: number; label: string }[] = []
  for (let i = 0; i <= 4; i++) {
    const val = mn - pad + (range + 2 * pad) * (i / 4)
    gl.push({
      y: MARGIN.top + INNER_H - (i / 4) * INNER_H,
      label: val.toFixed(2),
    })
  }

  return { points: pts, min: mn - pad, max: mx + pad, gridLines: gl }
}

function buildCandlestick(data: ChartData) {
  const allPrices = data.data.flatMap((d) => [d.open, d.close, d.high, d.low]).filter((v): v is number => v != null && v > 0)
  if (allPrices.length === 0) return { points: [] as LinePoint[], min: 0, max: 100, gridLines: [] }

  const mn = Math.min(...allPrices)
  const mx = Math.max(...allPrices)
  const range = mx - mn || 1
  const pad = range * 0.08

  const pts: LinePoint[] = data.data.map((d, i) => ({
    x: MARGIN.left + (i / Math.max(data.data.length - 1, 1)) * INNER_W,
    y: MARGIN.top + INNER_H - ((d.close ?? mn) - (mn - pad)) / (range + 2 * pad) * INNER_H,
    date: d.date,
    close: d.close,
    open: d.open,
    high: d.high,
    low: d.low,
  }))

  const gl: { y: number; label: string }[] = []
  for (let i = 0; i <= 4; i++) {
    const val = mn - pad + (range + 2 * pad) * (i / 4)
    gl.push({
      y: MARGIN.top + INNER_H - (i / 4) * INNER_H,
      label: val.toFixed(2),
    })
  }

  return { points: pts, min: mn - pad, max: mx + pad, gridLines: gl }
}

function buildLinePath(points: { x: number; y: number }[]): string {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
}
