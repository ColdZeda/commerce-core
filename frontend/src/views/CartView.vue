<script setup>
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { createOrder } from '../api/orders'
import { useAuthStore } from '../stores/auth'
import { useCartStore } from '../stores/cart'
import { newClientToken } from '../utils/clientToken'
import { moneyText } from '../utils/money'

const ORDER_ERRORS = {
  CART_EMPTY: '购物车是空的',
  CART_TOO_MANY_LINES: '一单最多 20 个 SKU',
  STOCK_NOT_ENOUGH: '有商品库存不足，先减数量或删掉',
  PRODUCT_OFF_SHELF: '有商品已下架，删掉再结算',
  COUPON_NOT_USABLE: '这张券现在用不了',
}

const auth = useAuthStore()
const cart = useCartStore()
const router = useRouter()

const submitting = ref(false)
// 进页面生成一次；提交成功换新的，失败保留，让重试能被识别成重放。
const clientToken = ref(newClientToken())

const hasUnavailable = computed(() => cart.blocked)

async function changeQty(item, qty) {
  if (qty < 1) {
    return
  }
  try {
    await cart.updateQty(item.id, qty)
  } catch (error) {
    const code = error?.response?.data?.code
    ElMessage.warning(ORDER_ERRORS[code] || '改数量失败')
    await cart.load()
  }
}

async function toggle(item, selected) {
  try {
    await cart.setSelected(item.id, selected)
  } catch {
    await cart.load()
  }
}

async function toggleAll(selected) {
  try {
    await cart.setAllSelected(selected)
  } catch {
    await cart.load()
  }
}

async function remove(item) {
  try {
    await cart.remove(item.id)
    ElMessage.success('已移出购物车')
  } catch {
    ElMessage.warning('删除失败，请稍后再试')
  }
}

async function checkout() {
  if (!auth.isAuthenticated) {
    router.push({ name: 'login', query: { redirect: '/cart' } })
    return
  }
  submitting.value = true
  try {
    const { order, replayed } = await createOrder({
      from_cart: true,
      client_token: clientToken.value,
    })
    clientToken.value = newClientToken()
    await cart.load()
    ElMessage.success(replayed ? '这一单刚才已经提交过，为你打开原订单' : '下单成功，请在 15 分钟内处理')
    router.push({ name: 'orders', query: { order: order.order_no } })
  } catch (error) {
    const code = error?.response?.data?.code
    ElMessage.warning(ORDER_ERRORS[code] || '下单失败，请稍后再试')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="wrap">
    <div class="cart-head">
      <h1>购物车</h1>
      <span class="cart-sub">{{ cart.totalQty }} 件商品</span>
    </div>

    <el-skeleton
      v-if="cart.loading && cart.isEmpty"
      :rows="4"
      animated
    />

    <el-empty
      v-else-if="cart.isEmpty"
      description="购物车是空的"
    >
      <RouterLink
        class="el-button el-button--primary"
        to="/products"
      >
        去逛逛
      </RouterLink>
    </el-empty>

    <template v-else>
      <div class="cart-list">
        <div class="cart-row cart-row-head">
          <span class="cart-check">
            <el-checkbox
              :model-value="cart.allSelected"
              :indeterminate="cart.someSelected"
              @change="toggleAll"
            />
            <span>全选</span>
          </span>
          <span>商品</span>
          <span>单价</span>
          <span>数量</span>
          <span>小计</span>
          <span />
        </div>
        <div
          v-for="item in cart.items"
          :key="item.id"
          class="cart-row"
          :class="{ off: !item.available, dim: !item.selected }"
        >
          <span class="cart-check">
            <el-checkbox
              :model-value="item.selected"
              :disabled="!item.available"
              @change="(value) => toggle(item, value)"
            />
          </span>
          <div class="cart-product">
            <RouterLink
              class="cart-thumb"
              :to="{ name: 'product-detail', params: { id: item.product_id } }"
            >
              <img
                :src="item.cover"
                :alt="item.product_name"
              >
            </RouterLink>
            <div>
              <RouterLink
                class="cart-name"
                :to="{ name: 'product-detail', params: { id: item.product_id } }"
              >
                {{ item.product_name }}
              </RouterLink>
              <p class="cart-sku">
                {{ item.sku_title }} · {{ item.sku_code }}
              </p>
              <p
                v-if="!item.available"
                class="cart-warn"
              >
                已下架或库存不足
              </p>
            </div>
          </div>
          <span class="cart-price">¥{{ moneyText(item.price) }}</span>
          <div>
            <el-input-number
              :model-value="item.qty"
              :min="1"
              :max="Math.min(item.stock, 999)"
              :disabled="!item.available"
              size="small"
              @change="(value) => changeQty(item, value)"
            />
          </div>
          <span class="cart-subtotal">¥{{ moneyText(item.subtotal) }}</span>
          <button
            class="cart-remove"
            @click="remove(item)"
          >
            删除
          </button>
        </div>
      </div>

      <div class="cart-summary">
        <span class="cart-total">
          已选 {{ cart.selectedQty }} 件，合计
          <strong class="money">¥{{ moneyText(cart.selectedAmount) }}</strong>
        </span>
        <el-button
          type="primary"
          size="large"
          :loading="submitting"
          :disabled="hasUnavailable || cart.selectedQty === 0"
          @click="checkout"
        >
          {{ hasUnavailable ? '先取消勾选不可售商品' : '去结算' }}
        </el-button>
      </div>
    </template>
  </div>
</template>
