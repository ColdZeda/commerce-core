import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as cartApi from '../api/cart'

export const useCartStore = defineStore('cart', () => {
  const items = ref([])
  const totalQty = ref(0)
  const totalAmount = ref('0.00')
  const loading = ref(false)

  const count = computed(() => totalQty.value)
  const isEmpty = computed(() => items.value.length === 0)

  function apply(snapshot) {
    items.value = snapshot.items
    totalQty.value = snapshot.total_qty
    totalAmount.value = snapshot.total_amount
  }

  async function load() {
    loading.value = true
    try {
      apply(await cartApi.fetchCart())
    } finally {
      loading.value = false
    }
  }

  async function add(skuId, qty = 1) {
    apply(await cartApi.addCartItem(skuId, qty))
  }

  async function updateQty(id, qty) {
    apply(await cartApi.updateCartItem(id, qty))
  }

  async function remove(id) {
    apply(await cartApi.removeCartItem(id))
  }

  // 退出登录或换账号时必须清空，否则会把上一个人的车显示给下一个人。
  function reset() {
    items.value = []
    totalQty.value = 0
    totalAmount.value = '0.00'
  }

  return { items, totalQty, totalAmount, loading, count, isEmpty, load, add, updateQty, remove, reset }
})
