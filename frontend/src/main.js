import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
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

// 组件自带的文案（确认框按钮、空状态等）跟着界面走中文。
app.use(pinia).use(router).use(ElementPlus, { locale: zhCn })

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
