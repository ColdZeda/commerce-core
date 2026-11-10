import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import ProductsView from '../views/ProductsView.vue'

// 商品列表与详情、订单页在 S3 补齐；这里只放 S2 需要的两个入口。
const routes = [
  { path: '/', redirect: '/products' },
  { path: '/login', name: 'login', component: LoginView },
  { path: '/products', name: 'products', component: ProductsView },
  { path: '/:pathMatch(.*)*', redirect: '/products' },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
