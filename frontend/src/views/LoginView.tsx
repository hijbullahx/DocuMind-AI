import React, { useState } from 'react'
import {
  AlertCircle,
  Eye,
  EyeOff,
  FileText,
  KeyRound,
  Lock,
  ShieldCheck,
  User as UserIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { LoginCredentials } from '@/types/auth'

export interface LoginViewProps {
  onLogin: (credentials: LoginCredentials) => Promise<boolean>
  isLoading: boolean
  error: string | null
  onClearError?: () => void
}

export const LoginView: React.FC<LoginViewProps> = ({
  onLogin,
  isLoading,
  error,
  onClearError,
}) => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)

    if (!username.trim() || !password) {
      setValidationError('Please enter both your username and password.')
      return
    }

    await onLogin({ username: username.trim(), password })
  }

  const handleFillCredentials = (user: string, pass: string) => {
    setUsername(user)
    setPassword(pass)
    setValidationError(null)
    if (onClearError) {
      onClearError()
    }
  }

  const displayError = validationError || error

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 sm:p-6 lg:p-8 relative overflow-hidden">
      {/* Background Ambient Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Login Card Container */}
      <div className="w-full max-w-md relative z-10">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center shadow-xl shadow-brand-500/25 ring-1 ring-brand-400/40 mb-4">
            <FileText className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-1.5">
            DocuMind<span className="text-brand-400">-AI</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-medium">
            Enterprise Document Intelligence & Hardened Audit Workbench
          </p>
        </div>

        {/* Security & Access Box */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl shadow-black/60 backdrop-blur-md">
          <div className="flex items-center justify-between pb-5 mb-5 border-b border-slate-800">
            <div>
              <h2 className="text-base font-semibold text-slate-100">Operator Sign In</h2>
              <p className="text-xs text-slate-400">Enter your credentials to access protected views</p>
            </div>
            <div className="w-9 h-9 rounded-xl bg-brand-950 border border-brand-800/80 flex items-center justify-center text-brand-300">
              <Lock className="w-4 h-4" />
            </div>
          </div>

          {/* Error Banner */}
          {displayError && (
            <div className="mb-5 p-3.5 rounded-xl bg-rose-950/70 border border-rose-800/80 flex items-start gap-3 text-rose-200 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span className="flex-1 font-medium">{displayError}</span>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username-input" className="block text-xs font-semibold text-slate-300 mb-1.5">
                Username or Auditor ID
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <UserIcon className="w-4 h-4" />
                </div>
                <input
                  id="username-input"
                  type="text"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value)
                    if (onClearError) onClearError()
                  }}
                  placeholder="e.g. compliance_auditor"
                  disabled={isLoading}
                  autoComplete="username"
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all disabled:opacity-50"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password-input" className="block text-xs font-semibold text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <KeyRound className="w-4 h-4" />
                </div>
                <input
                  id="password-input"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (onClearError) onClearError()
                  }}
                  placeholder="••••••••••••"
                  disabled={isLoading}
                  autoComplete="current-password"
                  className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl pl-10 pr-10 py-2.5 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200"
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full mt-2 font-semibold shadow-lg shadow-brand-600/20"
              isLoading={isLoading}
              leftIcon={<ShieldCheck className="w-4 h-4" />}
            >
              Authenticate & Continue
            </Button>
          </form>

          {/* Quick Credential Fill for Reviewers / Operators */}
          <div className="mt-6 pt-5 border-t border-slate-800">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2.5 text-center">
              Quick Operator Access
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleFillCredentials('compliance_auditor', 'SecurePassword2026!')}
                className="px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700/70 text-left transition-colors group"
              >
                <div className="text-xs font-semibold text-slate-200 group-hover:text-brand-300">
                  Auditor Account
                </div>
                <div className="text-[10px] text-slate-400 font-mono">compliance_auditor</div>
              </button>

              <button
                type="button"
                onClick={() => handleFillCredentials('admin', 'AdminPass2026!')}
                className="px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700/70 text-left transition-colors group"
              >
                <div className="text-xs font-semibold text-slate-200 group-hover:text-brand-300">
                  Administrator
                </div>
                <div className="text-[10px] text-slate-400 font-mono">admin</div>
              </button>
            </div>
          </div>
        </div>

        {/* Security Footer Notice */}
        <div className="mt-6 text-center text-[11px] text-slate-400 flex items-center justify-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-brand-400" />
          <span>TASK-020 Hardened JWT Token Pair • Protected API Endpoints</span>
        </div>
      </div>
    </div>
  )
}
