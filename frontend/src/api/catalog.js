import http from './client'

export function fetchProducts(params) {
  return http.get('/products', { params }).then((response) => response.data)
}

export function fetchProduct(id) {
  return http.get(`/products/${id}`).then((response) => response.data)
}
