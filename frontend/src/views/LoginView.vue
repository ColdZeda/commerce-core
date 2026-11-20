<script setup>
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const submitting = ref(false)
const errorMessage = ref('')

async function submit() {
  errorMessage.value = ''
  if (!form.username || !form.password) {
    errorMessage.value = '用户名和密码都要填'
    return
  }

  submitting.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (error) {
    const code = error?.response?.data?.code
    errorMessage.value = code === 'AUTH_INVALID_CREDENTIALS' ? '用户名或密码不对' : '登录失败，请稍后再试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="auth-page">
    <aside class="auth-aside">
      <h1>登录之后，<br>订单和券都在一个地方</h1>
      <p>下单、支付、取消、退款都走同一条链路；每张券的领取与使用都能查到记录。</p>
      <div class="auth-points">
        <span>新客立减 5 元</span>
        <span>满 199 减 30</span>
        <span>15 分钟超时关单</span>
      </div>
    </aside>

    <div class="auth-card">
      <h2>登录</h2>
      <p class="auth-lead">
        还没有账号？<RouterLink to="/register">
          注册一个
        </RouterLink>
      </p>
      <el-form
        label-position="top"
        @submit.prevent="submit"
      >
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            autocomplete="username"
            size="large"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            size="large"
          />
        </el-form-item>
        <el-alert
          v-if="errorMessage"
          type="error"
          :closable="false"
          :title="errorMessage"
          style="margin-bottom: 12px"
        />
        <el-button
          type="primary"
          native-type="submit"
          size="large"
          :loading="submitting"
          class="auth-submit"
        >
          登录
        </el-button>
      </el-form>
    </div>
  </section>
</template>
