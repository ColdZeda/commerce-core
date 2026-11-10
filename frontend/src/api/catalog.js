import http from './client'

export function fetchProducts(params) {
  return http.get('/products', { params }).then((response) => response.data)
}
