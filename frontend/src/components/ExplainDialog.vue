<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="SQL 执行计划"
    width="900px"
    destroy-on-close
  >
    <!-- Loading -->
    <div v-if="loading" class="explain-loading">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- Error -->
    <el-alert v-else-if="error" :title="error" type="error" show-icon :closable="false" />

    <!-- Execution Plan -->
    <div v-else-if="plan" class="explain-content">
      <!-- Visual Steps -->
      <div class="plan-steps">
        <div
          v-for="(step, idx) in plan.steps"
          :key="idx"
          :class="['plan-step', step._level]"
        >
          <div class="step-header">
            <el-tag :type="tagType(step._level)" size="small">
              Step {{ idx + 1 }}
            </el-tag>
            <span class="step-table">{{ step.table || '-' }}</span>
            <el-tag :type="tagType(step._level)" effect="dark" size="small">
              {{ step.type || 'UNKNOWN' }}
            </el-tag>
          </div>
          <div class="step-details">
            <div class="detail-row" v-if="step.possible_keys">
              <span class="label">可用索引:</span>
              <el-tag size="small" type="info" v-for="key in parseKeys(step.possible_keys)" :key="key">{{ key }}</el-tag>
            </div>
            <div class="detail-row" v-if="step.key">
              <span class="label">实际使用:</span>
              <el-tag size="small" type="success">{{ step.key }}</el-tag>
            </div>
            <div class="detail-row" v-if="step.rows">
              <span class="label">预估扫描行数:</span>
              <span class="value">{{ Number(step.rows).toLocaleString() }}</span>
            </div>
            <div class="detail-row" v-if="step.Extra">
              <span class="label">附加信息:</span>
              <span :class="['value', extraClass(step.Extra)]">{{ step.Extra }}</span>
            </div>
          </div>
          <div v-if="idx < plan.steps.length - 1" class="step-arrow">↓</div>
        </div>
      </div>

      <!-- Raw Table -->
      <el-collapse class="raw-table-collapse">
        <el-collapse-item title="原始 EXPLAIN 输出">
          <el-table :data="plan.rows.map((r, i) => Object.fromEntries(plan.columns.map((c, j) => [c, r[j]])))" size="small" stripe border>
            <el-table-column v-for="col in plan.columns" :key="col" :prop="col" :label="col" min-width="80" />
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { sqlExplain } from '../api'

const props = defineProps({
  visible: Boolean,
  sql: String,
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)
const error = ref(null)
const plan = ref(null)

const tagType = (level) => {
  const map = { danger: 'danger', warning: 'warning', success: 'success', info: 'info' }
  return map[level] || 'info'
}

const parseKeys = (keys) => {
  if (!keys) return []
  return keys.split(',').map(k => k.trim()).filter(Boolean)
}

const extraClass = (extra) => {
  if (!extra) return ''
  if (extra.includes('Using filesort')) return 'extra-warn'
  if (extra.includes('Using temporary')) return 'extra-danger'
  if (extra.includes('Using index')) return 'extra-good'
  return ''
}

watch(() => props.visible, async (val) => {
  if (!val || !props.sql) return

  loading.value = true
  error.value = null
  plan.value = null

  try {
    const res = await sqlExplain(props.sql)
    if (res.data.success) {
      plan.value = res.data
    } else {
      error.value = res.data.error || 'EXPLAIN 执行失败'
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.explain-loading {
  padding: 20px;
}

.plan-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 20px;
}

.plan-step {
  border-left: 3px solid #dcdfe6;
  padding: 12px 16px;
  border-radius: 0 8px 8px 0;
  background: #fafafa;
  position: relative;
}

.plan-step.success { border-left-color: #67c23a; background: #f0f9eb; }
.plan-step.warning { border-left-color: #e6a23c; background: #fdf6ec; }
.plan-step.danger  { border-left-color: #f56c6c; background: #fef0f0; }

.step-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.step-table {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.step-details {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  font-size: 13px;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.detail-row .label {
  color: #909399;
  white-space: nowrap;
}

.detail-row .value {
  color: #333;
}

.extra-warn { color: #e6a23c; font-weight: 500; }
.extra-danger { color: #f56c6c; font-weight: 500; }
.extra-good { color: #67c23a; font-weight: 500; }

.step-arrow {
  text-align: center;
  color: #c0c4cc;
  font-size: 18px;
  padding: 4px 0;
}

.raw-table-collapse {
  margin-top: 16px;
}
</style>
