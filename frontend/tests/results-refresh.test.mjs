import assert from 'node:assert/strict'
import test from 'node:test'

import {
  hasCommittedPostIncrease,
  isCollectionActive,
  latestSearchJob,
  resultRefreshMode,
} from '../src/lib/results-refresh.mjs'


test('polls only while collection work is active', () => {
  for (const status of ['queued', 'pending', 'running', 'cancelling']) {
    assert.equal(isCollectionActive(status), true)
  }
  for (const status of ['completed', 'completed_with_errors', 'cancelled', 'failed']) {
    assert.equal(isCollectionActive(status), false)
  }
})

test('selects the most recently created search job', () => {
  const latest = latestSearchJob([
    { id: 'old', created_at: '2026-01-01T00:00:00Z' },
    { id: 'new', created_at: '2026-02-01T00:00:00Z' },
  ])

  assert.equal(latest.id, 'new')
})

test('refreshes only when the same job commits additional posts', () => {
  const observation = { jobId: 'job-1', postsCollected: 20 }

  assert.equal(
    hasCommittedPostIncrease(observation, { id: 'job-1', posts_collected: 30 }),
    true
  )
  assert.equal(
    hasCommittedPostIncrease(observation, { id: 'job-1', posts_collected: 20 }),
    false
  )
  assert.equal(
    hasCommittedPostIncrease(observation, { id: 'job-2', posts_collected: 30 }),
    false
  )
})

test('fully refreshes page one and only refreshes metadata on later pages', () => {
  assert.equal(resultRefreshMode(1), 'full')
  assert.equal(resultRefreshMode(2), 'summary')
})
