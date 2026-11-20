<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { createAddress, deleteAddress, fetchAddresses, updateAddress } from '../api/addresses'

const EMPTY = { receiver: '', phone: '', region: '', detail: '', is_default: false }

const addresses = ref([])
const loading = ref(true)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = reactive({ ...EMPTY })

async function load() {
  loading.value = true
  try {
    addresses.value = (await fetchAddresses()).items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, EMPTY)
  dialogVisible.value = true
}

function openEdit(address) {
  editingId.value = address.id
  Object.assign(form, {
    receiver: address.receiver,
    phone: address.phone,
    region: address.region,
    detail: address.detail,
    is_default: address.is_default,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.receiver || !form.phone || !form.region || !form.detail) {
    ElMessage.warning('四项都要填')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateAddress(editingId.value, { ...form })
      ElMessage.success('已保存')
    } else {
      await createAddress({ ...form })
      ElMessage.success('已添加')
    }
    dialogVisible.value = false
    await load()
  } catch (error) {
    const detail = error?.response?.data?.detail
    ElMessage.warning(detail ? Object.values(detail)[0]?.[0] || '保存失败' : '保存失败')
  } finally {
    saving.value = false
  }
}

async function setDefault(address) {
  await updateAddress(address.id, { is_default: true })
  await load()
}

async function remove(address) {
  await ElMessageBox.confirm(`删除「${address.receiver}」的这个地址？`, '删除地址', { type: 'warning' })
  await deleteAddress(address.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="wrap">
    <div class="cart-head">
      <h1>收货地址</h1>
      <span class="cart-sub">下单时整段快照进订单，之后改这里不影响已有订单</span>
      <el-button
        type="primary"
        style="margin-left: auto"
        @click="openCreate"
      >
        新增地址
      </el-button>
    </div>

    <el-skeleton
      v-if="loading"
      :rows="3"
      animated
    />
    <el-empty
      v-else-if="!addresses.length"
      description="还没有收货地址"
    />

    <div
      v-else
      class="addr-list"
    >
      <div
        v-for="address in addresses"
        :key="address.id"
        class="addr-card"
        :class="{ 'is-default': address.is_default }"
      >
        <div class="addr-main">
          <div class="addr-title">
            <strong>{{ address.receiver }}</strong>
            <span>{{ address.phone }}</span>
            <span
              v-if="address.is_default"
              class="addr-tag"
            >默认</span>
          </div>
          <p>{{ address.region }}{{ address.detail }}</p>
        </div>
        <div class="addr-actions">
          <button
            v-if="!address.is_default"
            class="cart-remove"
            @click="setDefault(address)"
          >
            设为默认
          </button>
          <button
            class="cart-remove"
            @click="openEdit(address)"
          >
            编辑
          </button>
          <button
            class="cart-remove"
            @click="remove(address)"
          >
            删除
          </button>
        </div>
      </div>
    </div>

    <p class="addr-back">
      <RouterLink to="/cart">
        ← 回购物车
      </RouterLink>
    </p>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑地址' : '新增地址'"
      width="460px"
    >
      <el-form label-position="top">
        <el-form-item label="收件人">
          <el-input
            v-model="form.receiver"
            maxlength="40"
          />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input
            v-model="form.phone"
            maxlength="20"
          />
        </el-form-item>
        <el-form-item label="省市区">
          <el-input
            v-model="form.region"
            maxlength="120"
            placeholder="如：广东省 深圳市 南山区"
          />
        </el-form-item>
        <el-form-item label="详细地址">
          <el-input
            v-model="form.detail"
            maxlength="200"
            placeholder="街道、门牌号、楼层"
          />
        </el-form-item>
        <el-checkbox v-model="form.is_default">
          设为默认地址
        </el-checkbox>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          @click="save"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
