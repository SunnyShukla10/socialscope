'use client'

import React from 'react'
import { cn } from '@/lib/utils'
import { Check } from 'lucide-react'

interface CheckboxProps {
  label?: string
  checked?: boolean
  onChange?: (checked: boolean) => void
  disabled?: boolean
  className?: string
  id?: string
  description?: string
}

export function Checkbox({
  label,
  checked = false,
  onChange,
  disabled,
  className,
  id,
  description,
}: CheckboxProps) {
  const checkboxId = id || (label ? `checkbox-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined)

  return (
    <div className={cn('flex items-start gap-2.5', className)}>
      <button
        role="checkbox"
        aria-checked={checked}
        id={checkboxId}
        disabled={disabled}
        onClick={() => onChange?.(!checked)}
        className={cn(
          'flex-shrink-0 w-4 h-4 mt-0.5 rounded border transition-colors duration-150',
          'focus:outline-none focus:ring-2 focus:ring-primary/30 focus:ring-offset-1',
          'disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
          checked
            ? 'bg-primary border-primary'
            : 'bg-surface border-border hover:border-primary/50'
        )}
      >
        {checked && (
          <Check size={12} className="text-white m-auto" strokeWidth={3} />
        )}
      </button>
      {label && (
        <div className="flex flex-col">
          <label
            htmlFor={checkboxId}
            className={cn(
              'text-sm cursor-pointer select-none',
              disabled ? 'text-text-muted cursor-not-allowed' : 'text-text'
            )}
            onClick={() => !disabled && onChange?.(!checked)}
          >
            {label}
          </label>
          {description && (
            <span className="text-xs text-text-muted mt-0.5">{description}</span>
          )}
        </div>
      )}
    </div>
  )
}
