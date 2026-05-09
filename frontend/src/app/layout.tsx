'use client'

import { useEffect } from 'react'
import { Toaster } from 'react-hot-toast'
import { useSettingsStore } from '@/store/settingsStore'
import './globals.css'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const theme = useSettingsStore((s) => s.theme)
  const hydrate = useSettingsStore((s) => s.hydrate)

  // 客户端 hydrate 后从 localStorage 加载真实主题
  useEffect(() => {
    hydrate()
  }, [])

  // 主题切换时更新 DOM class
  useEffect(() => {
    document.documentElement.classList.remove('dark', 'light')
    document.documentElement.classList.add(theme)
  }, [theme])

  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <title>枭研 — OwlInsight</title>
        <link rel="icon" href="/logo.png" type="image/png" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <meta name="description" content="OwlInsight — 有来源、可追溯、懂你的投资研究" />
      </head>
      <body>
        {children}
        <Toaster
          position="top-center"
          toastOptions={{
            duration: 3000,
            style: {
              background: 'var(--card)',
              color: 'var(--text)',
              border: '1px solid var(--border-faint)',
              borderRadius: '2px',
              fontFamily: 'Georgia, "Noto Serif SC", serif',
              fontSize: '0.85rem',
            },
          }}
        />
      </body>
    </html>
  )
}
