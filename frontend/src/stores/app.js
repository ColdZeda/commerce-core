import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const probeCount = ref(0)

  function countProbe() {
    probeCount.value += 1
  }

  return { probeCount, countProbe }
})
