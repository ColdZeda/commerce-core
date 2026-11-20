import http from './client'

/** 三个写接口都返回整车快照，store 直接整体替换，不做增量合并。 */
export function fetchCart() {
  return http.get('/cart/items').then((response) => response.data)
}

export function addCartItem(skuId, qty = 1) {
  return http.post('/cart/items', { sku_id: skuId, qty }).then((response) => response.data)
}

export function updateCartItem(id, patch) {
  return http.patch(`/cart/items/${id}`, patch).then((response) => response.data)
}

export function selectAllCartItems(selected) {
  return http.patch('/cart/items', { selected }).then((response) => response.data)
}

export function removeCartItem(id) {
  return http.delete(`/cart/items/${id}`).then((response) => response.data)
}
