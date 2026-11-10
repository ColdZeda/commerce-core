<script setup>
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

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
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/products'
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
    <el-card class="auth-card">
      <template #header>
        <h2>登录</h2>
      </template>
      <el-form
        label-position="top"
        @submit.prevent="submit"
      >
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-alert
          v-if="errorMessage"
          type="error"
          :closable="false"
          :title="errorMessage"
        />
        <el-button
          type="primary"
          native-type="submit"
          :loading="submitting"
          class="auth-submit"
        >
          登录
        </el-button>
      </el-form>
    </el-card>
  </section>
</template>
