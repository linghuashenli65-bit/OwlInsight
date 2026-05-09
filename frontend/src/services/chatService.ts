/* 对话流式服务 — 基于 fetch + ReadableStream 实现 SSE */

import type { Citation, Anomaly, StepEvent, ChatMessage, ChartData, SavePrompt } from '@/lib/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8897'

export interface StreamCallbacks {
  onStep?: (step: StepEvent) => void
  onToken?: (token: string) => void
  onCitation?: (citation: Citation) => void
  onAnomaly?: (anomaly: Anomaly) => void
  onStatus?: (status: string) => void
  onChart?: (chart: ChartData) => void
  onSavePrompt?: (prompt: SavePrompt) => void
  onDone?: (messageId: string) => void
  onError?: (error: Error) => void
}

export async function streamChat(
  message: string,
  threadId: string,
  history: Pick<ChatMessage, 'role' | 'content'>[],
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId, history }),
    signal,
  })

  if (!response.ok) {
    callbacks.onError?.(new Error(`HTTP ${response.status}: ${response.statusText}`))
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    callbacks.onError?.(new Error('No response body'))
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // 解析 SSE 事件（可能跨 chunk）
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''  // 未完成的行留到下一次

      let currentEvent = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          const data = line.slice(6)
          try {
            const parsed = JSON.parse(data)
            dispatchEvent(currentEvent, parsed, callbacks)
          } catch {
            // 跳过无法解析的行
          }
        }
      }
    }
  } catch (err) {
    if ((err as Error).name === 'AbortError') {
      callbacks.onDone?.('aborted')
    } else {
      callbacks.onError?.(err as Error)
    }
  }
}

function dispatchEvent(event: string, data: unknown, cb: StreamCallbacks): void {
  switch (event) {
    case 'step':
      cb.onStep?.(data as StepEvent)
      break
    case 'token':
      cb.onToken?.((data as { content: string }).content)
      break
    case 'citation':
      cb.onCitation?.(data as Citation)
      break
    case 'anomaly':
      cb.onAnomaly?.(data as Anomaly)
      break
    case 'status':
      cb.onStatus?.((data as { message: string }).message)
      break
    case 'chart':
      cb.onChart?.(data as ChartData)
      break
    case 'save_prompt':
      cb.onSavePrompt?.(data as SavePrompt)
      break
    case 'done':
      cb.onDone?.((data as { message_id: string }).message_id)
      break
    case 'error':
      cb.onError?.(new Error((data as { error: string }).error))
      break
  }
}
