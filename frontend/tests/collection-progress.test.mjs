import assert from 'node:assert/strict'
import test from 'node:test'

import {
  displayPlatformState,
  findPlatformState,
  platformProgress,
  shortProviderError,
} from '../src/lib/collection-progress.mjs'


test('counts completed, failed, and cancelled platforms as finished', () => {
  const progress = platformProgress(
    ['twitter', 'tiktok', 'reddit', 'youtube'],
    {
      twitter: { status: 'running', posts_collected: 0 },
      tiktok: { status: 'completed', posts_collected: 189 },
      reddit: { status: 'failed', posts_collected: 0 },
      youtube: { status: 'cancel_requested', posts_collected: 0 },
    },
    'running'
  )

  assert.deepEqual(progress, { finished: 2, total: 4, percent: 50 })
})

test('looks up platform states without depending on key casing', () => {
  const state = findPlatformState(
    'Twitter',
    { twitter: { status: 'completed', posts_collected: 42 } }
  )

  assert.equal(state.status, 'completed')
  assert.equal(state.posts_collected, 42)
})

test('keeps historical terminal jobs at full progress when detailed states are absent', () => {
  assert.deepEqual(
    platformProgress(['twitter', 'reddit'], {}, 'completed'),
    { finished: 2, total: 2, percent: 100 }
  )
  assert.equal(
    displayPlatformState('twitter', {}, 'completed').status,
    'unavailable'
  )
})

test('shortens provider errors and removes line breaks', () => {
  const error = shortProviderError(`Xpoz request failed\n${'x'.repeat(140)}`)

  assert.equal(error.includes('\n'), false)
  assert.equal(error.length, 120)
  assert.equal(error.endsWith('...'), true)
})
