'use client'

import React, { useState } from 'react'
import { usePathname } from 'next/navigation'
import { fetchApi } from '@/lib/api'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

export function FeedbackDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname()
  const [kind, setKind] = useState('feedback')
  const [message, setMessage] = useState('')
  const [errorDetails, setErrorDetails] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await fetchApi('/feedback', { method: 'POST', body: JSON.stringify({ kind, message, error_details: errorDetails || null, page_path: pathname }) })
      setMessage('')
      setErrorDetails('')
      setSent(true)
    } catch (err) {
      setError((err as { message?: string }).message || 'Could not send your report. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  function dismiss() {
    if (busy) return
    setSent(false)
    onClose()
  }

  return <Dialog open={open} onClose={dismiss} title="Feedback / Report an issue" size="lg">
      <form onSubmit={submit} className="p-6 space-y-4">
        {sent ? <p role="status" className="text-sm text-text">Thank you. Your report has been sent to your administrator.</p> : <>
          <div className="text-sm text-text">
            <label htmlFor="feedback-kind" className="block">Type</label>
            <select id="feedback-kind" data-dialog-autofocus value={kind} onChange={e => setKind(e.target.value)} disabled={busy}
              className="block w-full mt-2 rounded border border-border bg-background p-2">
              <option value="feedback">Feedback</option><option value="issue">Issue</option>
            </select>
          </div>
          <div className="text-sm text-text">
            <label htmlFor="feedback-message" className="block">Message</label>
            <textarea id="feedback-message" required maxLength={5000} rows={5} value={message} disabled={busy}
              onChange={e => setMessage(e.target.value)}
              className="block w-full mt-2 rounded border border-border bg-background p-2" />
          </div>
          <div className="text-sm text-text">
            <label htmlFor="feedback-error-details" className="block">Error details (optional)</label>
            <textarea id="feedback-error-details" maxLength={20000} rows={6} value={errorDetails} disabled={busy}
              onChange={e => setErrorDetails(e.target.value)} spellCheck={false}
              placeholder="Copy and paste the exact error message here. Line breaks will be preserved."
              className="block w-full mt-2 rounded border border-border bg-background p-2 text-xs font-mono" />
          </div>
          <p className="text-xs text-text-muted">Your account and current page will be included. Please omit passwords, API keys, and sensitive research data.</p>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        </>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" disabled={busy} onClick={dismiss}>{sent ? 'Close' : 'Cancel'}</Button>
          {!sent && <Button type="submit" disabled={busy || !message.trim()}>{busy ? 'Sending…' : 'Submit'}</Button>}
        </div>
      </form>
    </Dialog>
}
