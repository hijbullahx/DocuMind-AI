/**
 * Custom React Hook for Managing User Authentication State & Session Lifecycle.
 */
import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '@/services/api'
import type { LoginCredentials, User } from '@/types/auth'

export interface UseAuthReturn {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (credentials: LoginCredentials) => Promise<boolean>
  logout: () => Promise<void>
  clearError: () => void
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<User | null>(() => api.getStoredUser())
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => Boolean(api.getAccessToken()))
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const clearError = useCallback(() => setError(null), [])

  // Initialize and validate existing session on mount
  useEffect(() => {
    let isMounted = true

    async function initSession() {
      const token = api.getAccessToken()
      if (!token) {
        if (isMounted) {
          setIsLoading(false)
          setIsAuthenticated(false)
          setUser(null)
        }
        return
      }

      try {
        const currentUser = await api.getCurrentUser()
        if (isMounted) {
          setUser(currentUser)
          setIsAuthenticated(true)
        }
      } catch (err: unknown) {
        if (isMounted) {
          if (err instanceof ApiError && err.status === 401) {
            api.clearStoredAuth()
            setUser(null)
            setIsAuthenticated(false)
          } else {
            // If network request failed but local session exists, retain stored user
            const fallbackUser = api.getStoredUser()
            if (fallbackUser) {
              setUser(fallbackUser)
              setIsAuthenticated(true)
            } else {
              setIsAuthenticated(false)
            }
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    initSession()

    // Subscribe to global 401 unauthorized session expiration events
    const unsubscribe = api.onUnauthorized(() => {
      if (isMounted) {
        setUser(null)
        setIsAuthenticated(false)
        setError('Your session has expired. Please sign in again.')
      }
    })

    return () => {
      isMounted = false
      unsubscribe()
    }
  }, [])

  const login = useCallback(async (credentials: LoginCredentials): Promise<boolean> => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.login(credentials)
      setUser(response.user)
      setIsAuthenticated(true)
      return true
    } catch (err: unknown) {
      let message = 'Sign in failed. Please check your credentials.'
      if (err instanceof ApiError) {
        if (err.data && typeof err.data === 'object') {
          const dataObj = err.data as Record<string, unknown>
          if (typeof dataObj.detail === 'string') {
            message = dataObj.detail
          } else if (typeof dataObj.error === 'string') {
            message = dataObj.error
          }
        }
      }
      setError(message)
      return false
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(async () => {
    setIsLoading(true)
    try {
      await api.logout()
    } finally {
      setUser(null)
      setIsAuthenticated(false)
      setError(null)
      setIsLoading(false)
    }
  }, [])

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    logout,
    clearError,
  }
}
