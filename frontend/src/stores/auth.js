import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as authApi from '../api/auth'

const ACCESS_KEY = 'commerce.access'
const REFRESH_KEY = 'commerce.refresh'

export const useAuthStore = defineStore('auth', () => {
  const access = ref(localStorage.getItem(ACCESS_KEY) || '')
  const refreshToken = ref(localStorage.getItem(REFRESH_KEY) || '')
  const user = ref(null)
  const isAuthenticated = computed(() => Boolean(access.value))

  function persist() {
    localStorage.setItem(ACCESS_KEY, access.value)
    localStorage.setItem(REFRESH_KEY, refreshToken.value)
  }

  function clear() {
    access.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  }

  async function login(username, password) {
    const data = await authApi.login({ username, password })
    access.value = data.access
    refreshToken.value = data.refresh
    user.value = data.user
    persist()
  }

  async function refreshAccess() {
    if (!refreshToken.value) {
      return ''
    }
    const data = await authApi.refresh(refreshToken.value)
    access.value = data.access
    persist()
    return data.access
  }

  // 刷新页面后凭已存的 access 恢复会话；失败就直接清掉，不要留半登录状态。
  async function restore() {
    if (!access.value) {
      return
    }
    try {
      user.value = await authApi.me()
    } catch {
      clear()
    }
  }

  function logout() {
    clear()
  }

  return { access, refreshToken, user, isAuthenticated, login, refreshAccess, restore, logout }
})
