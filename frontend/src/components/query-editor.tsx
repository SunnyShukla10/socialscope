'use client'

import React, { useState } from 'react'
import { cn } from '@/lib/utils'
import { X, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

// Tokenize a boolean query into chips
function tokenizeQuery(query: string): Token[] {
  const tokens: Token[] = []
  const parts = query.match(/("(?:[^"\\]|\\.)*"|\(|\)|AND|OR|NOT|\S+)/g) || []
  for (const part of parts) {
    if (part === 'AND') tokens.push({ type: 'operator', value: 'AND' })
    else if (part === 'OR') tokens.push({ type: 'operator', value: 'OR' })
    else if (part === 'NOT') tokens.push({ type: 'operator', value: 'NOT' })
    else if (part === '(') tokens.push({ type: 'paren', value: '(' })
    else if (part === ')') tokens.push({ type: 'paren', value: ')' })
    else if (part.startsWith('"')) tokens.push({ type: 'phrase', value: part })
    else tokens.push({ type: 'term', value: part })
  }
  return tokens
}

type TokenType = 'term' | 'phrase' | 'operator' | 'paren'

interface Token {
  type: TokenType
  value: string
}

interface QueryEditorProps {
  value: string
  onChange: (query: string) => void
  className?: string
}

export function QueryEditor({ value, onChange, className }: QueryEditorProps) {
  const [rawMode, setRawMode] = useState(false)
  const [rawValue, setRawValue] = useState(value)
  const [newTerm, setNewTerm] = useState('')
  const [addingTerm, setAddingTerm] = useState(false)

  const tokens = tokenizeQuery(value)

  function removeToken(idx: number) {
    const newTokens = tokens.filter((_, i) => i !== idx)
    onChange(newTokens.map((t) => t.value).join(' '))
  }

  function addTerm(term: string) {
    if (!term.trim()) return
    const trimmed = term.trim()
    const quoted = trimmed.includes(' ') ? `"${trimmed}"` : trimmed
    const newQuery = value ? `${value} AND ${quoted}` : quoted
    onChange(newQuery)
    setNewTerm('')
    setAddingTerm(false)
  }

  function handleRawSave() {
    onChange(rawValue)
    setRawMode(false)
  }

  const tokenColors: Record<TokenType, string> = {
    term: 'bg-primary/10 text-primary border-primary/20',
    phrase: 'bg-[#1B474D]/10 text-[#1B474D] border-[#1B474D]/20',
    operator: 'bg-[#FFC553]/15 text-[#7A5800] border-[#FFC553]/30',
    paren: 'bg-border/40 text-text-muted border-border',
  }

  return (
    <div className={cn('space-y-3', className)}>
      {/* Mode toggle */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
          Boolean Query
        </span>
        <button
          onClick={() => {
            if (rawMode) {
              handleRawSave()
            } else {
              setRawValue(value)
              setRawMode(true)
            }
          }}
          className="text-xs text-primary hover:text-primary-hover transition-colors"
        >
          {rawMode ? 'Done editing' : 'Edit as text'}
        </button>
      </div>

      {rawMode ? (
        <textarea
          value={rawValue}
          onChange={(e) => setRawValue(e.target.value)}
          onBlur={handleRawSave}
          className="w-full rounded border border-border bg-surface px-3 py-2.5 font-mono text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y min-h-[80px]"
          autoFocus
        />
      ) : (
        <div className="min-h-[60px] rounded-lg border border-border bg-surface p-3 flex flex-wrap gap-1.5 items-center">
          {tokens.map((token, idx) => (
            <span
              key={idx}
              className={cn(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border',
                tokenColors[token.type]
              )}
            >
              {token.value}
              {token.type !== 'operator' && token.type !== 'paren' && (
                <button
                  onClick={() => removeToken(idx)}
                  className="opacity-60 hover:opacity-100 transition-opacity ml-0.5"
                >
                  <X size={10} />
                </button>
              )}
            </span>
          ))}

          {addingTerm ? (
            <div className="flex items-center gap-1.5">
              <input
                type="text"
                value={newTerm}
                onChange={(e) => setNewTerm(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') addTerm(newTerm)
                  if (e.key === 'Escape') {
                    setNewTerm('')
                    setAddingTerm(false)
                  }
                }}
                placeholder="type term..."
                autoFocus
                className="px-2 py-0.5 text-xs rounded border border-primary bg-primary/5 focus:outline-none w-28"
              />
              <button
                onClick={() => addTerm(newTerm)}
                className="text-xs text-primary hover:text-primary-hover"
              >
                Add
              </button>
            </div>
          ) : (
            <button
              onClick={() => setAddingTerm(true)}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs text-text-muted hover:text-primary border border-dashed border-border hover:border-primary/40 transition-colors"
            >
              <Plus size={11} />
              Add term
            </button>
          )}
        </div>
      )}

      {/* Raw display */}
      {!rawMode && (
        <p className="font-mono text-xs text-text-muted bg-background px-3 py-2 rounded border border-border break-all">
          {value || <span className="italic">Empty query</span>}
        </p>
      )}
    </div>
  )
}
