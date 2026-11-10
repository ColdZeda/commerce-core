import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '../views/HomeView.vue'

// S0 只放自检页；四个业务路由按 plan §8 在 S1/S2 落地，避免提前定契约。
const routes = [{ path: '/', name: 'home', component: HomeView }]

export default createRouter({
  history: createWebHistory(),
  routes,
})
