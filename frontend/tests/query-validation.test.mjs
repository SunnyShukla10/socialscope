import assert from 'node:assert/strict'
import test from 'node:test'

import {
  DEFAULT_QUERY_LIMITS,
  applicableMaximum,
  characterCount,
  validateFrontendQuery,
} from '../src/lib/query-validation.mjs'


test('shows a clear platform and provider message when a query is too long', () => {
  const issue = validateFrontendQuery('x'.repeat(201), ['twitter'], DEFAULT_QUERY_LIMITS)

  assert.equal(issue.code, 'QUERY_TOO_LONG')
  assert.equal(issue.platform, 'twitter')
  assert.equal(issue.provider, 'xpoz')
  assert.match(issue.message, /Twitter \/ X via Xpoz/)
  assert.match(issue.message, /200 characters/)
  assert.match(issue.message, /query has 201/)
})

test('uses the most restrictive configured selected-platform limit', () => {
  const limits = structuredClone(DEFAULT_QUERY_LIMITS)
  limits.platforms.twitter.maximum_length = 150
  limits.platforms.reddit.maximum_length = 180

  assert.equal(applicableMaximum(['reddit', 'twitter'], limits), 150)
  assert.equal(
    validateFrontendQuery('x'.repeat(151), ['reddit', 'twitter'], limits).platform,
    'twitter'
  )
})

test('accepts a query exactly at the configured limit', () => {
  assert.equal(
    validateFrontendQuery('x'.repeat(200), ['reddit'], DEFAULT_QUERY_LIMITS),
    null
  )
})

test('shows clear syntax errors', () => {
  const parentheses = validateFrontendQuery('(migraine AND care', ['reddit'])
  const quotes = validateFrontendQuery('"migraine care', ['twitter'])

  assert.match(parentheses.message, /unbalanced parentheses/)
  assert.match(parentheses.message, /Reddit via SociaVault/)
  assert.match(quotes.message, /unbalanced double quote/)
  assert.match(quotes.message, /Twitter \/ X via Xpoz/)
})

test('counts Unicode code points consistently with the backend', () => {
  assert.equal(characterCount('care 😊'), 6)
})
