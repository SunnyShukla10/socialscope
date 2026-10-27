'use client'

import React, { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'
import { X } from 'lucide-react'

interface DialogProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
  children: React.ReactNode
  className?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
}

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
  size = 'md',
}: DialogProps) {
  const panel = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  const titleId = useId()
  useEffect(() => { close.current = onClose }, [onClose])
  useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const controls = () => Array.from(panel.current?.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]'
    ) || [])
    const preferred = panel.current?.querySelector<HTMLElement>('[data-dialog-autofocus]')
    ;(preferred || controls()[0] || panel.current)?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); close.current(); return }
      if (event.key !== 'Tab') return
      const items = controls(), first = items[0], last = items[items.length - 1]
      if (!first) { event.preventDefault(); panel.current?.focus(); return }
      if (!panel.current?.contains(document.activeElement) || document.activeElement === panel.current) {
        event.preventDefault(); (event.shiftKey ? last : first).focus()
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [open])

  if (!open || typeof document === 'undefined') return null

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Panel */}
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-label={title ? undefined : 'Dialog'}
        tabIndex={-1}
        className={cn(
          'relative w-full max-h-[90dvh] overflow-y-auto bg-surface border border-border rounded-xl shadow-xl z-10',
          sizeClasses[size],
          className
        )}
      >
        {/* Header */}
        {(title || description) && (
          <div className="px-6 py-5 border-b border-border">
            {title && <h2 id={titleId} className="text-base font-semibold text-text">{title}</h2>}
            {description && <p className="text-sm text-text-muted mt-1">{description}</p>}
          </div>
        )}
        {/* Close button */}
        <button
          type="button"
          aria-label="Close dialog"
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded text-text-muted hover:text-text hover:bg-border/40 transition-colors"
        >
          <X size={16} />
        </button>
        {/* Content */}
        <div>{children}</div>
      </div>
    </div>, document.body
  )
}

export function DialogContent({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('px-6 py-5', className)}>{children}</div>
}

export function DialogFooter({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn('px-6 py-4 border-t border-border flex items-center justify-end gap-3', className)}>
      {children}
    </div>
  )
}
