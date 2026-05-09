/* 设置状态管理 — 主题 */

import { create } from 'zustand'
import type { SettingsState, ThemeMode } from '@/lib/types'

/** 从 localStorage 读取主题（仅在浏览器端调用） */
function loadThemeFromStorage(): ThemeMode {
  const stored = localStorage.getItem('financebot-theme')
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

/** 主题持久化 key */
const STORAGE_KEY = 'financebot-theme'

export const useSettingsStore = create<SettingsState>((set) => ({
  theme: 'dark', // SSR 与服务端一致，客户端 hydrate 后用 useEffect 修正

  toggleTheme: () =>
    set((s) => {
      const next = s.theme === 'dark' ? 'light' : 'dark'
      localStorage.setItem(STORAGE_KEY, next)
      return { theme: next }
    }),

  setTheme: (t: ThemeMode) => {
    localStorage.setItem(STORAGE_KEY, t)
    set({ theme: t })
  },

  /** 初始化：从 localStorage 加载主题并应用到 DOM */
  hydrate: () => {
    const saved = loadThemeFromStorage()
    localStorage.setItem(STORAGE_KEY, saved)
    document.documentElement.classList.remove('dark', 'light')
    document.documentElement.classList.add(saved)
    set({ theme: saved })
  },
}))
