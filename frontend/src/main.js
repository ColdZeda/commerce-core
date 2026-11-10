import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { configureAuth } from './api/client'
import router from './router'
import { useAuthStore } from './stores/auth'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia).use(router).use(ElementPlus)

const auth = useAuthStore(pinia)
configureAuth({
  getAccessToken: () => auth.access,
  refreshAccess: () => auth.refreshAccess(),
  onUnauthorized: () => {
    auth.logout()
    if (router.currentRoute.value.name !== 'login') {
      router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    }
  },
})

// 先恢复会话再挂载，避免刷新页面时页面先闪一下未登录态。
auth.restore().finally(() => app.mount('#app'))
