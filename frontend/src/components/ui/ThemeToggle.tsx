'use client'

import { Moon, Sun } from 'lucide-react'
import { useSettingsStore } from '@/store/settingsStore'

export function ThemeToggle() {
  const theme = useSettingsStore((s) => s.theme)
  const toggleTheme = useSettingsStore((s) => s.toggleTheme)

  return (
    <button
      onClick={toggleTheme}
      className="flex items-center gap-2 w-full px-3 py-2 text-xs transition-colors rounded"
      style={{ color: 'var(--text-sec)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--card-hover)'
        e.currentTarget.style.color = 'var(--text)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'var(--text-sec)'
      }}
    >
      {theme === 'dark' ? <Sun size={12} /> : <Moon size={12} />}
      <span>{theme === 'dark' ? '浅色模式' : '暗色模式'}</span>
    </button>
  )
}
