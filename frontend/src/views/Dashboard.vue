<template>
  <div class="dashboard-page">
    <!-- Header -->
    <div class="dashboard-header">
      <div>
        <h2>数据看板</h2>
        <p class="subtitle">预计算分析结果，定时刷新（10/30/60 分钟）</p>
      </div>
      <el-button :loading="loading" @click="loadDashboard" type="primary">
        <el-icon><Refresh /></el-icon>
        刷新数据
      </el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading && !hasData" class="loading-state">
      <el-skeleton :rows="8" animated />
    </div>

    <!-- No Data -->
    <el-empty v-else-if="!hasData" description="暂无预计算数据，请等待后台任务完成">
      <el-button type="primary" @click="loadDashboard">重新加载</el-button>
    </el-empty>

    <!-- Dashboard Content -->
    <div v-else class="dashboard-grid">
      <!-- Overview Cards -->
      <div v-if="overview" class="overview-section">
        <div class="section-title">
          <el-icon><DataAnalysis /></el-icon>
          <span>总览</span>
          <el-tag size="small" type="info" v-if="overview.computed_at">
            {{ formatTime(overview.computed_at) }}
          </el-tag>
        </div>
        <div class="stat-cards">
          <div v-for="stat in overviewCards" :key="stat.label" class="stat-card">
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </div>

      <!-- Charts Row 1: Top Products + Category Sales -->
      <div class="chart-row">
        <div class="chart-card half">
          <div class="card-header">
            <span>热销商品 TOP10</span>
            <el-tag size="small" type="info" v-if="topProducts?.computed_at">
              {{ formatTime(topProducts.computed_at) }}
            </el-tag>
          </div>
          <div v-if="topProducts" ref="topProductsChart" class="chart-box"></div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </div>
        <div class="chart-card half">
          <div class="card-header">
            <span>类目销售分布</span>
            <el-tag size="small" type="info" v-if="categorySales?.computed_at">
              {{ formatTime(categorySales.computed_at) }}
            </el-tag>
          </div>
          <div v-if="categorySales" ref="categorySalesChart" class="chart-box"></div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </div>
      </div>

      <!-- Charts Row 2: Daily Trend (full width) -->
      <div class="chart-row">
        <div class="chart-card full">
          <div class="card-header">
            <span>近 30 天订单趋势</span>
            <el-tag size="small" type="info" v-if="dailyTrend?.computed_at">
              {{ formatTime(dailyTrend.computed_at) }}
            </el-tag>
          </div>
          <div v-if="dailyTrend" ref="dailyTrendChart" class="chart-box wide"></div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </div>
      </div>

      <!-- Charts Row 3: Payment + City + Member -->
      <div class="chart-row three-col">
        <div class="chart-card third">
          <div class="card-header">
            <span>支付方式分布</span>
            <el-tag size="small" type="info" v-if="paymentDist?.computed_at">
              {{ formatTime(paymentDist.computed_at) }}
            </el-tag>
          </div>
          <div v-if="paymentDist" ref="paymentDistChart" class="chart-box"></div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </div>
        <div class="chart-card third">
          <div class="card-header">
            <span>城市客户排名</span>
            <el-tag size="small" type="info" v-if="cityRanking?.computed_at">
              {{ formatTime(cityRanking.computed_at) }}
            </el-tag>
          </div>
          <div v-if="cityRanking" ref="cityRankingChart" class="chart-box"></div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </div>
        <div class="chart-card third">
          <div class="card-header">
            <span>会员消费分析</span>
            <el-tag size="small" type="info" v-if="memberAnalysis?.computed_at">
              {{ formatTime(memberAnalysis.computed_at) }}
            </el-tag>
          </div>
          <div v-if="memberAnalysis" ref="memberAnalysisChart" class="chart-box"></div>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getDashboardStats } from '../api'

const COLORS = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4']

const loading = ref(false)
const modules = ref({})

