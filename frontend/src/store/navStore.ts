/* 导航状态管理 — 多视图切换 */

import { create } from 'zustand'
import type { AppView } from '@/lib/types'

interface NavState {
  currentView: AppView
  navigate: (view: AppView) => void
}

export const useNavStore = create<NavState>((set) => ({
  currentView: 'chat',
  navigate: (view) => set({ currentView: view }),
}))
