const CANCELLABLE_STATUSES = new Set(['queued', 'pending', 'running'])

export function isCollectionCancellable(status) {
  return CANCELLABLE_STATUSES.has(status)
}

export function cancellationButtonState(status, submitting = false) {
  if (status === 'cancelling' || submitting) {
    return {
      visible: true,
      disabled: true,
      label: 'Cancelling…',
    }
  }
  if (isCollectionCancellable(status)) {
    return {
      visible: true,
      disabled: false,
      label: 'Cancel collection',
    }
  }
  return {
    visible: false,
    disabled: true,
    label: 'Cancel collection',
  }
}

export function applyCancellationResponse(job, response) {
  const cancelling = new Set(
    (response.cancelling_platforms || []).map((platform) => platform.toLowerCase())
  )
  const platformStates = Object.fromEntries(
    Object.entries(job.platform_states || {}).map(([platform, state]) => [
      platform,
      cancelling.has(platform.toLowerCase())
        ? { ...state, status: 'cancel_requested' }
        : state,
    ])
  )

  return {
    ...job,
    status: 'cancelling',
    cancel_requested_at: response.cancel_requested_at,
    cancel_requested_by: response.cancel_requested_by,
    platform_states: platformStates,
  }
}

export function createSingleFlightAction(action) {
  let inFlight = null
  return (...args) => {
    if (inFlight) return inFlight
    inFlight = Promise.resolve()
      .then(() => action(...args))
      .finally(() => {
        inFlight = null
      })
    return inFlight
  }
}

export function preservedPostsMessage(status, postsCollected) {
  if (status !== 'cancelled') return ''
  const count = Number(postsCollected || 0).toLocaleString('en-US')
  return `Collection cancelled — ${count} posts were preserved.`
}
