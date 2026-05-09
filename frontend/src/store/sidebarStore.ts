/* 侧边栏状态管理 — 关注公司 / 研究笔记 */

import { create } from 'zustand'
import type { SidebarState } from '@/lib/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8897'

export const useSidebarStore = create<SidebarState>((set) => ({
  watchedCompanies: [],
  researchNotes: [],
  isLoading: false,

  fetchCompanies: async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/data/companies`)
      const data = await res.json()
      set({ watchedCompanies: data.companies || [] })
    } catch {
      // 静默失败，保留空数组
    }
  },

  fetchNotes: async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/data/notes`)
      const data = await res.json()
      set({ researchNotes: data.notes || [] })
    } catch {
      // 静默失败
    }
  },
}))
