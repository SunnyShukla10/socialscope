import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const code = ts.transpileModule(
  readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } },
).outputText

function setup(fetch) {
  const storage = new Map([['socialscope_token', 'existing-session']])
  const timers = new Map()
  const context = {
    exports: {}, process: { env: {} }, fetch, AbortController,
    localStorage: { getItem: (key) => storage.get(key), removeItem: (key) => storage.delete(key) },
    window: { location: { href: '' } },
    setTimeout: (fn, ms) => { assert.equal(ms, 15000); timers.set(1, fn); return 1 },
    clearTimeout: (id) => timers.delete(id),
  }
  vm.runInNewContext(code, context)
  return { ...context, storage, timers }
}

test('session timeout aborts the request, preserves the token, and permits retry', async () => {
  let retry = false
  const app = setup(async (_url, { signal }) => {
    if (retry) return new Response(JSON.stringify({ email: 'user@example.com' }))
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('aborted'))))
  })
  const pending = app.exports.getMe()
  app.timers.get(1)()
  await assert.rejects(pending, /aborted/)
  assert.equal(app.storage.get('socialscope_token'), 'existing-session')
  assert.equal(app.timers.size, 0)
  retry = true
  assert.equal((await app.exports.getMe()).name, 'user@example.com')
  assert.equal(app.timers.size, 0)
})

test('connection errors and server failures preserve the session', async () => {
  for (const fetch of [async () => { throw new TypeError('Failed to fetch') }, async () => new Response('{}', { status: 503 })]) {
    const app = setup(fetch)
    await assert.rejects(app.exports.getMe())
    assert.equal(app.storage.get('socialscope_token'), 'existing-session')
    assert.equal(app.window.location.href, '')
    assert.equal(app.timers.size, 0)
  }
})

test('a confirmed unauthorized session clears the token and redirects', async () => {
  const app = setup(async () => new Response('{}', { status: 401 }))
  await assert.rejects(app.exports.getMe(), (error) => error.status === 401)
  assert.equal(app.storage.has('socialscope_token'), false)
  assert.equal(app.window.location.href, '/login')
  assert.equal(app.timers.size, 0)
})

test('timeout also covers a response body that stalls after headers arrive', async () => {
  let readingBody
  const started = new Promise((resolve) => { readingBody = resolve })
  const app = setup(async (_url, { signal }) => ({
    status: 200,
    ok: true,
    text: () => {
      readingBody()
      return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('body aborted'))))
    },
  }))
  const pending = app.exports.getMe()
  await started
  app.timers.get(1)()
  await assert.rejects(pending, /body aborted/)
  assert.equal(app.storage.get('socialscope_token'), 'existing-session')
  assert.equal(app.timers.size, 0)
})
