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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className="mx-4 w-full max-w-lg rounded-3xl bg-white shadow-lg">
        <div className="border-b border-apple-separator px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-[19px] font-semibold text-gray-900">{title}</h2>
            <button
              onClick={onClose}
              className="text-[24px] leading-none text-apple-gray hover:text-gray-900"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="px-6 py-5 overflow-y-auto max-h-[calc(100vh-8rem)]">{children}</div>
      </div>
    </div>
  )
}