// Chart refs
const topProductsChart = ref(null)
const categorySalesChart = ref(null)
const dailyTrendChart = ref(null)
const paymentDistChart = ref(null)
const cityRankingChart = ref(null)
const memberAnalysisChart = ref(null)

// Chart instances
let charts = []

// Data accessors
const getData = (key) => modules.value[key]?.data || null
const getTime = (key) => modules.value[key]?.computed_at || null

const overview = computed(() => {
  const d = getData('overview')
  if (!d?.rows?.length) return null
  const cols = d.columns
  const row = d.rows[0]
  return Object.fromEntries(cols.map((c, i) => [c, row[i]]))
})

const overviewCards = computed(() => {
  if (!overview.value) return []
  const map = [
    { key: '总订单数', format: (v) => Number(v).toLocaleString() },
    { key: '总客户数', format: (v) => Number(v).toLocaleString() },
    { key: '在售商品数', format: (v) => Number(v).toLocaleString() },
    { key: '总销售额', format: (v) => '¥' + Number(v).toLocaleString() },
    { key: '平均客单价', format: (v) => '¥' + Number(v).toFixed(2) },
    { key: '今日订单数', format: (v) => Number(v).toLocaleString() },
  ]
  return map
    .filter(m => overview.value[m.key] !== undefined)
    .map(m => ({
      label: m.key,
      value: m.format(overview.value[m.key]),
    }))
})

const topProducts = computed(() => getData('top_products') ? { ...getData('top_products'), computed_at: getTime('top_products') } : null)
const categorySales = computed(() => getData('category_sales') ? { ...getData('category_sales'), computed_at: getTime('category_sales') } : null)
const dailyTrend = computed(() => getData('daily_trend') ? { ...getData('daily_trend'), computed_at: getTime('daily_trend') } : null)
const paymentDist = computed(() => getData('payment_dist') ? { ...getData('payment_dist'), computed_at: getTime('payment_dist') } : null)
const cityRanking = computed(() => getData('city_ranking') ? { ...getData('city_ranking'), computed_at: getTime('city_ranking') } : null)
const memberAnalysis = computed(() => getData('member_analysis') ? { ...getData('member_analysis'), computed_at: getTime('member_analysis') } : null)

const hasData = computed(() => Object.values(modules.value).some(v => v !== null))

// Format ISO timestamp to local readable
const formatTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

