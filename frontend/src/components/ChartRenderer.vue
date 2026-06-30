<template>
  <div class="chart-wrapper" v-if="option">
    <div ref="chartRef" :style="{ width: '100%', height: height + 'px' }"></div>
  </div>
  <div v-else class="chart-placeholder">
    <el-empty description="暂无图表数据" :image-size="80" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  config: {
    type: Object,
    required: true,
  },
  data: {
    type: [Object, Array],
    default: null,
  },
  height: {
    type: Number,
    default: 360,
  },
})

const chartRef = ref(null)
let chartInstance = null

// Color palette
const COLORS = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4']

// Build ECharts option from config + data
const option = computed(() => {
  if (!props.config) return null

  const { chart_type, title, x_field, y_field, x_label, y_label } = props.config
  const chartData = props.data

  // If we have structured data, use it
  if (chartData && chartData.rows && chartData.columns) {
    return buildOption(chart_type, title, chartData, x_field, y_field, x_label, y_label)
  }

  // Fallback: build a placeholder showing chart type
  return buildPlaceholderOption(chart_type, title)
})

function buildOption(type, title, data, xField, yField, xLabel, yLabel) {
  const columns = data.columns
  const rows = data.rows

  // Auto-detect x and y fields if not specified
  const xIdx = xField ? columns.indexOf(xField) : 0
  const yIdx = yField ? columns.indexOf(yField) : (columns.length > 1 ? 1 : 0)

  const xData = rows.map(r => String(r[xIdx]))
  const yData = rows.map(r => Number(r[yIdx]) || 0)

  const baseOption = {
    title: { text: title || '', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    color: COLORS,
    grid: { left: 60, right: 30, top: 50, bottom: 40 },
  }

  switch (type) {
    case 'bar':
      return {
        ...baseOption,
        xAxis: { type: 'category', data: xData, name: xLabel || '', axisLabel: { rotate: xData.length > 6 ? 30 : 0 } },
        yAxis: { type: 'value', name: yLabel || '' },
        series: [{ type: 'bar', data: yData, barMaxWidth: 40, itemStyle: { borderRadius: [4, 4, 0, 0] } }],
      }

    case 'line':
      return {
        ...baseOption,
        xAxis: { type: 'category', data: xData, name: xLabel || '' },
        yAxis: { type: 'value', name: yLabel || '' },
        series: [{ type: 'line', data: yData, smooth: true, areaStyle: { opacity: 0.1 } }],
      }

    case 'pie':
      return {
        ...baseOption,
        tooltip: { trigger: 'item' },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data: xData.map((name, i) => ({ name, value: yData[i] })),
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' } },
          label: { formatter: '{b}: {d}%' },
        }],
      }

    case 'number':
      return {
        ...baseOption,
        title: {
          text: yData[0]?.toLocaleString() || '0',
          subtext: title || xData[0] || '',
          left: 'center',
          top: 'center',
          textStyle: { fontSize: 36, fontWeight: 'bold', color: '#e94560' },
          subtextStyle: { fontSize: 14, color: '#999' },
        },
        series: [],
      }

    default: // table or unknown
      return buildPlaceholderOption(type, title)
  }
}

function buildPlaceholderOption(type, title) {
  const typeNames = { bar: '柱状图', line: '折线图', pie: '饼图', number: '数值卡片', table: '数据表格' }
  return {
    title: {
      text: title || `${typeNames[type] || '图表'}`,
      subtext: '（等待查询数据...）',
      left: 'center',
      top: 'center',
      textStyle: { fontSize: 16 },
      subtextStyle: { fontSize: 12, color: '#999' },
    },
  }
}

// Render chart
const renderChart = async () => {
  await nextTick()
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)
  if (option.value) {
    chartInstance.setOption(option.value)
  }
}

watch(option, () => renderChart(), { deep: true })

onMounted(() => {
  renderChart()
  window.addEventListener('resize', () => chartInstance?.resize())
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  window.removeEventListener('resize', () => chartInstance?.resize())
})
</script>

<style scoped>
.chart-wrapper {
  padding: 12px;
  background: #fff;
}

.chart-placeholder {
  padding: 20px;
  text-align: center;
}
</style>
