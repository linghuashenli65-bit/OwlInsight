'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { PageHeader } from '@/components/ui/PageHeader'
import { api } from '@/lib/api'
import type { AppSettings, AlertConfig } from '@/lib/types'

const DEFAULT_SETTINGS: AppSettings = {
  theme: 'dark',
  language: 'zh',
  llm_provider: 'openai',
  llm_model: 'gpt-4o',
  temperature: 0.1,
}

interface EmailPrefs {
  alert_email_enabled: string
  alert_email_smtp_host: string
  alert_email_smtp_port: string
  alert_email_user: string
  alert_email_password: string
  alert_email_from: string
  alert_email_to: string
  alert_email_premarket_time: string
  alert_email_postmarket_time: string
}

const DEFAULT_EMAIL: EmailPrefs = {
  alert_email_enabled: 'false',
  alert_email_smtp_host: '',
  alert_email_smtp_port: '587',
  alert_email_user: '',
  alert_email_password: '',
  alert_email_from: '',
  alert_email_to: '',
  alert_email_premarket_time: '08:30',
  alert_email_postmarket_time: '15:30',
}

export function SettingsPage() {
  const [form, setForm] = useState<AppSettings>(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(false)

  // Email 配置
  const [emailPrefs, setEmailPrefs] = useState<EmailPrefs>(DEFAULT_EMAIL)
  const [showEmailPwd, setShowEmailPwd] = useState(false)

  // 告警阈值配置
  const [alertConfigs, setAlertConfigs] = useState<AlertConfig[]>([])
  const [activeTab, setActiveTab] = useState<'general' | 'email' | 'thresholds'>('general')

  useEffect(() => {
    // 页面直接渲染，后台加载数据填充
    const timeout = (ms: number) => new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), ms))

    const loadSettings = async () => {
      // 通用设置（MySQL，加 3s 超时避免卡死）
      try {
        const settingsData = await Promise.race([
          api.settings.get(),
          timeout(3000),
        ]) as Record<string, string | number>
        if (settingsData && Object.keys(settingsData).length > 0) {
          setForm({
            theme: (settingsData.theme as string) || DEFAULT_SETTINGS.theme,
            language: (settingsData.language as string) || DEFAULT_SETTINGS.language,
            llm_provider: (settingsData.llm_provider as string) || DEFAULT_SETTINGS.llm_provider,
            llm_model: (settingsData.llm_model as string) || DEFAULT_SETTINGS.llm_model,
            temperature: Number(settingsData.temperature) || DEFAULT_SETTINGS.temperature,
          })
        }
      } catch { /* MySQL 不可用时保持默认值 */ }

      // SQLite 请求（并发）
      await Promise.allSettled([
        (async () => {
          try {
            const prefData = await api.alerts.getPreferences()
            const prefs: Record<string, string> = prefData.preferences || {}
            setEmailPrefs({
              alert_email_enabled: prefs.alert_email_enabled || 'false',
              alert_email_smtp_host: prefs.alert_email_smtp_host || '',
              alert_email_smtp_port: prefs.alert_email_smtp_port || '587',
              alert_email_user: prefs.alert_email_user || '',
              alert_email_password: prefs.alert_email_password || '',
              alert_email_from: prefs.alert_email_from || '',
              alert_email_to: prefs.alert_email_to || '',
              alert_email_premarket_time: prefs.alert_email_premarket_time || '08:30',
              alert_email_postmarket_time: prefs.alert_email_postmarket_time || '15:30',
            })
          } catch { /* ignore */ }
        })(),
        (async () => {
          try {
            const configData = await api.alerts.getConfig()
            setAlertConfigs((configData.configs || []) as AlertConfig[])
          } catch { /* ignore */ }
        })(),
      ])

      setLoading(false)
    }

    loadSettings()
  }, [])

  const handleSaveGeneral = async () => {
    try {
      await api.settings.save(form as unknown as Record<string, string | number>)
      toast.success('设置已保存')
    } catch {
      toast.error('保存失败，请检查后端服务')
    }
  }

  const handleSaveEmail = async () => {
    try {
      await api.alerts.savePreferences(emailPrefs as unknown as Record<string, string>)
      toast.success('邮件配置已保存')
    } catch {
      toast.error('保存失败')
    }
  }

  const handleSaveThresholds = async () => {
    try {
      await api.alerts.saveConfig(alertConfigs)
      toast.success('阈值配置已保存')
    } catch {
      toast.error('保存失败')
    }
  }

  const updateAlertConfig = (code: string, field: string, value: number | boolean) => {
    setAlertConfigs((prev) =>
      prev.map((c) => (c.company_code === code ? { ...c, [field]: value } : c)),
    )
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 12px',
    fontSize: '0.8rem',
    background: 'var(--bg)',
    color: 'var(--text)',
    border: '1px solid var(--border-faint)',
    borderRadius: '2px',
    outline: 'none',
    fontFamily: 'Georgia, "Noto Serif SC", serif',
  }

  const labelStyle: React.CSSProperties = {
    fontSize: '0.75rem',
    color: 'var(--text-sec)',
    marginBottom: '4px',
    fontFamily: 'Georgia, "Noto Serif SC", serif',
  }

  const tabStyle = (tab: string): React.CSSProperties => ({
    padding: '6px 16px',
    fontSize: '0.75rem',
    cursor: 'pointer',
    border: 'none',
    background: activeTab === tab ? 'var(--card-hover)' : 'transparent',
    color: activeTab === tab ? 'var(--gold)' : 'var(--text-sec)',
    borderBottom: activeTab === tab ? '2px solid var(--gold)' : '2px solid transparent',
    fontFamily: 'Georgia, "Noto Serif SC", serif',
    transition: 'all 0.2s',
  })

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <PageHeader title="设置" description="管理应用偏好与告警配置" />

      {/* 标签页 */}
      <div className="flex gap-1 mb-6" style={{ borderBottom: '1px solid var(--border-faint)' }}>
        <button style={tabStyle('general')} onClick={() => setActiveTab('general')}>通用</button>
        <button style={tabStyle('email')} onClick={() => setActiveTab('email')}>邮件告警</button>
        <button style={tabStyle('thresholds')} onClick={() => setActiveTab('thresholds')}>阈值配置</button>
      </div>

      {/* ════════ 通用设置 ════════ */}
      {activeTab === 'general' && (
        <div className="max-w-lg space-y-5">
          <div>
            <div style={labelStyle}>语言 / Language</div>
            <select
              value={form.language}
              onChange={(e) => setForm({ ...form, language: e.target.value })}
              style={inputStyle}
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </div>

          <div>
            <div style={labelStyle}>LLM 提供商</div>
            <input
              value={form.llm_provider}
              onChange={(e) => setForm({ ...form, llm_provider: e.target.value })}
              style={inputStyle}
              placeholder="openai / anthropic / custom"
            />
          </div>

          <div>
            <div style={labelStyle}>模型名称</div>
            <input
              value={form.llm_model}
              onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
              style={inputStyle}
              placeholder="gpt-4o / claude-sonnet-4-6"
            />
          </div>

          <div>
            <div style={labelStyle}>Temperature ({form.temperature.toFixed(1)})</div>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={form.temperature}
              onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
              style={{ width: '100%', accentColor: 'var(--gold)' }}
            />
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.6rem',
                color: 'var(--text-muted)',
              }}
            >
              <span>精确 (0)</span>
              <span>创意 (2)</span>
            </div>
          </div>

          <button onClick={handleSaveGeneral} className="btn-gold">
            保存设置
          </button>
        </div>
      )}

      {/* ════════ 邮件告警配置 ════════ */}
      {activeTab === 'email' && (
        <div className="max-w-lg space-y-5">
          <div>
            <div style={labelStyle}>开启邮件推送</div>
            <label className="flex items-center gap-2" style={{ cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={emailPrefs.alert_email_enabled === 'true'}
                onChange={(e) =>
                  setEmailPrefs({ ...emailPrefs, alert_email_enabled: e.target.checked ? 'true' : 'false' })
                }
                style={{ accentColor: 'var(--gold)' }}
              />
              <span style={{ fontSize: '0.8rem', color: 'var(--text-sec)' }}>启用 SMTP 邮件发送</span>
            </label>
          </div>

          <div>
            <div style={labelStyle}>SMTP 服务器</div>
            <input
              value={emailPrefs.alert_email_smtp_host}
              onChange={(e) => setEmailPrefs({ ...emailPrefs, alert_email_smtp_host: e.target.value })}
              style={inputStyle}
              placeholder="smtp.qq.com"
            />
          </div>

          <div>
            <div style={labelStyle}>SMTP 端口</div>
            <input
              value={emailPrefs.alert_email_smtp_port}
              onChange={(e) => setEmailPrefs({ ...emailPrefs, alert_email_smtp_port: e.target.value })}
              style={inputStyle}
              placeholder="587"
            />
          </div>

          <div>
            <div style={labelStyle}>邮箱账号</div>
            <input
              value={emailPrefs.alert_email_user}
              onChange={(e) => setEmailPrefs({ ...emailPrefs, alert_email_user: e.target.value })}
              style={inputStyle}
              placeholder="your@email.com"
            />
          </div>

          <div>
            <div style={labelStyle}>邮箱密码 / 授权码</div>
            <div className="flex gap-2">
              <input
                type={showEmailPwd ? 'text' : 'password'}
                value={emailPrefs.alert_email_password}
                onChange={(e) => setEmailPrefs({ ...emailPrefs, alert_email_password: e.target.value })}
                style={inputStyle}
                placeholder="授权码"
              />
              <button
                onClick={() => setShowEmailPwd(!showEmailPwd)}
                className="px-2 text-xs rounded"
                style={{
                  background: 'var(--card-hover)',
                  color: 'var(--text-sec)',
                  border: '1px solid var(--border-faint)',
                  cursor: 'pointer',
                }}
              >
                {showEmailPwd ? '隐藏' : '显示'}
              </button>
            </div>
          </div>

          <div>
            <div style={labelStyle}>发件人地址</div>
            <input
              value={emailPrefs.alert_email_from}
              onChange={(e) => setEmailPrefs({ ...emailPrefs, alert_email_from: e.target.value })}
              style={inputStyle}
              placeholder="your@email.com（留空使用账号）"
            />
          </div>

          <div>
            <div style={labelStyle}>收件人地址</div>
            <input
              value={emailPrefs.alert_email_to}
              onChange={(e) => setEmailPrefs({ ...emailPrefs, alert_email_to: e.target.value })}
              style={inputStyle}
              placeholder="your@email.com（留空使用账号）"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div style={labelStyle}>盘前推送时间</div>
              <input
                type="time"
                value={emailPrefs.alert_email_premarket_time}
                onChange={(e) => setEmailPrefs({ ...emailPrefs, alert_email_premarket_time: e.target.value })}
                style={inputStyle}
              />
            </div>
            <div>
              <div style={labelStyle}>盘后推送时间</div>
              <input
                type="time"
                value={emailPrefs.alert_email_postmarket_time}
                onChange={(e) => setEmailPrefs({ ...emailPrefs, alert_email_postmarket_time: e.target.value })}
                style={inputStyle}
              />
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={handleSaveEmail} className="btn-gold">
              保存邮件配置
            </button>
            <button
              onClick={async () => {
                const toast = (await import('react-hot-toast')).default
                try {
                  toast.loading('正在发送测试邮件...', { id: 'test-email' })
                  const res = await api.alerts.triggerJob('pre_market')
                  toast.success(res.message || '测试邮件已触发', { id: 'test-email' })
                } catch (e: any) {
                  toast.error('触发失败: ' + (e.message || ''), { id: 'test-email' })
                }
              }}
              className="btn-ghost"
            >
              测试发送盘前邮件
            </button>
          </div>
        </div>
      )}

      {/* ════════ 告警阈值配置 ════════ */}
      {activeTab === 'thresholds' && (
        <div className="max-w-2xl space-y-4">
          {alertConfigs.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              暂无关注公司，请先在对话中添加关注公司。
            </p>
          ) : (
            alertConfigs.map((cfg) => (
              <div
                key={cfg.company_code}
                className="p-4 rounded"
                style={{ background: 'var(--card)', border: '1px solid var(--border-faint)' }}
              >
                <div
                  className="text-xs font-medium mb-3"
                  style={{ color: 'var(--text)', fontFamily: 'Georgia, "Noto Serif SC", serif' }}
                >
                  {cfg.company_name || cfg.company_code}
                  <span className="ml-2" style={{ color: 'var(--text-muted)' }}>{cfg.company_code}</span>
                </div>

                <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                  <div>
                    <div style={labelStyle}>涨幅阈值 (%)</div>
                    <input
                      type="number"
                      step="0.5"
                      min="0"
                      value={cfg.price_up_pct}
                      onChange={(e) => updateAlertConfig(cfg.company_code, 'price_up_pct', parseFloat(e.target.value) || 0)}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <div style={labelStyle}>跌幅阈值 (%)</div>
                    <input
                      type="number"
                      step="0.5"
                      max="0"
                      value={cfg.price_down_pct}
                      onChange={(e) => updateAlertConfig(cfg.company_code, 'price_down_pct', parseFloat(e.target.value) || 0)}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <div style={labelStyle}>资金流阈值 (元)</div>
                    <input
                      type="number"
                      step="10000000"
                      value={cfg.fund_flow_threshold}
                      onChange={(e) => updateAlertConfig(cfg.company_code, 'fund_flow_threshold', parseFloat(e.target.value) || 0)}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <div style={labelStyle}>盘中检测</div>
                    <label className="flex items-center gap-2" style={{ cursor: 'pointer', marginTop: '4px' }}>
                      <input
                        type="checkbox"
                        checked={cfg.intraday_enabled === 1}
                        onChange={(e) => updateAlertConfig(cfg.company_code, 'intraday_enabled', e.target.checked ? 1 : 0)}
                        style={{ accentColor: 'var(--gold)' }}
                      />
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-sec)' }}>启用</span>
                    </label>
                  </div>
                </div>
              </div>
            ))
          )}

          {alertConfigs.length > 0 && (
            <button onClick={handleSaveThresholds} className="btn-gold">
              保存阈值配置
            </button>
          )}
        </div>
      )}

      <style>{`
        .btn-gold {
          padding: 8px 24px;
          font-size: 0.8rem;
          background: var(--gold);
          color: #fff;
          border: none;
          border-radius: 2px;
          cursor: pointer;
          font-family: Georgia, "Noto Serif SC", serif;
          transition: opacity 0.2s;
        }
        .btn-gold:hover { opacity: 0.9; }
        .btn-ghost {
          padding: 8px 24px;
          font-size: 0.8rem;
          background: transparent;
          color: var(--text-sec);
          border: 1px solid var(--border-faint);
          border-radius: 2px;
          cursor: pointer;
          font-family: Georgia, "Noto Serif SC", serif;
          transition: all 0.2s;
        }
        .btn-ghost:hover {
          border-color: var(--gold);
          color: var(--gold);
        }
      `}</style>
    </div>
  )
}
