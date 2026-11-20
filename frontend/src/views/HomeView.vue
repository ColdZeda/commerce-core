<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import ProductCard from '../components/ProductCard.vue'
import { CATEGORIES } from '../constants/categories'
import { fetchProducts } from '../api/catalog'
import { claimCoupon, fetchCoupons } from '../api/coupons'
import { useAuthStore } from '../stores/auth'
import { moneyText } from '../utils/money'

const CLAIM_MESSAGES = {
  COUPON_ALREADY_CLAIMED: '你已经领过这张',
  COUPON_SOLD_OUT: '已经被领完了',
  COUPON_NOT_USABLE: '这张券现在不能领',
}

const auth = useAuthStore()
const router = useRouter()

const products = ref([])
const coupons = ref([])
const loading = ref(true)
const claimingId = ref(0)

// 商品总量只有 30 个，一次取回再在本地分组，比"热销/新品/分类计数"各打一次接口简单。
const featured = computed(() => products.value.filter((item) => item.is_featured).slice(0, 8))
const newest = computed(() =>
  products.value
    .filter((item) => !item.is_featured)
    .slice()
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    .slice(0, 8),
)
// 灯箱位给键盘：banner 讲的就是"从一块好键盘开始"，配图得对上文案；优先挑热销里的键盘。
const heroProduct = computed(
  () =>
    products.value.find((item) => item.category === 'keyboard' && item.is_featured) ||
    products.value.find((item) => item.category === 'keyboard') ||
    products.value[0] ||
    null,
)
const spotlights = computed(() =>
  products.value.filter((item) => item.is_featured && item.id !== heroProduct.value?.id).slice(0, 2),
)
const categoryCount = computed(() =>
  CATEGORIES.map((category) => ({
    ...category,
    count: products.value.filter((item) => item.category === category.value).length,
  })),
)

async function load() {
  loading.value = true
  try {
    const [productPage, couponPage] = await Promise.all([
      fetchProducts({ page_size: 50 }),
      fetchCoupons({ page_size: 3 }),
    ])
    products.value = productPage.results
    coupons.value = couponPage.results
  } finally {
    loading.value = false
  }
}

async function claim(coupon) {
  if (!auth.isAuthenticated) {
    router.push({ name: 'login', query: { redirect: '/' } })
    return
  }
  claimingId.value = coupon.id
  try {
    await claimCoupon(coupon.id)
    ElMessage.success('领取成功，去下单时可以用')
    const page = await fetchCoupons({ page_size: 3 })
    coupons.value = page.results
  } catch (error) {
    const code = error?.response?.data?.code
    ElMessage.warning(CLAIM_MESSAGES[code] || '领取失败，请稍后再试')
  } finally {
    claimingId.value = 0
  }
}

onMounted(load)
</script>

<template>
  <div class="wrap">
    <section class="hero">
      <div class="hero-main">
        <div class="hero-copy">
          <span class="hero-eyebrow">桌面焕新季</span>
          <h1>把桌面收拾干净，<br>从一块<b>好键盘</b>开始</h1>
          <p>键盘 / 鼠标 / 耳机 / 显示器 / 支架 / 扩展坞，六大类共 30 款，满 199 减 30。</p>
          <div class="hero-actions">
            <RouterLink
              class="el-button el-button--primary el-button--large"
              to="/products"
            >
              立即选购
            </RouterLink>
            <a
              class="el-button el-button--large"
              href="#coupons"
            >领取优惠券</a>
          </div>
          <div class="hero-stat">
            <span><b>{{ products.length || 30 }}</b>款商品在售</span>
            <span><b>{{ CATEGORIES.length }}</b>个分类</span>
            <span><b>15</b>分钟超时关单</span>
          </div>
        </div>
        <RouterLink
          v-if="heroProduct"
          class="hero-shot"
          :to="{ name: 'product-detail', params: { id: heroProduct.id } }"
        >
          <img
            :src="heroProduct.cover"
            :alt="heroProduct.name"
          >
        </RouterLink>
      </div>

      <div class="hero-side">
        <RouterLink
          v-for="item in spotlights"
          :key="item.id"
          class="side-card"
          :to="{ name: 'product-detail', params: { id: item.id } }"
        >
          <span class="tag">{{ item.category_label }}</span>
          <h3>{{ item.name }}</h3>
          <p>{{ item.subtitle }}</p>
          <strong><small>¥</small>{{ moneyText(item.min_price) }}</strong>
        </RouterLink>
      </div>
    </section>

    <section class="cat-row">
      <RouterLink
        v-for="category in categoryCount"
        :key="category.value"
        class="cat-tile"
        :to="{ name: 'products', query: { category: category.value } }"
      >
        <img
          :src="category.icon"
          :alt="category.label"
        >
        <b>{{ category.label }}</b>
        <small>{{ category.count }} 款在售</small>
      </RouterLink>
    </section>

    <section
      id="coupons"
      class="coupon-row"
    >
      <div
        v-for="coupon in coupons"
        :key="coupon.id"
        class="coupon-chip"
      >
        <span class="coupon-amount"><small>¥</small>{{ moneyText(coupon.discount_amount) }}</span>
        <span class="coupon-text">
          <b>{{ coupon.name }}</b>
          <small>满 ¥{{ moneyText(coupon.threshold_amount) }} 可用 · 剩 {{ coupon.remaining }} 张</small>
        </span>
        <button
          class="coupon-action"
          :disabled="coupon.claimed || coupon.remaining === 0"
          @click="claim(coupon)"
        >
          {{ coupon.claimed ? '已领取' : coupon.remaining === 0 ? '已抢光' : '领取' }}
        </button>
      </div>
    </section>

    <el-skeleton
      v-if="loading"
      class="floor"
      :rows="5"
      animated
    />
    <template v-else>
      <section class="floor">
        <div class="floor-head">
          <h2>热销</h2>
          <RouterLink :to="{ name: 'products' }">
            查看全部 ›
          </RouterLink>
        </div>
        <div class="product-grid">
          <ProductCard
            v-for="item in featured"
            :key="item.id"
            :product="item"
            badge="热销"
          />
        </div>
      </section>

      <section class="floor">
        <div class="floor-head">
          <h2>新品</h2>
          <RouterLink :to="{ name: 'products', query: { ordering: 'created_at' } }">
            查看全部 ›
          </RouterLink>
        </div>
        <div class="product-grid">
          <ProductCard
            v-for="item in newest"
            :key="item.id"
            :product="item"
            badge="新品"
          />
        </div>
      </section>
    </template>

    <section class="service-row">
      <div>
        <span class="service-icon">✓</span>
        <span><b>正品保障</b><small>官方渠道发货</small></span>
      </div>
      <div>
        <span class="service-icon">▤</span>
        <span><b>满 99 包邮</b><small>48 小时内发出</small></span>
      </div>
      <div>
        <span class="service-icon">↺</span>
        <span><b>七天无理由</b><small>不影响二次销售可退</small></span>
      </div>
      <div>
        <span class="service-icon">☎</span>
        <span><b>在线客服</b><small>每天 9:00 - 21:00</small></span>
      </div>
    </section>
  </div>
</template>
