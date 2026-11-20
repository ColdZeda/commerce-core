<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { fetchAddresses } from '../api/addresses'

const props = defineProps({
  modelValue: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue'])

const addresses = ref([])
const loading = ref(true)

function label(address) {
  return `${address.receiver} ${address.phone} ${address.region}${address.detail}`
}

async function load() {
  loading.value = true
  try {
    const data = await fetchAddresses()
    addresses.value = data.items
    // 还没选过就落到默认地址，省一次点击；没有地址则保持空，由外层拦住结算。
    if (!props.modelValue && data.items.length) {
      emit('update:modelValue', (data.items.find((item) => item.is_default) || data.items[0]).id)
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
defineExpose({ reload: load })
</script>

<template>
  <div class="addr-picker">
    <el-select
      :model-value="modelValue"
      :loading="loading"
      placeholder="选择收货地址"
      class="addr-select"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <el-option
        v-for="address in addresses"
        :key="address.id"
        :value="address.id"
        :label="label(address)"
      />
    </el-select>
    <RouterLink
      class="addr-manage"
      to="/addresses"
    >
      管理地址
    </RouterLink>
  </div>
  <p
    v-if="!loading && !addresses.length"
    class="addr-empty"
  >
    还没有收货地址，<RouterLink to="/addresses">
      去添加一个
    </RouterLink>
  </p>
</template>
