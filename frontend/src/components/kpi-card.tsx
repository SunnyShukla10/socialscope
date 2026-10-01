import React from 'react'
import { cn } from '@/lib/utils'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface KpiCardProps {
  label: string
  value: string | number
  delta?: number
  deltaLabel?: string
  icon?: React.ReactNode
  className?: string
  loading?: boolean
}

export function KpiCard({
  label,
  value,
  delta,
  deltaLabel,
  icon,
  className,
  loading,
}: KpiCardProps) {
  const hasDelta = delta !== undefined && delta !== null
  const isPositive = hasDelta && delta > 0
  const isNegative = hasDelta && delta < 0

  return (
    <div
      className={cn(
        'bg-surface border border-border rounded-lg p-5',
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wide truncate">
            {label}
          </p>
          {loading ? (
            <div className="mt-2 h-8 w-20 bg-border/60 rounded animate-pulse" />
          ) : (
            <p className="mt-1.5 text-2xl font-bold text-text leading-tight">
              {value}
            </p>
          )}
          {hasDelta && !loading && (
            <div
              className={cn(
                'mt-1.5 flex items-center gap-1 text-xs font-medium',
                isPositive && 'text-[#437A22]',
                isNegative && 'text-[#A12C7B]',
                !isPositive && !isNegative && 'text-text-muted'
              )}
            >
              {isPositive && <TrendingUp size={12} />}
              {isNegative && <TrendingDown size={12} />}
              {!isPositive && !isNegative && <Minus size={12} />}
              <span>
                {isPositive ? '+' : ''}{delta}%{' '}
                {deltaLabel && <span className="font-normal">{deltaLabel}</span>}
              </span>
            </div>
          )}
        </div>
        {icon && (
          <div className="shrink-0 p-2.5 bg-primary/8 rounded-lg text-primary">
            {icon}
          </div>
        )}
      </div>
    </div>
  )
}
