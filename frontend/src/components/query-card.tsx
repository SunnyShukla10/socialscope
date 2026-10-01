'use client'

import React, { useState } from 'react'
import { cn } from '@/lib/utils'
import { Check, Edit2, FileText, Search, Zap, Shield, Layers } from 'lucide-react'
import type { QueryCandidate } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { characterCount } from '@/lib/query-validation.mjs'

interface QueryCardProps {
  candidate: QueryCandidate
  selected: boolean
  onSelect: (candidate: QueryCandidate) => void
  onEdit?: (candidate: QueryCandidate, newQuery: string) => void
  maximumLength: number
  warningRatio: number
  validationMessage?: string
}

const complexityConfig = {
  simple: { icon: Zap, label: 'Simple', color: 'text-[#437A22]', bg: 'bg-[#437A22]/10' },
  moderate: { icon: Layers, label: 'Moderate', color: 'text-primary', bg: 'bg-primary/10' },
  complex: { icon: Shield, label: 'Complex', color: 'text-[#A84B2F]', bg: 'bg-[#A84B2F]/10' },
}

const queryTypeConfig = {
  natural_language: {
    icon: Search,
    label: 'Natural language',
    color: 'text-[#1B474D]',
    bg: 'bg-[#1B474D]/10',
  },
  boolean: {
    icon: FileText,
    label: 'Boolean',
    color: 'text-[#7A5800]',
    bg: 'bg-[#FFC553]/15',
  },
}

export function QueryCard({
  candidate,
  selected,
  onSelect,
  onEdit,
  maximumLength,
  warningRatio,
  validationMessage,
}: QueryCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(candidate.query)
  const cfg = complexityConfig[candidate.complexity] || complexityConfig.moderate
  const ComplexityIcon = cfg.icon
  const typeCfg = queryTypeConfig[candidate.queryType] || queryTypeConfig.boolean
  const QueryTypeIcon = typeCfg.icon
  const displayedQuery = isEditing ? editValue : candidate.query
  const queryLength = characterCount(displayedQuery)
  const approachingLimit = queryLength >= Math.floor(maximumLength * warningRatio)

  function handleSaveEdit() {
    if (onEdit && editValue.trim()) {
      onEdit(candidate, editValue.trim())
    }
    setIsEditing(false)
  }

  function handleCancelEdit() {
    setEditValue(candidate.query)
    setIsEditing(false)
  }

  return (
    <div
      className={cn(
        'relative rounded-lg border-2 p-5 transition-all duration-150 cursor-pointer',
        selected
          ? 'border-primary bg-primary/5 shadow-sm'
          : 'border-border bg-surface hover:border-primary/40 hover:shadow-sm'
      )}
      onClick={() => !isEditing && onSelect(candidate)}
    >
      {/* Selection indicator */}
      <div
        className={cn(
          'absolute top-3 right-3 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all',
          selected ? 'bg-primary border-primary' : 'border-border bg-surface'
        )}
      >
        {selected && <Check size={12} className="text-white" strokeWidth={3} />}
      </div>

      {/* Header */}
      <div className="flex items-center gap-2 mb-3 pr-8">
        <span
          className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
            typeCfg.bg,
            typeCfg.color
          )}
        >
          <QueryTypeIcon size={11} />
          {typeCfg.label}
        </span>
        <span
          className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
            cfg.bg,
            cfg.color
          )}
        >
          <ComplexityIcon size={11} />
          {cfg.label}
        </span>
        {candidate.estimated_volume && (
          <span className="text-xs text-text-muted">~{candidate.estimated_volume} results</span>
        )}
      </div>

      {/* Description */}
      <p className="text-sm font-medium text-text mb-3">{candidate.description}</p>

      {/* Query */}
      {isEditing ? (
        <div
          className="space-y-2"
          onClick={(e) => e.stopPropagation()}
        >
          <Textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="font-mono text-xs min-h-[80px]"
            autoFocus
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSaveEdit}>
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={handleCancelEdit}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <>
          <div className="bg-background rounded border border-border px-3 py-2.5 font-mono text-xs text-text leading-relaxed break-all">
            {candidate.query}
          </div>
          <button
            className="mt-2 flex items-center gap-1 text-xs text-text-muted hover:text-primary transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              setIsEditing(true)
            }}
          >
            <Edit2 size={12} />
            Edit query
          </button>
        </>
      )}
      <div className="mt-2 flex flex-wrap items-start justify-between gap-2 text-xs">
        <span
          className={
            validationMessage
              ? 'text-red-700'
              : approachingLimit
                ? 'text-[#A84B2F]'
                : 'text-text-muted'
          }
        >
          {queryLength} / {maximumLength} characters
        </span>
        {!validationMessage && approachingLimit && (
          <span className="text-[#A84B2F]">
            Approaching the configured limit for the selected platforms.
          </span>
        )}
      </div>
      {validationMessage && (
        <p className="mt-2 text-xs text-red-700" role="alert">
          {validationMessage}
        </p>
      )}
    </div>
  )
}
