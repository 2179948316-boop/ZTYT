<template>
  <div class="history-page">
    <div class="page-header">
      <h2>查询历史</h2>
      <el-tag type="info">共 {{ total }} 条记录</el-tag>
    </div>

    <el-table :data="historyItems" stripe style="width: 100%" v-loading="loading">
      <el-table-column label="问题" min-width="250">
        <template #default="{ row }">
          <span class="question-text">{{ row.question }}</span>
        </template>
      </el-table-column>
      <el-table-column label="SQL" width="120">
        <template #default="{ row }">
          <el-button v-if="row.sql_query" link type="primary" @click="showSql(row)">
            查看 SQL
          </el-button>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="图表" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.chart_type" size="small">{{ chartTypeLabel(row.chart_type) }}</el-tag>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="100" align="right">
        <template #default="{ row }">
          <span v-if="row.execution_time_ms">{{ row.execution_time_ms }}ms</span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="缓存" width="70" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.cached" type="warning" size="small">命中</el-tag>
          <el-tag v-else type="info" size="small">实时</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadHistory"
      />
    </div>

    <!-- SQL Dialog -->
    <el-dialog v-model="sqlDialogVisible" title="SQL 查询语句" width="600px">
      <pre class="sql-display">{{ currentSql }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getHistory } from '../api'

const historyItems = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const loading = ref(false)
const sqlDialogVisible = ref(false)
const currentSql = ref('')

const chartTypeLabel = (type) => {
  const map = { bar: '柱状图', line: '折线图', pie: '饼图', number: '数值', table: '表格' }
  return map[type] || type
}

const formatTime = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const showSql = (row) => {
  currentSql.value = row.sql_query
  sqlDialogVisible.value = true
}

const loadHistory = async () => {
  loading.value = true
  try {
    const res = await getHistory(currentPage.value, pageSize)
    historyItems.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    console.error('Failed to load history:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadHistory())
</script>

<style scoped>
.history-page {
  padding: 24px;
  height: 100vh;
  overflow-y: auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #333;
}

.question-text {
  font-size: 13px;
}

.text-muted {
  color: #ccc;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

.sql-display {
  background: #1e1e2e;
  color: #a6e3a1;
  padding: 16px;
  border-radius: 8px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  overflow-x: auto;
}
</style>
