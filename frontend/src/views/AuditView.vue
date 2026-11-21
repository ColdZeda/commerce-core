<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchAudit } from '../api/audit'

const report = ref(null)
const loading = ref(true)
const onlyUnbalanced = ref(false)

const rows = computed(() => {
  const all = report.value?.skus ?? []
  return onlyUnbalanced.value ? all.filter((row) => !row.balanced) : all
})

async function load() {
  loading.value = true
  try {
    report.value = await fetchAudit()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="wrap">
    <div class="cart-head">
      <h1>对账看板</h1>
      <span class="cart-sub">免登录只读，只统计数量，不含用户名、手机号与地址</span>
    </div>

    <el-skeleton
      v-if="loading"
      :rows="6"
      animated
    />
    <template v-else-if="report">
      <div
        class="audit-banner"
        :class="report.summary.balanced ? 'ok' : 'bad'"
      >
        <strong>{{ report.summary.balanced ? '账是平的' : '账不平' }}</strong>
        <span v-if="report.summary.balanced">
          {{ report.summary.skus }} 个 SKU 全部满足「初始 − 已售 = 账面」，且「已售 + 回补 = 明细合计」
        </span>
        <span v-else>
          有 {{ report.summary.unbalanced }} 个 SKU 对不上，先看下面的差额列
        </span>
      </div>

      <div class="audit-stats">
        <div><b>{{ report.summary.skus }}</b><small>在册 SKU</small></div>
        <div><b>{{ report.summary.stock_total }}</b><small>账面合计</small></div>
        <div><b>{{ report.summary.sold_total }}</b><small>已售（待支付 + 已支付）</small></div>
        <div><b>{{ report.summary.restocked_total }}</b><small>回补（取消 + 关闭 + 退款）</small></div>
        <div :class="{ warn: report.summary.unbalanced }">
          <b>{{ report.summary.unbalanced }}</b><small>不平的 SKU</small>
        </div>
      </div>

      <div class="audit-toolbar">
        <el-checkbox v-model="onlyUnbalanced">
          只看不平的
        </el-checkbox>
        <el-button
          text
          type="primary"
          @click="load"
        >
          刷新
        </el-button>
        <span class="catalog-result">生成于 {{ new Date(report.generated_at).toLocaleString('zh-CN', { hour12: false }) }}</span>
      </div>

      <el-table
        :data="rows"
        size="small"
        class="audit-table"
        :row-class-name="({ row }) => (row.balanced ? '' : 'row-bad')"
      >
        <el-table-column
          prop="sku_code"
          label="SKU"
          min-width="120"
        />
        <el-table-column
          prop="product"
          label="商品"
          min-width="140"
        />
        <el-table-column
          prop="initial"
          label="初始"
          width="80"
          align="right"
        />
        <el-table-column
          prop="sold"
          label="已售"
          width="80"
          align="right"
        />
        <el-table-column
          prop="restocked"
          label="回补"
          width="80"
          align="right"
        />
        <el-table-column
          prop="stock"
          label="账面"
          width="80"
          align="right"
        />
        <el-table-column
          prop="items_total"
          label="明细合计"
          width="100"
          align="right"
        />
        <el-table-column
          label="差额"
          width="90"
          align="right"
        >
          <template #default="{ row }">
            <span :class="row.balanced ? '' : 'audit-diff'">{{ row.diff }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="状态"
          width="90"
        >
          <template #default="{ row }">
            <el-tag
              :type="row.balanced ? 'success' : 'danger'"
              size="small"
            >
              {{ row.balanced ? '平' : '不平' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="audit-side">
        <section>
          <h2>券</h2>
          <el-table
            :data="report.coupons"
            size="small"
          >
            <el-table-column
              prop="name"
              label="券"
              min-width="130"
            />
            <el-table-column
              prop="issued"
              label="已发"
              width="80"
              align="right"
            />
            <el-table-column
              prop="used"
              label="已用"
              width="80"
              align="right"
            />
            <el-table-column
              prop="total"
              label="总量"
              width="80"
              align="right"
            />
          </el-table>
        </section>

        <section>
          <h2>订单</h2>
          <div class="audit-stats compact">
            <div><b>{{ report.orders.pending }}</b><small>待支付</small></div>
            <div><b>{{ report.orders.paid }}</b><small>已支付</small></div>
            <div><b>{{ report.orders.cancelled }}</b><small>已取消</small></div>
            <div><b>{{ report.orders.closed }}</b><small>已关闭</small></div>
            <div><b>{{ report.orders.refunded }}</b><small>已退款</small></div>
            <div><b>{{ report.orders.total }}</b><small>合计</small></div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
