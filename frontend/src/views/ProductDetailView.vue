<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchProduct } from '../api/catalog'
import { fetchMyCoupons } from '../api/coupons'
import { createOrder } from '../api/orders'
import { useAuthStore } from '../stores/auth'
import { newClientToken } from '../utils/clientToken'

const ORDER_ERRORS = {
  STOCK_NOT_ENOUGH: '库存不足，换个数量或规格试试',
  PRODUCT_OFF_SHELF: '这个商品已下架',
  COUPON_NOT_USABLE: '这张券现在用不了',
  VALIDATION_ERROR: '提交的内容有问题，检查一下数量和券',
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const product = ref(null)
const loading = ref(true)
const submitting = ref(false)
const coupons = ref([])
const clientToken = ref(newClientToken())

const form = reactive({ skuId: null, qty: 1, userCouponId: null, remark: '' })

const selectedSku = computed(() => product.value?.skus.find((sku) => sku.id === form.skuId) || null)
const maxQty = computed(() => Math.min(selectedSku.value?.stock ?? 1, 999))
const total = computed(() => Number(selectedSku.value?.price ?? 0) * form.qty)
const selectedCoupon = computed(() => coupons.value.find((item) => item.id === form.userCouponId) || null)
// 券面额可能大于订单金额，应付最多减到 0，和 /orders 接口的口径一致。
const discount = computed(() =>
  selectedCoupon.value ? Math.min(Number(selectedCoupon.value.coupon.discount_amount), total.value) : 0,
)
const payable = computed(() => Math.max(total.value - discount.value, 0))

function money(value) {
  return Number(value).toFixed(2)
}

function couponLabel(item) {
  return `满 ${item.coupon.threshold_amount} 减 ${item.coupon.discount_amount}`
}

function couponUsable(item) {
  return Number(item.coupon.threshold_amount) <= total.value
}

async function load() {
  loading.value = true
  try {
    product.value = await fetchProduct(route.params.id)
    form.skuId = product.value.skus.find((sku) => sku.stock > 0)?.id ?? product.value.skus[0]?.id ?? null
  } catch {
    ElMessage.warning('商品不存在或已下架')
    router.replace({ name: 'products' })
  } finally {
    loading.value = false
  }
}

async function loadCoupons() {
  if (!auth.isAuthenticated) {
    return
  }
  const data = await fetchMyCoupons({ status: 'unused', page_size: 50 })
  coupons.value = data.results
}

async function submit() {
  if (!auth.isAuthenticated) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  if (!selectedSku.value) {
    ElMessage.warning('先选一个规格')
    return
  }

  submitting.value = true
  try {
    const { order, replayed } = await createOrder({
      items: [{ sku_id: form.skuId, qty: form.qty }],
      user_coupon_id: form.userCouponId || undefined,
      client_token: clientToken.value,
      remark: form.remark || undefined,
    })
    clientToken.value = newClientToken()
    ElMessage.success(replayed ? '这一单刚才已经提交过，为你打开原订单' : '下单成功，请在 15 分钟内处理')
    router.push({ name: 'orders', query: { order: order.order_no } })
  } catch (error) {
    const code = error?.response?.data?.code
    ElMessage.warning(ORDER_ERRORS[code] || '下单失败，请稍后再试')
  } finally {
    submitting.value = false
  }
}

// 换规格或加数量后，原来选的券可能不够门槛，直接清掉比提交时再报错好。
watch([selectedSku, () => form.qty], () => {
  if (form.qty > maxQty.value) {
    form.qty = maxQty.value
  }
  if (selectedCoupon.value && !couponUsable(selectedCoupon.value)) {
    form.userCouponId = null
  }
})

onMounted(() => {
  load()
  loadCoupons()
})
</script>

<template>
  <main class="page">
    <el-skeleton
      v-if="loading"
      :rows="6"
      animated
    />
    <div
      v-else-if="product"
      class="detail-layout"
    >
      <section class="detail-main">
        <h1>{{ product.name }}</h1>
        <p class="product-subtitle">
          {{ product.subtitle }}
        </p>
        <p
          v-if="product.description"
          class="detail-desc"
        >
          {{ product.description }}
        </p>

        <h2>选择规格</h2>
        <el-radio-group v-model="form.skuId">
          <el-radio-button
            v-for="sku in product.skus"
            :key="sku.id"
            :value="sku.id"
            :disabled="sku.stock === 0"
          >
            {{ sku.title }} ¥{{ sku.price }}（库存 {{ sku.stock }}）
          </el-radio-button>
        </el-radio-group>

        <div class="detail-qty">
          <span>数量</span>
          <el-input-number
            v-model="form.qty"
            :min="1"
            :max="maxQty"
          />
        </div>

        <el-form label-position="top">
          <el-form-item label="优惠券">
            <el-select
              v-model="form.userCouponId"
              clearable
              placeholder="不使用优惠券"
              class="detail-coupon"
            >
              <el-option
                v-for="item in coupons"
                :key="item.id"
                :label="couponLabel(item)"
                :value="item.id"
                :disabled="!couponUsable(item)"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input
              v-model="form.remark"
              maxlength="200"
              show-word-limit
              placeholder="选填"
            />
          </el-form-item>
        </el-form>
      </section>

      <aside class="detail-summary">
        <el-descriptions
          :column="1"
          border
        >
          <el-descriptions-item label="商品金额">
            ¥{{ money(total) }}
          </el-descriptions-item>
          <el-descriptions-item label="优惠">
            -¥{{ money(discount) }}
          </el-descriptions-item>
          <el-descriptions-item label="应付">
            <strong class="money">¥{{ money(payable) }}</strong>
          </el-descriptions-item>
        </el-descriptions>
        <el-button
          type="primary"
          size="large"
          :loading="submitting"
          :disabled="!selectedSku || selectedSku.stock === 0"
          class="detail-submit"
          @click="submit"
        >
          {{ auth.isAuthenticated ? '提交订单' : '登录后下单' }}
        </el-button>
        <p class="detail-hint">
          订单 15 分钟内未支付会被关闭
        </p>
      </aside>
    </div>
  </main>
</template>
