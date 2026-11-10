import axios from 'axios'

const http = axios.create({ baseURL: '/api/v1', timeout: 10000 })

const AUTH_ENDPOINTS = ['/auth/login', '/auth/refresh']

let bridge = {
  getAccessToken: () => '',
  refreshAccess: async () => '',
  onUnauthorized: () => {},
}
let refreshPromise = null

export function configureAuth(next) {
  bridge = { ...bridge, ...next }
}

function isAuthEndpoint(url = '') {
  return AUTH_ENDPOINTS.some((path) => url.endsWith(path))
}

http.interceptors.request.use((config) => {
  const token = bridge.getAccessToken()
  if (token && !isAuthEndpoint(config.url)) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error
    if (!response || response.status !== 401) {
      return Promise.reject(error)
    }
    // 登录/刷新自身的 401 交给页面处理，重试过的请求也不再刷新，避免死循环。
    if (config?._retried || isAuthEndpoint(config?.url)) {
      return Promise.reject(error)
    }

    config._retried = true
    try {
      // 单飞：并发 401 共用同一次刷新，不把 refresh 打成风暴。
      refreshPromise = refreshPromise || bridge.refreshAccess().finally(() => {
        refreshPromise = null
      })
      const nextAccess = await refreshPromise
      if (!nextAccess) {
        throw new Error('refresh failed')
      }
      config.headers.Authorization = `Bearer ${nextAccess}`
      return http.request(config)
    } catch {
      bridge.onUnauthorized()
      return Promise.reject(error)
    }
  },
)

export default http
