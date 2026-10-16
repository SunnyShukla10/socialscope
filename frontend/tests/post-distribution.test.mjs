import assert from 'node:assert/strict'
import {distribution} from '../src/lib/post-distribution.mjs'
const platforms = ['tiktok', 'instagram', 'facebook']
assert.deepEqual(distribution(platforms, 1000, {facebook: 50}).counts, {tiktok: 343, instagram: 157, facebook: 500})
assert.deepEqual(distribution(platforms, 500, {facebook: 100}).counts, {tiktok: 0, instagram: 0, facebook: 500})
assert.ok(distribution(platforms, 500, {facebook: 101}).error)
assert.ok(distribution(platforms, 500, {facebook: 50, instagram: 50, tiktok: 50}).error)
assert.ok(distribution(platforms, 500, {facebook: 30, instagram: 30, tiktok: 30}).error)
assert.deepEqual(distribution(['facebook'], 100).counts, {facebook: 100})
for (const total of [100, 101, 499, 2500, 5000]) {
  for (const overrides of [{}, {facebook: 0}, {tiktok: 33.33}, {tiktok: 33.33, instagram: 33.33, facebook: 33.34}]) {
    const result = distribution(platforms, total, overrides)
    assert.equal(result.error, '')
    assert.equal(Object.values(result.counts).reduce((a,b) => a+b, 0), total)
    assert.ok(Object.values(result.counts).every(n => Number.isInteger(n) && n >= 0))
  }
}
console.log('Post distribution checks passed')
