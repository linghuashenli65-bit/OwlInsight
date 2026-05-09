'use client'

import { useEffect, useState } from 'react'
import { ChatSidebar } from '@/components/chat/ChatSidebar'
import { AlertPanel } from '@/components/alerter/AlertPanel'
import { ChatMain } from '@/components/chat/ChatMain'
import { DashboardPage } from '@/components/pages/DashboardPage'
import { SettingsPage } from '@/components/pages/SettingsPage'
import { CompaniesPage } from '@/components/pages/CompaniesPage'
import { NotesPage } from '@/components/pages/NotesPage'
import { DocumentsPage } from '@/components/pages/DocumentsPage'
import { useChatStore } from '@/store/chatStore'
import { useSidebarStore } from '@/store/sidebarStore'
import { useNavStore } from '@/store/navStore'

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const createNewConversation = useChatStore((s) => s.createNewConversation)
  const currentConversationId = useChatStore((s) => s.currentConversationId)
  const fetchCompanies = useSidebarStore((s) => s.fetchCompanies)
  const fetchNotes = useSidebarStore((s) => s.fetchNotes)
  const currentView = useNavStore((s) => s.currentView)
  const navigate = useNavStore((s) => s.navigate)
  const fetchConversationList = useChatStore((s) => s.fetchConversationList)

  useEffect(() => {
    navigate('dashboard')
    fetchConversationList()
    fetchCompanies()
    fetchNotes()
  }, [])

  const renderMain = () => {
    switch (currentView) {
      case 'dashboard':
        return <DashboardPage />
      case 'settings':
        return <SettingsPage />
      case 'companies':
        return <CompaniesPage />
      case 'notes':
        return <NotesPage />
      case 'documents':
        return <DocumentsPage />
      case 'chat':
      default:
        return (
          <ChatMain
            key={currentConversationId}
            onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          />
        )
    }
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* 侧边栏 */}
      <ChatSidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onClose={() => setSidebarOpen(false)}
      />

      {/* 告警面板 — 固定在根层级，不受 sidebar translate-x 影响 */}
      <AlertPanel />

      {/* 主区域 */}
      <main className="flex-1 flex flex-col relative z-10 min-w-0">
        {renderMain()}
      </main>
    </div>
  )
}
