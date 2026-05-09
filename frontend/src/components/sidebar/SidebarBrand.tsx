'use client'

export function SidebarBrand() {
  return (
    <div
      className="flex items-center gap-3 px-3 pb-4 mb-3"
      style={{ borderBottom: '1px solid rgba(201,169,110,0.13)' }}
    >
      <div
        className="w-9 h-9 flex items-center justify-center flex-shrink-0"
        style={{ borderRadius: '2px', overflow: 'hidden' }}
      >
        <img src="/logo.png" alt="枭研" className="w-full h-full object-cover" />
      </div>
      <div className="min-w-0">
        <div className="text-sm font-bold truncate" style={{ color: 'var(--text)' }}>
          枭研
        </div>
        <div className="text-[0.6rem] tracking-widest uppercase" style={{ color: 'var(--text-muted)' }}>
          OwlInsight
        </div>
      </div>
    </div>
  )
}
