<script setup>
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { fetchProducts } from '../api/catalog'
import { claimCoupon, fetchCoupons } from '../api/coupons'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const products = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, page_size: 6, keyword: '', ordering: '-created_at' })

const coupons = ref([])
const claimingId = ref(0)

const ORDERING_OPTIONS = [
  { label: '最新', value: '-created_at' },
  { label: '价格从低到高', value: 'price' },
  { label: '价格从高到低', value: '-price' },
]

const CLAIM_MESSAGES = {
  COUPON_ALREADY_CLAIMED: '你已经领过这张',
  COUPON_SOLD_OUT: '已经被领完了',
  COUPON_NOT_USABLE: '这张券现在不能领',
}

async function loadProducts() {
  loading.value = true
  try {
    const data = await fetchProducts({
      page: query.page,
      page_size: query.page_size,
      ordering: query.ordering,
      keyword: query.keyword || undefined,
    })
    products.value = data.results
    total.value = data.count
  } finally {
    loading.value = false
  }
}

async function loadCoupons() {
  const data = await fetchCoupons({ page_size: 5 })
  coupons.value = data.results
}

function onSearch() {
  query.page = 1
  loadProducts()
}

function onPageChange(page) {
  query.page = page
  loadProducts()
}

async function claim(coupon) {
  if (!auth.isAuthenticated) {
    router.push({ name: 'login', query: { redirect: '/products' } })
    return
  }

  claimingId.value = coupon.id
  try {
    await claimCoupon(coupon.id)
    ElMessage.success('领取成功')
    await loadCoupons()
  } catch (error) {
    const code = error?.response?.data?.code
    ElMessage.warning(CLAIM_MESSAGES[code] || '领取失败，请稍后再试')
  } finally {
    claimingId.value = 0
  }
}

onMounted(() => {
  loadProducts()
  loadCoupons()
})
</script>

<template>
  <main class="page">
    <section class="coupons">
      <h2>可领优惠券</h2>
      <div
        v-if="coupons.length"
        class="coupon-grid"
      >
        <el-card
          v-for="coupon in coupons"
          :key="coupon.id"
          shadow="never"
          class="coupon-card"
        >
          <div class="coupon-main">
            <strong>{{ coupon.name }}</strong>
            <span class="coupon-threshold">满 ¥{{ coupon.threshold_amount }} 可用</span>
            <span class="coupon-left">剩 {{ coupon.remaining }} 张</span>
          </div>
          <el-button
            type="primary"
            size="small"
            :loading="claimingId === coupon.id"
            :disabled="coupon.claimed || coupon.remaining === 0"
            @click="claim(coupon)"
          >
            {{ coupon.claimed ? '已领取' : coupon.remaining === 0 ? '已抢光' : '领取' }}
          </el-button>
        </el-card>
      </div>
      <el-empty
        v-else
        description="暂时没有可领的券"
      />
    </section>

    <section class="catalog">
      <div class="catalog-toolbar">
        <h2>商品</h2>
        <el-input
          v-model="query.keyword"
          placeholder="搜商品名"
          clearable
          class="catalog-search"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
        <el-select
          v-model="query.ordering"
          class="catalog-order"
          @change="onSearch"
        >
          <el-option
            v-for="item in ORDERING_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button @click="onSearch">
          搜索
        </el-button>
      </div>

      <el-skeleton
        v-if="loading"
        :rows="4"
        animated
      />
      <template v-else>
        <el-empty
          v-if="!products.length"
          description="没有匹配的商品"
        />
        <div
          v-else
          class="product-grid"
        >
          <RouterLink
            v-for="product in products"
            :key="product.id"
            :to="{ name: 'product-detail', params: { id: product.id } }"
            class="product-link"
          >
            <el-card
              shadow="hover"
              class="product-card"
            >
              <h3>{{ product.name }}</h3>
              <p class="product-subtitle">
                {{ product.subtitle }}
              </p>
              <p class="product-price">
                ¥{{ product.min_price ?? '—' }}
              </p>
            </el-card>
          </RouterLink>
        </div>

        <el-pagination
          v-if="total > query.page_size"
          class="catalog-pagination"
          layout="prev, pager, next"
          :total="total"
          :page-size="query.page_size"
          :current-page="query.page"
          @current-change="onPageChange"
        />
      </template>
    </section>
  </main>
</template>
