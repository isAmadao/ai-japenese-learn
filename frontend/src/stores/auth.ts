/** Auth store — manages JWT token, current user, login/register/logout */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { http } from '@/api'

const TOKEN_KEY = 'ai_jp_token'
const REFRESH_KEY = 'ai_jp_refresh'
const USER_KEY = 'ai_jp_user'

export interface AuthUser {
  id: number
  username: string
  role: string
  email?: string
  is_verified?: boolean
  created_at?: string | null
}

/** Get a storage object (localStorage or sessionStorage) */
function _storage(): Storage {
  // _remember is set by login()
  const r = (window as any).__ai_jp_remember
  return r === false ? sessionStorage : localStorage
}

/** Read value from both storages (session takes priority) */
function _getItem(key: string): string | null {
  return sessionStorage.getItem(key) || localStorage.getItem(key)
}

/** Remove from both storages */
function _removeItem(key: string) {
  localStorage.removeItem(key)
  sessionStorage.removeItem(key)
}

/** Set in the active storage */
function _setItem(key: string, value: string) {
  _storage().setItem(key, value)
}

export const useAuthStore = defineStore('auth', () => {
  // ── State ──────────────────────────────────────────────

  const token = ref<string | null>(_getItem(TOKEN_KEY))
  const refreshToken = ref<string | null>(_getItem(REFRESH_KEY))
  const user = ref<AuthUser | null>(_loadUser())
  const loading = ref(false)
  const error = ref<string | null>(null)
  const remember = ref(true)

  // ── Getters ────────────────────────────────────────────

  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  // ── Actions ────────────────────────────────────────────

  /** Login. Returns { ok, captcha_required? } */
  async function login(username: string, password: string, captchaToken?: string, rememberMe?: boolean): Promise<{ ok: boolean; captcha_required?: boolean }> {
    loading.value = true
    error.value = null
    remember.value = rememberMe !== false
    try {
      const body: any = { username, password }
      if (captchaToken) body.captcha_token = captchaToken
      const { data } = await http.post('/auth/login', body)

      if (data.captcha_required) {
        return { ok: false, captcha_required: true }
      }

      _saveToken(data.access_token, data.refresh_token || '', {
        id: data.user_id,
        username: data.username,
        role: data.role || 'user',
        email: data.email || '',
        is_verified: data.is_verified || false,
      })
      return { ok: true }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || '登录失败'
      return { ok: false }
    } finally {
      loading.value = false
    }
  }

  async function register(username: string, password: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const { data } = await http.post('/auth/register', { username, password })
      _saveToken(data.access_token, data.refresh_token || '', {
        id: data.user_id,
        username: data.username,
        role: data.role || 'user',
        email: data.email || '',
        is_verified: data.is_verified || false,
      })
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.detail || '注册失败'
      return false
    } finally {
      loading.value = false
    }
  }

  async function registerWithEmail(
    nickname: string,
    email: string,
    password: string,
    registerToken: string,
  ): Promise<{ ok: boolean; userId?: number }> {
    loading.value = true
    error.value = null
    try {
      const { data } = await http.post('/auth/register/email', {
        nickname, email, password, register_token: registerToken,
      })
      _saveToken(data.access_token, data.refresh_token || '', {
        id: data.user_id,
        username: data.username,
        role: data.role || 'user',
        email: data.email || '',
        is_verified: data.is_verified || false,
      })
      return { ok: true, userId: data.user_id }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || '注册失败'
      return { ok: false }
    } finally {
      loading.value = false
    }
  }

  /** Try to refresh the access token. Returns true if successful. */
  async function tryRefresh(): Promise<boolean> {
    const rt = localStorage.getItem(REFRESH_KEY)
    if (!rt) return false

    try {
      const { data } = await http.post('/auth/refresh', { refresh_token: rt })
      _saveToken(data.access_token, data.refresh_token, user.value || undefined)
      return true
    } catch {
      logout()
      return false
    }
  }

  function logout() {
    token.value = null
    refreshToken.value = null
    user.value = null
    _removeItem(TOKEN_KEY)
    _removeItem(REFRESH_KEY)
    _removeItem(USER_KEY)
  }

  function _loadUser(): AuthUser | null {
    try {
      const raw = _getItem(USER_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }

  function _saveToken(t: string, rt: string, u?: AuthUser) {
    (window as any).__ai_jp_remember = remember.value
    token.value = t
    refreshToken.value = rt
    if (u) user.value = u
    _setItem(TOKEN_KEY, t)
    if (rt) _setItem(REFRESH_KEY, rt)
    if (u) _setItem(USER_KEY, JSON.stringify(u))
  }

  return {
    token, refreshToken, user, loading, error, remember,
    isAuthenticated, isAdmin,
    login, register, registerWithEmail, tryRefresh, logout,
  }
})