// Load dashboard data
const loadDashboard = async () => {
  loading.value = true
  try {
    const res = await getDashboardStats()
    modules.value = res.data.modules || {}
    await nextTick()
    renderAllCharts()
  } catch (e) {
    ElMessage.error('加载看板数据失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

// Dispose all chart instances
const disposeCharts = () => {
  charts.forEach(c => c?.dispose())
  charts = []
}

// Render all charts
const renderAllCharts = () => {
  disposeCharts()

  if (topProducts.value && topProductsChart.value) {
    charts.push(renderBarChart(
      topProductsChart.value,
      topProducts.value.data,
      '商品名称', '总销量',
      { rotate: 30 }
    ))
  }

  if (categorySales.value && categorySalesChart.value) {
    charts.push(renderPieChart(
      categorySalesChart.value,
      categorySales.value.data,
      '类目名称', '销售总额'
    ))
  }

  if (dailyTrend.value && dailyTrendChart.value) {
    charts.push(renderDualLineChart(
      dailyTrendChart.value,
      dailyTrend.value.data
    ))
  }

  if (paymentDist.value && paymentDistChart.value) {
    charts.push(renderPieChart(
      paymentDistChart.value,
      paymentDist.value.data,
      '支付方式', '订单数量'
    ))
  }

  if (cityRanking.value && cityRankingChart.value) {
    charts.push(renderBarChart(
      cityRankingChart.value,
      cityRanking.value.data,
      '城市', '客户数量',
      { horizontal: true }
    ))
  }

  if (memberAnalysis.value && memberAnalysisChart.value) {
    charts.push(renderBarChart(
      memberAnalysisChart.value,
      memberAnalysis.value.data,
      '会员等级', '平均订单金额'
    ))
  }
}

function renderBarChart(el, data, xField, yField, opts = {}) {
  const cols = data.columns
  const xIdx = cols.indexOf(xField)
  const yIdx = cols.indexOf(yField)
  if (xIdx < 0 || yIdx < 0) return null

  const xData = data.rows.map(r => String(r[xIdx]))
  const yData = data.rows.map(r => Number(r[yIdx]) || 0)

  const chart = echarts.init(el)
  const option = opts.horizontal
    ? {
        tooltip: { trigger: 'axis' },
        color: COLORS,
        grid: { left: 100, right: 30, top: 10, bottom: 20 },
        xAxis: { type: 'value' },
        yAxis: { type: 'category', data: xData, inverse: true },
        series: [{ type: 'bar', data: yData, barMaxWidth: 24, itemStyle: { borderRadius: [0, 4, 4, 0] } }],
      }
    : {
        tooltip: { trigger: 'axis' },
        color: COLORS,
        grid: { left: 50, right: 20, top: 10, bottom: opts.rotate ? 80 : 40 },
        xAxis: {
          type: 'category',
          data: xData,
          axisLabel: { rotate: opts.rotate || 0, fontSize: 11 },
        },
        yAxis: { type: 'value' },
        series: [{ type: 'bar', data: yData, barMaxWidth: 32, itemStyle: { borderRadius: [4, 4, 0, 0] } }],
      }

  chart.setOption(option)
  return chart
}

function renderPieChart(el, data, nameField, valueField) {
  const cols = data.columns
  const nameIdx = cols.indexOf(nameField)
  const valueIdx = cols.indexOf(valueField)
  if (nameIdx < 0 || valueIdx < 0) return null

  const pieData = data.rows.map(r => ({
    name: String(r[nameIdx]),
    value: Number(r[valueIdx]) || 0,
  }))

  const chart = echarts.init(el)
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    color: COLORS,
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      data: pieData,
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' } },
      label: { formatter: '{b}\n{d}%', fontSize: 11 },
    }],
  })
  return chart
}

function renderDualLineChart(el, data) {
  const cols = data.columns
  const dateIdx = cols.indexOf('日期')
  const orderIdx = cols.indexOf('订单数')
  const revenueIdx = cols.indexOf('日销售额')

  if (dateIdx < 0) return null

  const dates = data.rows.map(r => String(r[dateIdx]))
  const orders = data.rows.map(r => Number(r[orderIdx]) || 0)
  const revenue = data.rows.map(r => Number(r[revenueIdx]) || 0)

  const chart = echarts.init(el)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['订单数', '日销售额'], top: 0 },
    color: ['#5470c6', '#ee6666'],
    grid: { left: 50, right: 60, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: [
      { type: 'value', name: '订单数', position: 'left' },
      { type: 'value', name: '销售额(¥)', position: 'right' },
    ],
    series: [
      {
        name: '订单数', type: 'bar', data: orders,
        barMaxWidth: 20, itemStyle: { borderRadius: [3, 3, 0, 0] },
      },
      {
        name: '日销售额', type: 'line', yAxisIndex: 1, data: revenue,
        smooth: true, areaStyle: { opacity: 0.08 },
      },
    ],
  })
  return chart
}

// Resize handler
const handleResize = () => charts.forEach(c => c?.resize())

onMounted(() => {
  loadDashboard()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  disposeCharts()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.dashboard-page {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.dashboard-header h2 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #999;
}

.loading-state {
  padding: 40px;
}

/* ── Overview Cards ── */
.overview-section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.stat-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

.stat-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #e94560;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #999;
}

/* ── Chart Grid ── */
.chart-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.chart-row.three-col {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}

.chart-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.chart-card.half {
  flex: 1;
}

.chart-card.full {
  flex: 1;
}

.chart-card.third {
  /* handled by grid */
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.chart-box {
  height: 300px;
}

.chart-box.wide {
  height: 340px;
}
</style>
