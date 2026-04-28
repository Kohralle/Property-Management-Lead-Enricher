import { useEffect, useRef } from 'react'

interface ModalProps {
  title: string
  onClose: () => void
  children: React.ReactNode
}

export default function Modal({ title, onClose, children }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-[#2d2115]/35 p-4 backdrop-blur-md"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className="my-auto flex max-h-[calc(100vh-2rem)] w-full max-w-lg flex-col overflow-hidden rounded-[28px] border border-luxe-line bg-luxe-panel shadow-[0_28px_70px_rgba(72,49,26,0.18)]">
        <div className="flex items-center justify-between border-b border-luxe-line px-6 pb-4 pt-6">
          <h2 className="font-display text-[22px] font-semibold tracking-tight text-luxe-ink">{title}</h2>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-luxe-soft text-luxe-muted transition-colors hover:bg-luxe-accentSoft hover:text-luxe-ink"
          >
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
              <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  )
}
