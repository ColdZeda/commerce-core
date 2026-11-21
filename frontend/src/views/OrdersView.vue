<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchMyCoupons } from '../api/coupons'
import { cancelOrder, fetchOrder, fetchOrders, payOrder, refundOrder } from '../api/orders'
import { submitOrderReview } from '../api/reviews'

const TABS = [
  { name: 'all', label: '全部' },
  { name: 'pending', label: '待支付' },
  { name: 'paid', label: '已支付' },
  { name: 'cancelled', label: '已取消' },
  { name: 'closed', label: '已关闭' },
  { name: 'refunded', label: '已退款' },
]

const STATUS_TYPES = { 0: 'warning', 1: 'success', 2: 'info', 3: 'info', 4: 'danger' }

const CANCEL_ERRORS = {
  ORDER_STATUS_INVALID: '这单已经不是待支付状态了',
  NOT_FOUND: '订单不存在',
}

const PAY_ERRORS = {
  PAY_NOT_ENABLED: '这个环境没有开启模拟支付',
  ORDER_NOT_PAYABLE: '这单已经不能支付了',
  PAY_AMOUNT_MISMATCH: '金额对不上，支付被拒',
  NOT_FOUND: '订单不存在',
}

const REFUND_ERRORS = {
  ORDER_ALREADY_REFUNDED: '这单已经退过款了',
  ORDER_STATUS_INVALID: '只有已支付的订单可以退款',
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
const paying = ref('')
const refunding = ref('')

const coupons = ref([])
const couponsVisible = ref(false)

const reviewVisible = ref(false)
const reviewing = ref(false)
const reviewEntries = ref([])

const REVIEW_ERRORS = {
  REVIEW_ORDER_NOT_PAID: '只有已支付的订单可以评价',
  REVIEW_ALREADY_EXISTS: '这些商品里有的已经评过了',
  REVIEW_PRODUCT_GONE: '商品已不存在，无法评价',
  NOT_FOUND: '订单或明细不存在',
}

function money(value) {
  return Number(value).toFixed(2)
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

function isPending(order) {
  return order.status === 0
}

function isPaid(order) {
  return order.status === 1
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

async function pay(orderNo) {
  try {
    await ElMessageBox.confirm('这是模拟支付，只把订单标记为已支付，不会真的扣款。', '模拟支付', {
      type: 'info',
    })
  } catch {
    return
  }

  paying.value = orderNo
  try {
    const { order, replayed } = await payOrder(orderNo)
    ElMessage.success(replayed ? '这单之前已经支付过了' : '支付成功')
    if (detail.value?.order_no === order.order_no) {
      detail.value = order
    }
    await load()
  } catch (error) {
    ElMessage.warning(PAY_ERRORS[error?.response?.data?.code] || '支付失败，请稍后再试')
  } finally {
    paying.value = ''
  }
}

async function refund(orderNo) {
  let reason
  try {
    const { value } = await ElMessageBox.prompt('整单退款：库存和优惠券都会退回，原因可以不填。', '申请退款', {
      type: 'warning',
      inputPlaceholder: '退款原因（选填）',
      confirmButtonText: '确认退款',
      cancelButtonText: '再想想',
    })
    reason = (value || '').trim()
  } catch {
    return
  }

  refunding.value = orderNo
  try {
    const updated = await refundOrder(orderNo, reason)
    ElMessage.success('已退款')
    if (detail.value?.order_no === updated.order_no) {
      detail.value = updated
    }
    await load()
  } catch (error) {
    ElMessage.warning(REFUND_ERRORS[error?.response?.data?.code] || '退款失败，请稍后再试')
  } finally {
    refunding.value = ''
  }
}

async function openCoupons() {
  const data = await fetchMyCoupons({ status: 'unused', page_size: 50 })
  coupons.value = data.results
  couponsVisible.value = true
}

function pendingReviews(order) {
  return (order?.items ?? []).filter((item) => !item.reviewed)
}

function openReview() {
  // 已评过的行不再列出来，避免用户以为要重评一次。
  reviewEntries.value = pendingReviews(detail.value).map((item) => ({
    order_item_id: item.id,
    title: item.title,
    rating: 5,
    content: '',
  }))
  reviewVisible.value = true
}

async function submitReview() {
  if (!reviewEntries.value.length) {
    return
  }
  reviewing.value = true
  try {
    const { created } = await submitOrderReview(
      detail.value.order_no,
      reviewEntries.value.map(({ order_item_id, rating, content }) => ({
        order_item_id,
        rating,
        content,
      })),
    )
    reviewVisible.value = false
    ElMessage.success(`已提交 ${created} 条评价`)
    detail.value = await fetchOrder(detail.value.order_no)
    await load()
  } catch (error) {
    ElMessage.warning(REVIEW_ERRORS[error?.response?.data?.code] || '评价失败，请稍后再试')
  } finally {
    reviewing.value = false
  }
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
        width="230"
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
            type="success"
            :loading="paying === row.order_no"
            @click="pay(row.order_no)"
          >
            支付
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
          <el-button
            v-if="isPaid(row)"
            link
            type="danger"
            :loading="refunding === row.order_no"
            @click="refund(row.order_no)"
          >
            退款
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
      size="560px"
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
            v-if="detail.address_snapshot"
            label="收货地址"
          >
            {{ detail.address_snapshot.receiver }} {{ detail.address_snapshot.phone }}
            <br>
            {{ detail.address_snapshot.region }}{{ detail.address_snapshot.detail }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="detail.cancel_reason"
            label="取消原因"
          >
            {{ detail.cancel_reason }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="detail.refunded_at"
            label="退款时间"
          >
            {{ formatTime(detail.refunded_at) }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="detail.refund_reason"
            label="退款原因"
          >
            {{ detail.refund_reason }}
          </el-descriptions-item>
        </el-descriptions>

        <h3 class="detail-items-title">
          进度
        </h3>
        <el-timeline class="order-timeline">
          <el-timeline-item
            :timestamp="formatTime(detail.created_at)"
            type="primary"
          >
            下单
          </el-timeline-item>
          <el-timeline-item
            v-if="detail.paid_at"
            :timestamp="formatTime(detail.paid_at)"
            type="success"
          >
            已支付
          </el-timeline-item>
          <el-timeline-item
            v-if="detail.status_name === 'cancelled'"
            type="info"
          >
            已取消
          </el-timeline-item>
          <el-timeline-item
            v-if="detail.refunded_at"
            :timestamp="formatTime(detail.refunded_at)"
            type="danger"
          >
            已退款，库存与券已退回
          </el-timeline-item>
          <el-timeline-item
            v-if="detail.closed_at"
            :timestamp="formatTime(detail.closed_at)"
            type="info"
          >
            超时关闭，库存已回补
          </el-timeline-item>
          <el-timeline-item
            type="info"
            :hollow="true"
          >
            物流：演示项目未接入，不产生真实发货
          </el-timeline-item>
        </el-timeline>

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
          v-if="detail.status_name === 'paid' && pendingReviews(detail).length"
          type="primary"
          class="detail-submit"
          @click="openReview"
        >
          评价商品（{{ pendingReviews(detail).length }}）
        </el-button>
        <el-button
          v-if="isPaid(detail)"
          type="danger"
          plain
          class="detail-submit"
          :loading="refunding === detail.order_no"
          @click="refund(detail.order_no)"
        >
          申请退款
        </el-button>
        <el-button
          v-if="isPending(detail)"
          type="success"
          class="detail-submit"
          :loading="paying === detail.order_no"
          @click="pay(detail.order_no)"
        >
          模拟支付
        </el-button>
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

    <el-dialog
      v-model="reviewVisible"
      title="评价商品"
      width="520px"
    >
      <p class="review-done">
        评价只针对已支付的订单，每条商品只能评一次，提交后不能修改。
      </p>
      <div
        v-for="entry in reviewEntries"
        :key="entry.order_item_id"
        class="review-row"
      >
        <div class="review-row-head">
          <span class="review-row-title">{{ entry.title }}</span>
          <el-rate v-model="entry.rating" />
        </div>
        <el-input
          v-model="entry.content"
          type="textarea"
          :rows="2"
          maxlength="500"
          show-word-limit
          placeholder="说说使用感受（选填）"
        />
      </div>
      <template #footer>
        <el-button @click="reviewVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="reviewing"
          @click="submitReview"
        >
          提交评价
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>
