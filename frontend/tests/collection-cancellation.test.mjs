import assert from 'node:assert/strict'
import test from 'node:test'

import {
  applyCancellationResponse,
  cancellationButtonState,
  createSingleFlightAction,
  isCollectionCancellable,
  preservedPostsMessage,
} from '../src/lib/collection-cancellation.mjs'


test('shows cancellation only for active collection states', () => {
  for (const status of ['queued', 'pending', 'running']) {
    assert.equal(isCollectionCancellable(status), true)
    assert.deepEqual(cancellationButtonState(status), {
      visible: true,
      disabled: false,
      label: 'Cancel collection',
    })
  }

  assert.deepEqual(cancellationButtonState('cancelling'), {
    visible: true,
    disabled: true,
    label: 'Cancelling…',
  })
  assert.equal(cancellationButtonState('completed').visible, false)
  assert.equal(cancellationButtonState('cancelled').visible, false)
})

test('double confirmation shares one cancellation request', async () => {
  let calls = 0
  let release
  const pending = new Promise((resolve) => {
    release = resolve
  })
  const cancelOnce = createSingleFlightAction(async () => {
    calls += 1
    await pending
    return { status: 'cancelling' }
  })

  const first = cancelOnce('project-1', 'job-1')
  const second = cancelOnce('project-1', 'job-1')

  assert.equal(calls, 0)
  await Promise.resolve()
  assert.equal(calls, 1)
  assert.equal(first, second)
  release()
  await first
})

test('optimistic cancellation preserves completed platform results', () => {
  const job = {
    status: 'running',
    platform_states: {
      tiktok: { status: 'completed', posts_collected: 189 },
      twitter: { status: 'running', posts_collected: 0 },
    },
  }
  const updated = applyCancellationResponse(job, {
    status: 'cancelling',
    cancel_requested_at: '2026-07-28T20:00:00Z',
    cancel_requested_by: 'user-1',
    completed_platforms: ['tiktok'],
    cancelling_platforms: ['twitter'],
  })

  assert.equal(updated.status, 'cancelling')
  assert.equal(updated.platform_states.tiktok.status, 'completed')
  assert.equal(updated.platform_states.tiktok.posts_collected, 189)
  assert.equal(updated.platform_states.twitter.status, 'cancel_requested')
  assert.equal(job.platform_states.twitter.status, 'running')
})

test('reports the number of posts preserved after cancellation', () => {
  assert.equal(
    preservedPostsMessage('cancelled', 309),
    'Collection cancelled — 309 posts were preserved.'
  )
  assert.equal(preservedPostsMessage('running', 309), '')
})
