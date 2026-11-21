<script setup>
import { ElMessage } from 'element-plus'
import { ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { CATEGORIES } from './constants/categories'
import { useAuthStore } from './stores/auth'
import { useCartStore } from './stores/cart'

const auth = useAuthStore()
const cart = useCartStore()
const router = useRouter()
const route = useRoute()

const keyword = ref(typeof route.query.keyword === 'string' ? route.query.keyword : '')

// 登录态变化就重取整车：刷新页面能恢复件数，换账号不会看到上一个人的车。
watch(
  () => auth.isAuthenticated,
  (loggedIn) => {
    if (loggedIn) {
      cart.load().catch(() => cart.reset())
    } else {
      cart.reset()
    }
  },
  { immediate: true },
)

function search() {
  router.push({ name: 'products', query: keyword.value ? { keyword: keyword.value } : {} })
}

function logout() {
  auth.logout()
  ElMessage.info('已退出登录')
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="shell">
    <div class="topstrip">
      <div class="wrap topstrip-in">
        <span v-if="auth.isAuthenticated">你好，{{ auth.user?.username }}</span>
        <span v-else>你好，欢迎来到 commerce-core</span>
        <nav class="topstrip-links">
          <RouterLink
            v-if="auth.isAuthenticated"
            to="/orders"
          >
            我的订单
          </RouterLink>
          <a
            v-if="auth.isAuthenticated"
            @click="logout"
          >退出登录</a>
          <template v-else>
            <RouterLink
              to="/login"
              class="strong-link"
            >
              登录
            </RouterLink>
            <RouterLink
              to="/register"
              class="strong-link"
            >
              注册
            </RouterLink>
          </template>
          <span class="sep" />
          <RouterLink to="/audit">
            对账看板
          </RouterLink>
          <span>客服 9:00 - 21:00</span>
        </nav>
      </div>
    </div>

    <header class="site-header">
      <div class="wrap site-header-in">
        <RouterLink
          class="brand"
          to="/"
        >
          <span class="brand-mark">c</span>
          <span class="brand-text">commerce<em>-core</em></span>
        </RouterLink>
        <form
          class="site-search"
          @submit.prevent="search"
        >
          <input
            v-model="keyword"
            placeholder="搜索 键盘 / 鼠标 / 耳机 / 扩展坞…"
          >
          <button type="submit">
            搜索
          </button>
        </form>
        <RouterLink
          class="header-cart"
          to="/cart"
        >
          <span>购物车</span>
          <span
            v-if="cart.count"
            class="cart-badge"
          >{{ cart.count }}</span>
        </RouterLink>
      </div>
    </header>

    <nav class="site-nav">
      <div class="wrap site-nav-in">
        <RouterLink
          to="/"
          :class="{ on: route.path === '/' }"
        >
          首页
        </RouterLink>
        <RouterLink
          to="/products"
          :class="{ on: route.path === '/products' && !route.query.category }"
        >
          全部商品
        </RouterLink>
        <RouterLink
          v-for="category in CATEGORIES"
          :key="category.value"
          :to="{ name: 'products', query: { category: category.value } }"
          :class="{ on: route.query.category === category.value }"
        >
          {{ category.label }}
        </RouterLink>
        <span class="nav-note">30 天价保 · 七天无理由</span>
      </div>
    </nav>

    <main class="shell-main">
      <RouterView />
    </main>

    <footer class="site-footer">
      <div class="wrap footer-cols">
        <div>
          <h4>购物指南</h4>
          <a>购物流程</a><a>会员介绍</a><a>常见问题</a><a>联系客服</a>
        </div>
        <div>
          <h4>配送方式</h4>
          <a>上门自提</a><a>配送范围</a><a>运费说明</a>
        </div>
        <div>
          <h4>支付方式</h4>
          <a>在线支付</a><a>优惠券使用</a><a>发票说明</a>
        </div>
        <div>
          <h4>售后服务</h4>
          <a>退款说明</a><a>取消订单</a><a>价格保护</a>
        </div>
        <div class="footer-note">
          <b>commerce-core</b>
          <p>演示项目：下单、支付、取消、退款、超时关单都是真实链路，但不产生真实交易，也不发货。</p>
        </div>
      </div>
      <div class="footer-bar">
        <div class="wrap">
          <span>© 2026 commerce-core</span>
          <span>Django · MySQL · Redis · Celery · Vue</span>
        </div>
      </div>
    </footer>
  </div>
</template>
