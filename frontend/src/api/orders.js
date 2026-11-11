import http from './client'

export function createOrder(payload) {
  return http.post('/orders', payload).then((response) => ({
    order: response.data,
    // 同一 client_token 的重放不会新建订单，页面要把这件事告诉用户。
    replayed: response.headers['x-idempotent-replay'] === '1',
  }))
}

export function fetchOrders(params) {
  return http.get('/orders', { params }).then((response) => response.data)
}

export function fetchOrder(orderNo) {
  return http.get(`/orders/${orderNo}`).then((response) => response.data)
}

export function cancelOrder(orderNo, reason) {
  return http.post(`/orders/${orderNo}/cancel`, { reason }).then((response) => response.data)
}

export function payOrder(orderNo) {
  return http.post(`/orders/${orderNo}/pay`).then((response) => ({
    order: response.data,
    replayed: response.headers['x-idempotent-replay'] === '1',
  }))
}
