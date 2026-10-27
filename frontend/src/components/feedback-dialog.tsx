'use client'

import React, { useEffect, useRef, useState } from 'react'
import { usePathname } from 'next/navigation'
import { fetchApi } from '@/lib/api'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

export function FeedbackDialog() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState('feedback')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    form.current?.querySelector<HTMLSelectElement>('select')?.focus()
    return () => trigger.current?.focus()
  }, [open])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await fetchApi('/feedback', { method: 'POST', body: JSON.stringify({ kind, message, page_path: pathname }) })
      setMessage('')
      setSent(true)
    } catch (err) {
      setError((err as { message?: string }).message || 'Could not send your report. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return <>
    <button ref={trigger} onClick={() => { setOpen(true); setSent(false) }}
      className="w-full px-3 py-2.5 text-left text-sm text-text-muted hover:text-text hover:bg-background rounded-lg">
      Feedback / Report an issue
    </button>
    <Dialog open={open} onClose={() => { if (!busy) setOpen(false) }} title="Feedback / Report an issue">
      <form ref={form} onSubmit={submit} role="dialog" aria-modal="true" aria-label="Feedback / Report an issue"
        className="p-6 space-y-4" onKeyDown={(event) => {
          if (event.key === 'Escape' && !busy) setOpen(false)
          if (event.key !== 'Tab') return
          const controls = form.current?.querySelectorAll<HTMLElement>('select, textarea, button:not(:disabled)')
          if (!controls?.length) return
          const first = controls[0], last = controls[controls.length - 1]
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
          if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
        }}>
        {sent ? <p role="status" className="text-sm text-text">Thank you. Your report has been sent to your administrator.</p> : <>
          <label className="block text-sm text-text">Type
            <select value={kind} onChange={e => setKind(e.target.value)} disabled={busy}
              className="block w-full mt-2 rounded border border-border bg-background p-2">
              <option value="feedback">Feedback</option><option value="issue">Issue</option>
            </select>
          </label>
          <label className="block text-sm text-text">Message
            <textarea required maxLength={5000} rows={5} value={message} disabled={busy}
              onChange={e => setMessage(e.target.value)}
              className="block w-full mt-2 rounded border border-border bg-background p-2" />
          </label>
          <p className="text-xs text-text-muted">Your account and current page will be included. Please omit passwords, API keys, and sensitive research data.</p>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        </>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" disabled={busy} onClick={() => setOpen(false)}>{sent ? 'Close' : 'Cancel'}</Button>
          {!sent && <Button type="submit" disabled={busy || !message.trim()}>{busy ? 'Sending…' : 'Submit'}</Button>}
        </div>
      </form>
    </Dialog>
  </>
}
