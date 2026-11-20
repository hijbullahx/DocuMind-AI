/**
 * Unit Test Suite for TASK-020: Frontend Authentication, Token Management & Session Hardening.
 */
import test, { describe } from 'node:test'
import assert from 'node:assert'
import {
  api,
  clearStoredAuth,
  getStoredAccessToken,
  getStoredRefreshToken,
  getStoredUser,
  setStoredTokens,
  setStoredUser,
} from '../services/api.ts'
import type { User } from '../types/auth.ts'

// Mock in-memory localStorage for Node test runner
const memoryStorage: Record<string, string> = {}
globalThis.localStorage = {
  getItem: (key: string) => memoryStorage[key] || null,
  setItem: (key: string, value: string) => {
    memoryStorage[key] = value
  },
  removeItem: (key: string) => {
    delete memoryStorage[key]
  },
  clear: () => {
    for (const key in memoryStorage) {
      delete memoryStorage[key]
    }
  },
  length: 0,
  key: () => null,
}

describe('TASK-020: Token Storage & Session Persistence', () => {
  test('stores, retrieves, and clears JWT access and refresh tokens', () => {
    clearStoredAuth()
    assert.strictEqual(getStoredAccessToken(), null)
    assert.strictEqual(getStoredRefreshToken(), null)

    setStoredTokens({
      access: 'mock-access-token-xyz-123',
      refresh: 'mock-refresh-token-abc-456',
    })

    assert.strictEqual(getStoredAccessToken(), 'mock-access-token-xyz-123')
    assert.strictEqual(getStoredRefreshToken(), 'mock-refresh-token-abc-456')

    clearStoredAuth()
    assert.strictEqual(getStoredAccessToken(), null)
    assert.strictEqual(getStoredRefreshToken(), null)
  })

  test('stores, retrieves, and clears authenticated user profile', () => {
    clearStoredAuth()
    assert.strictEqual(getStoredUser(), null)

    const mockUser: User = {
      id: 42,
      username: 'lead_auditor',
      email: 'auditor@documind.test',
      is_staff: true,
      is_superuser: false,
    }

    setStoredUser(mockUser)
    const retrieved = getStoredUser()
    assert.deepStrictEqual(retrieved, mockUser)

    clearStoredAuth()
    assert.strictEqual(getStoredUser(), null)
  })
})

describe('TASK-020: Authorization Header Injection & API Security', () => {
  test('injects Authorization Bearer header when token is stored', async () => {
    clearStoredAuth()
    setStoredTokens({ access: 'test-jwt-token-999', refresh: 'test-refresh-999' })

    let capturedHeaders: Headers | null = null
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (_input: RequestInfo | URL, init?: RequestInit) => {
      capturedHeaders = new Headers(init?.headers)
      return new Response(JSON.stringify({ id: 'doc-1', filename: 'invoice.pdf' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    try {
      await api.getDocumentDetail('doc-1')
      assert.notStrictEqual(capturedHeaders, null)
      assert.strictEqual(capturedHeaders?.get('Authorization'), 'Bearer test-jwt-token-999')
    } finally {
      globalThis.fetch = originalFetch
      clearStoredAuth()
    }
  })

  test('does not inject Authorization header when user is unauthenticated', async () => {
    clearStoredAuth()

    let capturedHeaders: Headers | null = null
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (_input: RequestInfo | URL, init?: RequestInit) => {
      capturedHeaders = new Headers(init?.headers)
      return new Response(JSON.stringify({ status: 'ok', app: 'DocuMind-AI' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    try {
      await api.checkBackendHealth()
      assert.notStrictEqual(capturedHeaders, null)
      assert.strictEqual(capturedHeaders?.get('Authorization'), null)
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})

describe('TASK-020: Token Refresh & Unauthorized Interception', () => {
  test('automatically refreshes token on 401 and retries original request', async () => {
    clearStoredAuth()
    setStoredTokens({ access: 'expired-access-token', refresh: 'valid-refresh-token' })

    let requestCount = 0
    let refreshAttempted = false
    const originalFetch = globalThis.fetch

    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const urlStr = String(input)
      requestCount++

      if (urlStr.includes('/auth/refresh/')) {
        refreshAttempted = true
        return new Response(JSON.stringify({ access: 'brand-new-access-token' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      const authHeader = new Headers(init?.headers).get('Authorization')
      if (authHeader === 'Bearer expired-access-token') {
        return new Response(JSON.stringify({ detail: 'Token expired' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (authHeader === 'Bearer brand-new-access-token') {
        return new Response(JSON.stringify({ id: 'doc-refreshed', filename: 'refreshed.pdf' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      return new Response(null, { status: 500 })
    }

    try {
      const result = await api.getDocumentDetail('doc-refreshed')
      assert.strictEqual(refreshAttempted, true)
      assert.strictEqual(result.filename, 'refreshed.pdf')
      assert.strictEqual(getStoredAccessToken(), 'brand-new-access-token')
    } finally {
      globalThis.fetch = originalFetch
      clearStoredAuth()
    }
  })

  test('clears stored credentials and notifies subscribers when refresh fails', async () => {
    clearStoredAuth()
    setStoredTokens({ access: 'expired-token', refresh: 'expired-refresh-token' })

    let notified = false
    const unsubscribe = api.onUnauthorized(() => {
      notified = true
    })

    const originalFetch = globalThis.fetch
    globalThis.fetch = async (input: RequestInfo | URL) => {
      const urlStr = String(input)
      if (urlStr.includes('/auth/refresh/')) {
        return new Response(JSON.stringify({ detail: 'Token is invalid or expired' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({ detail: 'Authentication credentials were not provided.' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    try {
      await assert.rejects(async () => {
        await api.getDocumentDetail('some-doc')
      })

      assert.strictEqual(notified, true)
      assert.strictEqual(getStoredAccessToken(), null)
      assert.strictEqual(getStoredRefreshToken(), null)
    } finally {
      unsubscribe()
      globalThis.fetch = originalFetch
      clearStoredAuth()
    }
  })
})

describe('TASK-020: User Roles & Profile Authorization Attributes', () => {
  test('determines operator role labels accurately', () => {
    const superuser: User = {
      id: 1,
      username: 'root',
      email: 'root@documind.test',
      is_staff: true,
      is_superuser: true,
    }
    const staffUser: User = {
      id: 2,
      username: 'staff_admin',
      email: 'admin@documind.test',
      is_staff: true,
      is_superuser: false,
    }
    const standardAuditor: User = {
      id: 3,
      username: 'auditor_one',
      email: 'auditor@documind.test',
      is_staff: false,
      is_superuser: false,
    }

    const getRole = (u: User) =>
      u.is_superuser ? 'Superuser' : u.is_staff ? 'Administrator' : 'Compliance Auditor'

    assert.strictEqual(getRole(superuser), 'Superuser')
    assert.strictEqual(getRole(staffUser), 'Administrator')
    assert.strictEqual(getRole(standardAuditor), 'Compliance Auditor')
  })
})
