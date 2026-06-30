<template>
  <div class="perf-panel">
    <div class="panel-header">
      <h3>查询性能对比</h3>
      <el-button size="small" :loading="loading" @click="loadStats">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- Loading -->
    <el-skeleton v-if="loading && !summary" :rows="4" animated />

    <!-- Empty -->
    <el-empty v-else-if="!summary || summary.total_queries === 0" description="暂无查询记录" :image-size="60" />

    <!-- Stats -->
    <div v-else>
      <!-- Summary Cards -->
      <div class="summary-row">
        <div class="summary-card">
          <div class="summary-value">{{ summary.total_queries }}</div>
          <div class="summary-label">总查询数</div>
        </div>
        <div class="summary-card agent">
          <div class="summary-value">{{ summary.avg_agent_ms }}<small>ms</small></div>
          <div class="summary-label">Agent 平均耗时</div>
        </div>
        <div class="summary-card cache">
          <div class="summary-value">{{ summary.avg_cache_ms }}<small>ms</small></div>
          <div class="summary-label">缓存平均耗时</div>
        </div>
        <div class="summary-card speedup" v-if="summary.speedup_ratio">
          <div class="summary-value">{{ summary.speedup_ratio }}<small>x</small></div>
          <div class="summary-label">加速比</div>
        </div>
      </div>

      <!-- Comparison Chart -->
      <div ref="chartRef" class="perf-chart"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getPerformanceStats } from '../api'

const loading = ref(false)
const summary = ref(null)
const items = ref([])
const chartRef = ref(null)
let chart = null

const loadStats = async () => {
  loading.value = true
  try {
    const res = await getPerformanceStats(50)
    summary.value = res.data.summary
    items.value = res.data.items
    await nextTick()
    renderChart()
  } catch (e) {
    console.error('Failed to load performance stats:', e)
  } finally {
    loading.value = false
  }
}

const renderChart = () => {
  if (!chartRef.value || !items.value.length) return

  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  // Separate agent and cache queries, sort by time
  const data = [...items.value].reverse()
  const labels = data.map((d, i) => `Q${i + 1}`)
  const agentData = data.map(d => d.cached ? null : d.execution_time_ms)
  const cacheData = data.map(d => d.cached ? d.execution_time_ms : null)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const idx = params[0]?.dataIndex
        if (idx === undefined) return ''
        const item = data[idx]
        const type = item.cached ? '缓存命中' : 'Agent 执行'
        return `${item.question}<br/>${type}: ${item.execution_time_ms}ms`
      },
    },
    legend: { data: ['Agent 执行', '缓存命中'], top: 0 },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { fontSize: 10, rotate: 45 },
    },
    yAxis: { type: 'value', name: '耗时(ms)', nameTextStyle: { fontSize: 11 } },
    series: [
      {
        name: 'Agent 执行',
        type: 'bar',
        data: agentData,
        itemStyle: { color: '#5470c6', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 16,
      },
      {
        name: '缓存命中',
        type: 'bar',
        data: cacheData,
        itemStyle: { color: '#91cc75', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 16,
      },
    ],
  })
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', () => chart?.resize())
})

onBeforeUnmount(() => {
  chart?.dispose()
  window.removeEventListener('resize', () => chart?.resize())
})
</script>

<style scoped>
.perf-panel {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0;
  font-size: 15px;
  color: #333;
}

.summary-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.summary-card {
  text-align: center;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 8px;
}

.summary-card.agent { background: #ecf5ff; }
.summary-card.cache { background: #f0f9eb; }
.summary-card.speedup { background: #fef0f0; }

.summary-value {
  font-size: 20px;
  font-weight: 700;
  color: #333;
}

.summary-value small {
  font-size: 12px;
  font-weight: 400;
  color: #999;
  margin-left: 2px;
}

.summary-label {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.perf-chart {
  height: 260px;
}
</style>
