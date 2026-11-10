<script setup>
import { ElMessage } from 'element-plus'
import { RouterLink, RouterView, useRouter } from 'vue-router'

import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  ElMessage.info('已退出登录')
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="topbar">
    <RouterLink
      class="brand"
      to="/products"
    >commerce-core</RouterLink>
    <div class="account">
      <span
        v-if="auth.isAuthenticated"
        class="account-name"
      >{{ auth.user?.username || '已登录' }}</span>
      <el-button
        v-if="auth.isAuthenticated"
        link
        type="primary"
        @click="logout"
      >
        退出
      </el-button>
      <RouterLink
        v-else
        to="/login"
      >登录</RouterLink>
    </div>
  </header>

  <RouterView />
</template>
