import http from './client'

export function login(payload) {
  return http.post('/auth/login', payload).then((response) => response.data)
}

export function refresh(refreshToken) {
  return http.post('/auth/refresh', { refresh: refreshToken }).then((response) => response.data)
}

export function me() {
  return http.get('/auth/me').then((response) => response.data)
}
