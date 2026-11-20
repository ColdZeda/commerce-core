import http from './client'

export function fetchAudit() {
  return http.get('/audit').then((response) => response.data)
}
