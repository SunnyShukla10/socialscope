import React from 'react'
import { cn } from '@/lib/utils'

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'muted' | 'outline'

interface BadgeProps {
  variant?: BadgeVariant
  className?: string
  children: React.ReactNode
  style?: React.CSSProperties
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-primary/10 text-primary border-primary/20',
  success: 'bg-[#437A22]/10 text-[#437A22] border-[#437A22]/20',
  warning: 'bg-[#FFC553]/15 text-[#7A5800] border-[#FFC553]/30',
  danger: 'bg-red-50 text-red-700 border-red-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
  muted: 'bg-border/40 text-text-muted border-border',
  outline: 'bg-transparent text-text border-border',
}

export function Badge({ variant = 'default', className, children, style }: BadgeProps) {
  return (
    <span
      style={style}
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border',
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  )
}
