<script setup>
import axios from 'axios'
import { ref } from 'vue'

import { useAppStore } from '../stores/app'

const store = useAppStore()
const result = ref(null)
const error = ref('')

async function probe() {
  error.value = ''
  store.countProbe()
  try {
    const { status, data } = await axios.get('/api/v1/health')
    result.value = { httpStatus: status, ...data }
  } catch (err) {
    result.value = null
    error.value = err.message
  }
}
</script>

<template>
  <main class="page">
    <h1>commerce-core</h1>
    <p>S0 骨架自检：Vite + Vue 3 + Vue Router + Pinia + axios + Element Plus</p>

    <el-space
      direction="vertical"
      alignment="start"
      :size="16"
    >
      <el-button
        type="primary"
        @click="probe"
      >
        请求 /api/v1/health
      </el-button>
      <el-text>已探测 {{ store.probeCount }} 次</el-text>
      <el-alert
        v-if="result"
        type="success"
        :closable="false"
        title="后端健康"
        :description="JSON.stringify(result)"
      />
      <el-alert
        v-if="error"
        type="error"
        :closable="false"
        title="请求失败"
        :description="error"
      />
    </el-space>
  </main>
</template>
