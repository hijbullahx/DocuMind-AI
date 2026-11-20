/**
 * TypeScript Interfaces for DocuMind-AI Authentication and User Management.
 */

export interface User {
  id: number
  username: string
  email: string
  first_name?: string
  last_name?: string
  is_staff: boolean
  is_superuser: boolean
  date_joined?: string
  last_login?: string
}

export interface AuthTokens {
  access: string
  refresh: string
}

export interface LoginCredentials {
  username: string
  password: string
}

export interface LoginResponse {
  access: string
  refresh: string
  user: User
  message: string
}

export interface AuthState {
  user: User | null
  tokens: AuthTokens | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}
