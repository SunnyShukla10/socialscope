'use client'

import React from 'react'
import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  className?: string
}

export function Pagination({ page, totalPages, onPageChange, className }: PaginationProps) {
  if (totalPages <= 1) return null

  const getPageNumbers = () => {
    const pages: (number | '...')[] = []
    const maxVisible = 7

    if (totalPages <= maxVisible) {
      return Array.from({ length: totalPages }, (_, i) => i + 1)
    }

    pages.push(1)

    if (page > 3) pages.push('...')

    const start = Math.max(2, page - 1)
    const end = Math.min(totalPages - 1, page + 1)

    for (let i = start; i <= end; i++) {
      pages.push(i)
    }

    if (page < totalPages - 2) pages.push('...')

    pages.push(totalPages)

    return pages
  }

  const pageNumbers = getPageNumbers()

  return (
    <div className={cn('flex items-center justify-center gap-1', className)}>
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className={cn(
          'flex items-center gap-1 px-3 py-1.5 rounded text-sm font-medium transition-colors',
          'hover:bg-border/50 text-text-muted hover:text-text',
          'disabled:opacity-40 disabled:cursor-not-allowed'
        )}
      >
        <ChevronLeft size={16} />
        <span>Previous</span>
      </button>

      {pageNumbers.map((pageNum, idx) =>
        pageNum === '...' ? (
          <span key={`ellipsis-${idx}`} className="px-2 py-1.5 text-sm text-text-muted">
            …
          </span>
        ) : (
          <button
            key={pageNum}
            onClick={() => onPageChange(pageNum as number)}
            className={cn(
              'min-w-[36px] h-9 px-2 rounded text-sm font-medium transition-colors',
              page === pageNum
                ? 'bg-primary text-white'
                : 'text-text hover:bg-border/50'
            )}
          >
            {pageNum}
          </button>
        )
      )}

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className={cn(
          'flex items-center gap-1 px-3 py-1.5 rounded text-sm font-medium transition-colors',
          'hover:bg-border/50 text-text-muted hover:text-text',
          'disabled:opacity-40 disabled:cursor-not-allowed'
        )}
      >
        <span>Next</span>
        <ChevronRight size={16} />
      </button>
    </div>
  )
}
