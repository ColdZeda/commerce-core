<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchProductReviews } from '../api/reviews'

const props = defineProps({
  productId: { type: [Number, String], required: true },
})

const PAGE_SIZE = 5

const reviews = ref([])
const total = ref(0)
const summary = ref({ count: 0, average: null })
const page = ref(1)
const loading = ref(true)

const hasMore = computed(() => reviews.value.length < total.value)

async function load(reset = false) {
  loading.value = true
  try {
    const data = await fetchProductReviews(props.productId, { page: page.value, page_size: PAGE_SIZE })
    reviews.value = reset ? data.results : [...reviews.value, ...data.results]
    total.value = data.count
    summary.value = data.summary
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  page.value += 1
  await load()
}

function formatTime(value) {
  return value ? new Date(value).toLocaleDateString('zh-CN') : ''
}

onMounted(() => load(true))
</script>

<template>
  <section class="reviews">
    <div class="reviews-head">
      <h2>评价</h2>
      <span
        v-if="summary.count"
        class="reviews-score"
      >
        <el-rate
          :model-value="summary.average"
          disabled
          allow-half
          size="small"
        />
        <b>{{ summary.average }}</b>
        <small>{{ summary.count }} 条</small>
      </span>
      <span
        v-else
        class="reviews-score"
      >暂无评价</span>
    </div>

    <p
      v-if="!loading && !reviews.length"
      class="reviews-empty"
    >
      买过的人还没留下评价。
    </p>

    <ul
      v-else
      class="reviews-list"
    >
      <li
        v-for="review in reviews"
        :key="review.id"
      >
        <div class="review-top">
          <span class="review-user">{{ review.username }}</span>
          <el-rate
            :model-value="review.rating"
            disabled
            size="small"
          />
          <span class="review-date">{{ formatTime(review.created_at) }}</span>
        </div>
        <p
          v-if="review.content"
          class="review-text"
        >
          {{ review.content }}
        </p>
      </li>
    </ul>

    <el-button
      v-if="hasMore"
      text
      type="primary"
      :loading="loading"
      @click="loadMore"
    >
      查看更多评价
    </el-button>
  </section>
</template>
