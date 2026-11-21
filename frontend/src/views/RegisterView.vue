<script setup>
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({ username: '', password: '', passwordConfirm: '' })
const submitting = ref(false)
const errorMessage = ref('')

// 后端把字段错误放在 detail 里，取第一条就够表单用，全部堆出来反而看不清。
function firstError(detail) {
  if (!detail || typeof detail !== 'object') {
    return ''
  }
  for (const messages of Object.values(detail)) {
    if (Array.isArray(messages) && messages.length) {
      return String(messages[0])
    }
    if (typeof messages === 'string') {
      return messages
    }
  }
  return ''
}

async function submit() {
  errorMessage.value = ''
  if (!form.username || !form.password) {
    errorMessage.value = '用户名和密码都要填'
    return
  }
  if (form.password !== form.passwordConfirm) {
    errorMessage.value = '两次输入的密码不一致'
    return
  }

  submitting.value = true
  try {
    await auth.register(form.username, form.password, form.passwordConfirm)
    ElMessage.success('注册成功，新人券已经放进账户')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (error) {
    const body = error?.response?.data
    errorMessage.value = firstError(body?.detail) || '注册失败，请稍后再试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="auth-page">
    <aside class="auth-aside">
      <h1>注册就送<br>一张新人券</h1>
      <p>填用户名和密码即可，不需要邮箱验证。注册成功直接是登录状态，可以马上下单。</p>
      <div class="auth-points">
        <span>新客满 49 减 5</span>
        <span>不绑手机</span>
        <span>随时可退</span>
      </div>
    </aside>

    <div class="auth-card">
      <h2>注册</h2>
      <p class="auth-lead">
        已经有账号？<RouterLink to="/login">
          直接登录
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
            placeholder="字母、数字或下划线，最长 150 位"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="new-password"
            size="large"
            placeholder="请输入密码"
          />
          <!-- 占位符一打字就看不见了，规则得常驻在下面，否则只会在提交后被告知"太常见"。 -->
          <p class="auth-hint">
            至少 8 位；不能全是数字；不能与用户名太相似；别用 testtest、password 这类常见词。
          </p>
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="form.passwordConfirm"
            type="password"
            show-password
            autocomplete="new-password"
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
          注册并登录
        </el-button>
      </el-form>
    </div>
  </section>
</template>
