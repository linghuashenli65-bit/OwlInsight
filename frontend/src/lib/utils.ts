import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    if (days === 0) return '今天'
    if (days === 1) return '昨天'
    if (days < 7) return `${days}天前`
    return `${d.getMonth() + 1}/${d.getDate()}`
  } catch {
    return iso
  }
}

export function generateId(): string {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max) + '…' : str
}

/** 从 Markdown 文本中提取纯文本（去除标记符号） */
export function stripMarkdown(md: string): string {
  return md
    .replace(/#{1,6}\s/g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')
    .replace(/>\s/g, '')
    .replace(/[|\\\-]/g, '')
    .trim()
}

/** 为对话生成标题（取第一条消息的前 N 个字） */
export function guessConversationTitle(messages: { content: string }[]): string {
  const first = messages.find(m => m.content.trim())
  if (!first) return '新对话'
  const text = stripMarkdown(first.content)
  return text.length > 30 ? text.slice(0, 30) + '…' : text
}
