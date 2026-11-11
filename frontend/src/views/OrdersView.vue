<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchMyCoupons } from '../api/coupons'
import { cancelOrder, fetchOrder, fetchOrders } from '../api/orders'

const TABS = [
  { name: 'all', label: '全部' },
  { name: 'pending', label: '待支付' },
  { name: 'paid', label: '已支付' },
  { name: 'cancelled', label: '已取消' },
  { name: 'closed', label: '已关闭' },
]

const STATUS_TYPES = { 0: 'warning', 1: 'success', 2: 'info', 3: 'info' }

const CANCEL_ERRORS = {
  ORDER_STATUS_INVALID: '这单已经不是待支付状态了',
  NOT_FOUND: '订单不存在',
}

const route = useRoute()

const activeTab = ref('all')
const orders = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

const detail = ref(null)
const detailVisible = ref(false)
const cancelling = ref('')

const coupons = ref([])
const couponsVisible = ref(false)

function money(value) {
  return Number(value).toFixed(2)
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

function isPending(order) {
  return order.status === 0
}

async function load() {
  loading.value = true
  try {
    const data = await fetchOrders({
      page: page.value,
      page_size: pageSize,
      status: activeTab.value === 'all' ? undefined : activeTab.value,
    })
    orders.value = data.results
    total.value = data.count
  } finally {
    loading.value = false
  }
}

function changeTab() {
  page.value = 1
  load()
}

function changePage(next) {
  page.value = next
  load()
}

async function openDetail(orderNo) {
  detail.value = await fetchOrder(orderNo)
  detailVisible.value = true
}

async function cancel(orderNo) {
  try {
    await ElMessageBox.confirm('取消后库存和券会退回，确定取消这一单？', '取消订单', { type: 'warning' })
  } catch {
    return
  }

  cancelling.value = orderNo
  try {
    const updated = await cancelOrder(orderNo)
    ElMessage.success('已取消')
    if (detail.value?.order_no === updated.order_no) {
      detail.value = updated
    }
    await load()
  } catch (error) {
    ElMessage.warning(CANCEL_ERRORS[error?.response?.data?.code] || '取消失败，请稍后再试')
  } finally {
    cancelling.value = ''
  }
}

async function openCoupons() {
  const data = await fetchMyCoupons({ status: 'unused', page_size: 50 })
  coupons.value = data.results
  couponsVisible.value = true
}

onMounted(() => {
  load()
  if (typeof route.query.order === 'string') {
    openDetail(route.query.order)
  }
})
</script>

<template>
  <main class="page">
    <div class="orders-toolbar">
      <h1>我的订单</h1>
      <el-button @click="openCoupons">
        我的券
      </el-button>
    </div>

    <el-tabs
      v-model="activeTab"
      @tab-change="changeTab"
    >
      <el-tab-pane
        v-for="tab in TABS"
        :key="tab.name"
        :label="tab.label"
        :name="tab.name"
      />
    </el-tabs>

    <el-table
      v-loading="loading"
      :data="orders"
      row-key="order_no"
      empty-text="还没有订单"
    >
      <el-table-column
        prop="order_no"
        label="订单号"
        min-width="210"
      />
      <el-table-column
        label="状态"
        width="100"
      >
        <template #default="{ row }">
          <el-tag :type="STATUS_TYPES[row.status]">
            {{ row.status_label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="应付"
        width="110"
      >
        <template #default="{ row }">
          ¥{{ money(row.pay_amount) }}
        </template>
      </el-table-column>
      <el-table-column
        label="下单时间"
        min-width="170"
      >
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        width="170"
      >
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            @click="openDetail(row.order_no)"
          >
            详情
          </el-button>
          <el-button
            v-if="isPending(row)"
            link
            type="danger"
            :loading="cancelling === row.order_no"
            @click="cancel(row.order_no)"
          >
            取消
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      class="catalog-pagination"
      layout="prev, pager, next"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      @current-change="changePage"
    />

    <el-drawer
      v-model="detailVisible"
      title="订单详情"
      size="460px"
    >
      <template v-if="detail">
        <el-descriptions
          :column="1"
          border
        >
          <el-descriptions-item label="订单号">
            {{ detail.order_no }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="STATUS_TYPES[detail.status]">
              {{ detail.status_label }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="下单时间">
            {{ formatTime(detail.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="支付截止">
            {{ formatTime(detail.expire_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="商品金额">
            ¥{{ money(detail.total_amount) }}
          </el-descriptions-item>
          <el-descriptions-item label="优惠">
            -¥{{ money(detail.discount_amount) }}
          </el-descriptions-item>
          <el-descriptions-item label="应付">
            <strong class="money">¥{{ money(detail.pay_amount) }}</strong>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="detail.cancel_reason"
            label="取消原因"
          >
            {{ detail.cancel_reason }}
          </el-descriptions-item>
        </el-descriptions>

        <h3 class="detail-items-title">
          商品明细
        </h3>
        <el-table
          :data="detail.items"
          size="small"
        >
          <el-table-column
            prop="title"
            label="商品"
            min-width="120"
          />
          <el-table-column
            prop="sku_code"
            label="编码"
            min-width="110"
          />
          <el-table-column
            label="单价"
            width="90"
          >
            <template #default="{ row }">
              ¥{{ money(row.unit_price) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="qty"
            label="数量"
            width="70"
          />
          <el-table-column
            label="小计"
            width="90"
          >
            <template #default="{ row }">
              ¥{{ money(row.subtotal) }}
            </template>
          </el-table-column>
        </el-table>

        <el-button
          v-if="isPending(detail)"
          type="danger"
          plain
          class="detail-submit"
          :loading="cancelling === detail.order_no"
          @click="cancel(detail.order_no)"
        >
          取消订单
        </el-button>
      </template>
    </el-drawer>

    <el-drawer
      v-model="couponsVisible"
      title="我的券"
      size="400px"
    >
      <el-empty
        v-if="!coupons.length"
        description="没有未使用的券"
      />
      <el-card
        v-for="item in coupons"
        :key="item.id"
        shadow="never"
        class="coupon-card"
      >
        <div class="coupon-main">
          <strong>满 {{ item.coupon.threshold_amount }} 减 {{ item.coupon.discount_amount }}</strong>
          <span class="coupon-threshold">有效期至 {{ formatTime(item.coupon.end_at) }}</span>
        </div>
      </el-card>
    </el-drawer>
  </main>
</template>
