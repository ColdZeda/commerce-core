<script setup>
import { RouterLink } from 'vue-router'

import { moneyText } from '../utils/money'

defineProps({
  product: { type: Object, required: true },
  badge: { type: String, default: '' },
})
</script>

<template>
  <RouterLink
    class="pcard"
    :to="{ name: 'product-detail', params: { id: product.id } }"
  >
    <div class="pcard-thumb">
      <span
        v-if="badge"
        class="pcard-badge"
        :class="{ new: badge === '新品' }"
      >{{ badge }}</span>
      <img
        v-if="product.cover"
        :src="product.cover"
        :alt="product.name"
        loading="lazy"
      >
    </div>
    <div class="pcard-body">
      <h3>{{ product.name }}</h3>
      <p class="pcard-sub">
        {{ product.subtitle }}
      </p>
      <div class="pcard-foot">
        <span class="price"><small>¥</small>{{ moneyText(product.min_price) }}</span>
        <span
          class="pcard-add"
          title="进详情选规格后加购"
        >+</span>
      </div>
    </div>
  </RouterLink>
</template>
