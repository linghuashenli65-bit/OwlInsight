/* 对话状态管理 — Zustand + 后端持久化 */

import { create } from 'zustand'
import type { ChatMessage, Conversation, Citation, Anomaly, ChartData, ConversationSummary } from '@/lib/types'
import { generateId, guessConversationTitle } from '@/lib/utils'
import { streamChat } from '@/services/chatService'
import { api } from '@/lib/api'
import type { ChatState } from '@/lib/types'

function createNewConversationObj(id?: string, title?: string): Conversation {
  const now = new Date().toISOString()
  return {
    id: id || generateId(),
    title: title || '新对话',
    messages: [],
    created_at: now,
    updated_at: now,
    isLoading: false,
  }
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversationId: null,
  isLoading: false,

  streamingContent: '',
  streamingReasoning: [],
  streamingCitations: [],
  streamingAnomalies: [],
  streamingStatus: [],
  streamingChartData: null,
  pendingSavePrompt: null,

  conversationList: [],
  isFetchingList: false,

  /* ── 从后端加载对话列表 ── */
  fetchConversationList: async () => {
    set({ isFetchingList: true })
    try {
      const res = await api.conversations.list()
      set({ conversationList: res.conversations || [] })
    } catch {
      // 静默
    } finally {
      set({ isFetchingList: false })
    }
  },

  /* ── 切换到已有对话（从后端加载消息） ── */
  switchConversation: async (id: string) => {
    const existing = get().conversations.find((c) => c.id === id)
    if (existing) {
      set({ currentConversationId: id })
      return
    }
    try {
      const res = await api.conversations.get(id)
      const conv: Conversation = {
        id: res.conversation.id,
        title: res.conversation.title,
        messages: (res.messages || []).map((m: any) => ({
          id: `msg-${m.id}`,
          role: m.role,
          content: m.content || '',
          reasoning: m.reasoning || [],
          citations: m.citations || [],
          anomalies: m.anomalies || [],
          chartData: m.chart_data ? JSON.parse(m.chart_data) : undefined,
          timestamp: m.created_at,
        })),
        created_at: res.conversation.created_at,
        updated_at: res.conversation.updated_at,
      }
      set((s) => ({
        conversations: [conv, ...s.conversations.filter((c) => c.id !== id)],
        currentConversationId: id,
        streamingContent: '',
        streamingReasoning: [],
        streamingCitations: [],
        streamingAnomalies: [],
        streamingStatus: [],
        streamingChartData: null,
      }))
    } catch {
      // fallback: 本地创建
      set({ currentConversationId: id })
    }
  },

  /* ── 新建对话 ── */
  createNewConversation: () => {
    const conv = createNewConversationObj()
    set((s) => ({
      conversations: [conv, ...s.conversations],
      currentConversationId: conv.id,
      streamingContent: '',
      streamingReasoning: [],
      streamingCitations: [],
      streamingAnomalies: [],
      streamingStatus: [],
      streamingChartData: null,
    }))
    // 在后端创建
    api.conversations.create('新对话').then((res) => {
      if (res.conversation?.id) {
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === conv.id ? { ...c, id: res.conversation.id } : c,
          ),
          currentConversationId:
            s.currentConversationId === conv.id ? res.conversation.id : s.currentConversationId,
          conversationList: [
            { id: res.conversation.id, title: '新对话', created_at: '', updated_at: '', message_count: 0 },
            ...s.conversationList.filter((cl) => cl.id !== res.conversation.id),
          ],
        }))
      }
    }).catch(() => {})
  },

  setCurrentConversation: (id: string) => {
    set({ currentConversationId: id })
  },

  /* ── 删除对话 ── */
  deleteConversation: async (id: string) => {
    try {
      await api.conversations.delete(id)
    } catch { /* ok */ }
    set((s) => {
      const filtered = s.conversations.filter((c) => c.id !== id)
      return {
        conversations: filtered,
        currentConversationId:
          s.currentConversationId === id
            ? filtered[0]?.id ?? null
            : s.currentConversationId,
        conversationList: s.conversationList.filter((cl) => cl.id !== id),
      }
    })
  },

  /* ── 重命名 ── */
  renameConversation: (id: string, title: string) => {
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === id ? { ...c, title } : c,
      ),
      conversationList: s.conversationList.map((cl) =>
        cl.id === id ? { ...cl, title } : cl,
      ),
    }))
    api.conversations.update(id, title).catch(() => {})
  },

  /* ── 停止生成 ── */
  stopGeneration: () => {
    set({ isLoading: false })
  },

  /* ── 发送消息 ── */
  sendMessage: async (content: string) => {
    const state = get()
    let convId = state.currentConversationId
    let conv = state.conversations.find((c) => c.id === convId)

    if (!conv) {
      const newConv = createNewConversationObj()
      set((s) => ({
        conversations: [newConv, ...s.conversations],
        currentConversationId: newConv.id,
      }))
      convId = newConv.id
      conv = newConv
      // 在后端创建
      api.conversations.create().then((res) => {
        if (res.conversation?.id) {
          set((s) => ({
            conversations: s.conversations.map((c) =>
              c.id === newConv.id ? { ...c, id: res.conversation.id } : c,
            ),
            currentConversationId: s.currentConversationId === newConv.id ? res.conversation.id : s.currentConversationId,
            conversationList: [
              { id: res.conversation.id, title: '新对话', created_at: '', updated_at: '', message_count: 0 },
              ...s.conversationList.filter((cl) => cl.id !== res.conversation.id),
            ],
          }))
          convId = res.conversation.id
        }
      }).catch(() => {})
    }

    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }

    const assistantMsg: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      reasoning: [],
      citations: [],
      anomalies: [],
      dataStatus: [],
      timestamp: new Date().toISOString(),
    }

    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === convId
          ? { ...c, messages: [...c.messages, userMsg, assistantMsg], isLoading: true }
          : c,
      ),
      isLoading: true,
      streamingContent: '',
      streamingReasoning: [],
      streamingCitations: [],
      streamingAnomalies: [],
      streamingStatus: [],
      streamingChartData: null,
    }))

    const allMessages = conv?.messages || []
    const history = allMessages.map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
    }))

    const abortController = new AbortController()

    try {
      await streamChat(
        content,
        convId!,
        history,
        {
          onStep: (step) => {
            set((s) => ({
              streamingReasoning: [...s.streamingReasoning, step.detail],
            }))
          },
          onToken: (token) => {
            set((s) => ({
              streamingContent: s.streamingContent + token,
            }))
          },
          onCitation: (citation) => {
            set((s) => ({
              streamingCitations: [...s.streamingCitations, citation],
            }))
          },
          onAnomaly: (anomaly) => {
            set((s) => ({
              streamingAnomalies: [...s.streamingAnomalies, anomaly],
            }))
          },
          onStatus: (status) => {
            set((s) => ({
              streamingStatus: [...s.streamingStatus, status],
            }))
          },
          onChart: (chart) => {
            set({ streamingChartData: chart })
          },
          onSavePrompt: (prompt) => {
            set({ pendingSavePrompt: prompt })
          },
          onDone: async () => {
            const s = get()
            const finalContent = s.streamingContent
            const finalChart = s.streamingChartData
            const finalSavePrompt = s.pendingSavePrompt

            const title =
              conv && conv.title === '新对话'
                ? guessConversationTitle([userMsg])
                : undefined

            set((state) => ({
              isLoading: false,
              conversations: state.conversations.map((c) =>
                c.id === convId
                  ? {
                      ...c,
                      title: title || c.title,
                      messages: c.messages.map((m) =>
                        m.id === assistantMsg.id
                          ? {
                              ...m,
                              content: finalContent,
                              reasoning: s.streamingReasoning,
                              citations: s.streamingCitations,
                              anomalies: s.streamingAnomalies,
                              dataStatus: s.streamingStatus,
                              chartData: finalChart || undefined,
                              savePrompt: finalSavePrompt || undefined,
                            }
                          : m,
                      ),
                      isLoading: false,
                    }
                  : c,
              ),
              streamingChartData: null,
              pendingSavePrompt: null,
            }))

            // ── 持久化到后端（串行，避免 SQLite 并发问题）──
            const currentConvId = get().currentConversationId
            if (currentConvId) {
              try {
                await api.conversations.addMessage(currentConvId, {
                  role: 'user',
                  content,
                })
                await api.conversations.addMessage(currentConvId, {
                  role: 'assistant',
                  content: finalContent,
                  reasoning: s.streamingReasoning,
                  citations: s.streamingCitations,
                  anomalies: s.streamingAnomalies,
                  chart_data: finalChart ? JSON.stringify(finalChart) : null,
                })
              } catch (e) {
                console.warn('保存消息失败:', e)
              }
              // 自动生成标题（只有一轮对话时）
              if (title) {
                api.conversations.generateTitle(currentConvId).then((res) => {
                  set((state) => ({
                    conversations: state.conversations.map((c) =>
                      c.id === currentConvId ? { ...c, title: res.title } : c,
                    ),
                    conversationList: state.conversationList.map((cl) =>
                      cl.id === currentConvId ? { ...cl, title: res.title } : cl,
                    ),
                  }))
                }).catch(() => {})
              }
              // 刷新列表
              get().fetchConversationList()
            }
          },
          onError: (err) => {
            set((state) => ({
              isLoading: false,
              conversations: state.conversations.map((c) =>
                c.id === convId
                  ? {
                      ...c,
                      messages: c.messages.map((m) =>
                        m.id === assistantMsg.id
                          ? { ...m, content: `请求失败: ${err.message}` }
                          : m,
                      ),
                      isLoading: false,
                    }
                  : c,
              ),
            }))
          },
        },
        abortController.signal,
      )
    } catch {
      // AbortError handled in streamChat
    }
  },

  /* ── 导出 Markdown ── */
  exportToMarkdown: (conversationId: string): string => {
    const conv = get().conversations.find((c) => c.id === conversationId)
    if (!conv) return ''

    const parts = [
      `# 枭研 分析报告`,
      `*${new Date().toLocaleString('zh-CN')}*\n`,
    ]

    for (const msg of conv.messages) {
      if (msg.role === 'user') {
        parts.push(`## 用户\n${msg.content}\n`)
      } else {
        if (msg.reasoning?.length) {
          parts.push('## 分析过程')
          parts.push(msg.reasoning.map((s) => `- ${s}`).join('\n'))
          parts.push('')
        }
        parts.push(`## 分析结果\n${msg.content}\n`)
        if (msg.citations?.length) {
          parts.push('## 引用来源')
          parts.push(msg.citations.map((c) => `[${c.index}] ${c.detail}`).join('\n'))
          parts.push('')
        }
      }
    }

    return parts.join('\n')
  },
}))
