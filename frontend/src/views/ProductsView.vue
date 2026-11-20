<script setup>
import { ElMessage } from 'element-plus'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ProductCard from '../components/ProductCard.vue'
import { CATEGORIES } from '../constants/categories'
import { fetchProducts } from '../api/catalog'

const PAGE_SIZE = 10

const ORDERING_OPTIONS = [
  { label: '最新上架', value: '-created_at' },
  { label: '价格从低到高', value: 'price' },
  { label: '价格从高到低', value: '-price' },
]

const route = useRoute()
const router = useRouter()

const products = ref([])
const total = ref(0)
const loading = ref(true)
const draftKeyword = ref('')

const activeCategory = computed(() =>
  typeof route.query.category === 'string' ? route.query.category : '',
)
const keyword = computed(() => (typeof route.query.keyword === 'string' ? route.query.keyword : ''))
const ordering = computed(() =>
  typeof route.query.ordering === 'string' ? route.query.ordering : '-created_at',
)
const page = computed(() => Number(route.query.page) || 1)

const heading = computed(() => {
  if (keyword.value) {
    return `“${keyword.value}” 的搜索结果`
  }
  return CATEGORIES.find((item) => item.value === activeCategory.value)?.label || '全部商品'
})

/** 换筛选条件时回到第 1 页，只翻页时保留条件。 */
function go(patch) {
  router.push({ name: 'products', query: { ...route.query, page: undefined, ...patch } })
}

function submitKeyword() {
  go({ keyword: draftKeyword.value.trim() || undefined })
}

watch(
  () => keyword.value,
  (value) => {
    draftKeyword.value = value
  },
  { immediate: true },
)

async function load() {
  loading.value = true
  try {
    const data = await fetchProducts({
      page: page.value,
      page_size: PAGE_SIZE,
      ordering: ordering.value,
      category: activeCategory.value || undefined,
      keyword: keyword.value || undefined,
    })
    products.value = data.results
    total.value = data.count
  } catch (error) {
    if (error?.response?.status === 400) {
      ElMessage.warning('筛选条件不正确，已经重置')
      router.replace({ name: 'products' })
    }
  } finally {
    loading.value = false
  }
}

watch(() => route.fullPath, load, { immediate: true })
</script>

<template>
  <div class="wrap">
    <div class="catalog-bar">
      <form
        class="catalog-search"
        @submit.prevent="submitKeyword"
      >
        <input
          v-model="draftKeyword"
          placeholder="搜商品名或副标题"
        >
        <button type="submit">
          搜索
        </button>
      </form>
      <el-select
        :model-value="ordering"
        class="catalog-order"
        style="width: 148px"
        @change="go({ ordering: $event })"
      >
        <el-option
          v-for="item in ORDERING_OPTIONS"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <span class="catalog-result">{{ heading }} · 共 {{ total }} 件</span>
    </div>

    <div class="catalog-bar catalog-bar-pills">
      <button
        class="pill"
        :class="{ on: !activeCategory }"
        @click="go({ category: undefined })"
      >
        全部
      </button>
      <button
        v-for="category in CATEGORIES"
        :key="category.value"
        class="pill"
        :class="{ on: activeCategory === category.value }"
        @click="go({ category: category.value })"
      >
        {{ category.label }}
      </button>
    </div>

    <el-skeleton
      v-if="loading"
      :rows="6"
      animated
      style="margin-top: 22px"
    />
    <template v-else>
      <el-empty
        v-if="!products.length"
        description="没有找到商品，换个词或换个分类试试"
      />
      <div
        v-else
        class="product-grid"
        style="margin-top: 22px"
      >
        <ProductCard
          v-for="item in products"
          :key="item.id"
          :product="item"
        />
      </div>

      <el-pagination
        v-if="total > PAGE_SIZE"
        class="catalog-pagination"
        layout="prev, pager, next"
        :total="total"
        :page-size="PAGE_SIZE"
        :current-page="page"
        @current-change="go({ page: $event })"
      />
    </template>
  </div>
</template>
