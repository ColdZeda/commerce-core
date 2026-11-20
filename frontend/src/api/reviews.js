import http from './client'

export function fetchProductReviews(productId, params) {
  return http.get(`/products/${productId}/reviews`, { params }).then((response) => response.data)
}

export function submitOrderReview(orderNo, entries) {
  return http.post(`/orders/${orderNo}/review`, { reviews: entries }).then((response) => response.data)
}
