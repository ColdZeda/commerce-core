import http from './client'

export function fetchCoupons(params) {
  return http.get('/coupons', { params }).then((response) => response.data)
}

export function claimCoupon(id) {
  return http.post(`/coupons/${id}/claim`).then((response) => response.data)
}
