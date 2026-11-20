import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as cartApi from '../api/cart'

export const useCartStore = defineStore('cart', () => {
  const items = ref([])
  const totalQty = ref(0)
  const totalAmount = ref('0.00')
  const selectedQty = ref(0)
  const selectedAmount = ref('0.00')
  const loading = ref(false)

  const count = computed(() => totalQty.value)
  const isEmpty = computed(() => items.value.length === 0)
  const allSelected = computed(() => items.value.length > 0 && items.value.every((item) => item.selected))
  const someSelected = computed(() => items.value.some((item) => item.selected) && !allSelected.value)
  // 勾中的行里有下架或库存不够的，结算按钮要拦住，不然只能等服务端报错。
  const blocked = computed(() =>
    items.value.some((item) => item.selected && !item.available),
  )

  function apply(snapshot) {
    items.value = snapshot.items
    totalQty.value = snapshot.total_qty
    totalAmount.value = snapshot.total_amount
    selectedQty.value = snapshot.selected_qty
    selectedAmount.value = snapshot.selected_amount
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
    apply(await cartApi.updateCartItem(id, { qty }))
  }

  async function setSelected(id, selected) {
    apply(await cartApi.updateCartItem(id, { selected }))
  }

  async function setAllSelected(selected) {
    apply(await cartApi.selectAllCartItems(selected))
  }

  async function remove(id) {
    apply(await cartApi.removeCartItem(id))
  }

  // 退出登录或换账号时必须清空，否则会把上一个人的车显示给下一个人。
  function reset() {
    items.value = []
    totalQty.value = 0
    totalAmount.value = '0.00'
    selectedQty.value = 0
    selectedAmount.value = '0.00'
  }

  return {
    items,
    totalQty,
    totalAmount,
    selectedQty,
    selectedAmount,
    loading,
    count,
    isEmpty,
    allSelected,
    someSelected,
    blocked,
    load,
    add,
    updateQty,
    setSelected,
    setAllSelected,
    remove,
    reset,
  }
})
