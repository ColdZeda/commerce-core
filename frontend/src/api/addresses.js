import http from './client'

export function fetchAddresses() {
  return http.get('/addresses').then((response) => response.data)
}

export function createAddress(payload) {
  return http.post('/addresses', payload).then((response) => response.data)
}

export function updateAddress(id, payload) {
  return http.patch(`/addresses/${id}`, payload).then((response) => response.data)
}

export function deleteAddress(id) {
  return http.delete(`/addresses/${id}`)
}
