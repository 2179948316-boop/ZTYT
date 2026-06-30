<template>
  <div class="chat-layout">
    <!-- Conversation Sidebar -->
    <div class="conv-sidebar">
      <div class="conv-header">
        <el-button type="primary" @click="handleNewChat" class="new-chat-btn">
          <el-icon><Plus /></el-icon>
          新对话
        </el-button>
      </div>
      <div class="conv-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          :class="['conv-item', { active: conv.id === currentConvId }]"
          @click="selectConversation(conv.id)"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span class="conv-title">{{ conv.title }}</span>
          <el-icon class="conv-delete" @click.stop="handleDeleteConv(conv.id)"><Delete /></el-icon>
        </div>
      </div>
      <div class="perf-toggle">
        <el-button :type="showPerf ? 'primary' : 'default'" size="small" @click="showPerf = !showPerf" style="width:100%">
          <el-icon><TrendCharts /></el-icon>
          {{ showPerf ? '隐藏' : '性能对比' }}
        </el-button>
      </div>
    </div>

    <!-- Main Chat Area -->
    <div class="chat-main">
      <!-- Messages -->
      <div class="messages-container" ref="messagesRef">
        <!-- Welcome Screen -->
        <div v-if="messages.length === 0" class="welcome-screen">
          <el-icon :size="48" color="#e94560"><DataAnalysis /></el-icon>
          <h2>智能数据分析助手</h2>
          <p>用自然语言提问，AI 自动生成 SQL、执行查询、返回分析结论和可视化图表</p>
          <div class="example-questions">
            <div
              v-for="q in exampleQuestions"
              :key="q"
              class="example-q"
              @click="sendExample(q)"
            >
              {{ q }}
            </div>
          </div>
        </div>

        <!-- Message List -->
        <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role]">
          <div class="message-avatar">
            <el-icon v-if="msg.role === 'user'" :size="20"><User /></el-icon>
            <el-icon v-else :size="20"><Monitor /></el-icon>
          </div>
          <div class="message-content">
            <!-- User Message -->
            <div v-if="msg.role === 'user'" class="user-text">{{ msg.content }}</div>

            <!-- Assistant Message -->
            <div v-else class="assistant-content">
              <!-- SQL Block -->
              <div v-if="msg.sql" class="sql-block">
                <div class="sql-header">
                  <el-icon><Document /></el-icon>
                  <span>执行的 SQL</span>
                  <el-tag size="small" :type="msg.cached ? 'warning' : 'success'">
                    {{ msg.cached ? '缓存命中' : '实时查询' }}
                  </el-tag>
                  <el-tag v-if="msg.execution_time_ms" size="small" type="info">
                    {{ msg.execution_time_ms }}ms
                  </el-tag>
                  <el-button size="small" text @click="showExplain(msg.sql)" class="explain-btn">
                    <el-icon><View /></el-icon>
                    EXPLAIN
                  </el-button>
                </div>
                <pre class="sql-code"><code>{{ msg.sql }}</code></pre>
              </div>

              <!-- Answer Text -->
              <div class="answer-text" v-html="renderMarkdown(msg.content)"></div>

              <!-- Chart -->
              <div v-if="msg.chart_config" class="chart-container">
                <ChartRenderer :config="msg.chart_config" :data="msg.chart_data" />
              </div>
            </div>
          </div>
        </div>

        <!-- Loading Indicator -->
        <div v-if="isLoading" class="message assistant">
          <div class="message-avatar">
            <el-icon :size="20"><Monitor /></el-icon>
          </div>
          <div class="message-content">
            <div class="loading-steps">
              <div v-for="(step, i) in loadingSteps" :key="i" class="step-item">
                <el-icon class="step-icon"><Loading /></el-icon>
                <span>{{ step }}</span>
              </div>
              <div v-if="loadingSteps.length === 0" class="step-item">
                <el-icon class="step-icon"><Loading /></el-icon>
                <span>正在分析您的问题...</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="input-area">
        <el-input
          v-model="inputText"
          :placeholder="isLoading ? '正在分析中，请稍候...' : '输入您的问题，例如：上个月销量最高的产品是哪些？'"
          :disabled="isLoading"
          size="large"
          @keyup.enter="handleSend"
          class="chat-input"
        >
          <template #append>
            <el-button
              type="primary"
              :disabled="!inputText.trim() || isLoading"
              @click="handleSend"
            >
              <el-icon><Promotion /></el-icon>
              发送
            </el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- EXPLAIN Dialog -->
    <ExplainDialog v-model:visible="explainVisible" :sql="explainSql" />

    <!-- Performance Panel (collapsible at bottom of sidebar) -->
    <div v-if="showPerf" class="perf-overlay">
      <PerformancePanel />
      <el-button size="small" class="perf-close" @click="showPerf = false">收起</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  askQuestion, askQuestionStream, executeSql,
  listConversations, getConversation, deleteConversation, createConversation
} from '../api'
import ChartRenderer from '../components/ChartRenderer.vue'
import ExplainDialog from '../components/ExplainDialog.vue'
import PerformancePanel from '../components/PerformancePanel.vue'

const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const loadingSteps = ref([])
const currentConvId = ref(null)

// EXPLAIN dialog state
const explainVisible = ref(false)
const explainSql = ref('')
const showExplain = (sql) => {
  explainSql.value = sql
  explainVisible.value = true
}

// Performance panel toggle
const showPerf = ref(false)
const conversations = ref([])
const messagesRef = ref(null)

const exampleQuestions = [
  '上个月销量最高的5个产品是哪些？',
  '各城市客户数量排名前10',
  '最近3个月每月的订单金额趋势',
  '不同会员等级的客户平均消费是多少？',
  '评分最高的商品有哪些？',
  '各支付方式的订单占比是多少？',
]

// ── Markdown Rendering ──
const renderMarkdown = (text) => {
  if (!text) return ''
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/```sql\n([\s\S]*?)```/g, '<pre class="sql-inline"><code>$1</code></pre>')
    .replace(/```json\n([\s\S]*?)```/g, '')
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/\n/g, '<br/>')
}

// ── Send Message ──
const handleSend = async () => {
  const question = inputText.value.trim()
  if (!question || isLoading.value) return

  inputText.value = ''
  messages.value.push({ role: 'user', content: question })
  isLoading.value = true
  loadingSteps.value = []
  scrollToBottom()

  try {
    const response = await askQuestion(question, currentConvId.value)
    const data = response.data

    // Update conversation ID
    if (!currentConvId.value) {
      // Refresh conversation list
      await loadConversations()
      // The new conversation should be the first one
      if (conversations.value.length > 0) {
        currentConvId.value = conversations.value[0].id
      }
    }

    // Extract chart data from the SQL result if available
    const chartData = await fetchChartData(data.sql, data.chart_config)

    messages.value.push({
      role: 'assistant',
      content: data.answer,
      sql: data.sql,
      chart_config: data.chart_config,
      chart_data: chartData,
      cached: data.cached,
      execution_time_ms: data.execution_time_ms,
    })
  } catch (error) {
    console.error('Query failed:', error)
    ElMessage.error('查询失败，请稍后重试')
    messages.value.push({
      role: 'assistant',
      content: '抱歉，分析过程中出现了错误：' + (error.response?.data?.detail || error.message),
    })
  } finally {
    isLoading.value = false
    loadingSteps.value = []
    scrollToBottom()
  }
}

const sendExample = (q) => {
  inputText.value = q
  handleSend()
}

// ── Chart Data Extraction ──
const fetchChartData = async (sql, chartConfig) => {
  if (!sql || !chartConfig) return null
  // Skip chart for 'number' type or 'table' type — they don't need chart rendering
  if (chartConfig.chart_type === 'table') return null
  try {
    const res = await executeSql(sql)
    if (res.data.columns && res.data.rows) {
      return { columns: res.data.columns, rows: res.data.rows }
    }
  } catch (e) {
    console.warn('Failed to fetch chart data:', e)
  }
  return null
}

// ── Conversations ──
const loadConversations = async () => {
  try {
    const res = await listConversations()
    conversations.value = res.data
  } catch (e) {
    console.error('Failed to load conversations:', e)
  }
}

const selectConversation = async (id) => {
  try {
    currentConvId.value = id
    const res = await getConversation(id)
    const conv = res.data
    messages.value = (conv.messages || []).map(msg => ({
      role: msg.role,
      content: msg.content,
      sql: msg.metadata?.sql || '',
      chart_config: msg.metadata?.chart_config || null,
      cached: msg.metadata?.cached || false,
      execution_time_ms: msg.metadata?.execution_time_ms || null,
    }))
    scrollToBottom()
  } catch (e) {
    ElMessage.error('加载对话失败')
  }
}

const handleNewChat = () => {
  currentConvId.value = null
  messages.value = []
}

const handleDeleteConv = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该对话？', '提示', { type: 'warning' })
    await deleteConversation(id)
    await loadConversations()
    if (currentConvId.value === id) {
      handleNewChat()
    }
  } catch (e) {
    // Cancelled
  }
}

// ── Scroll ──
const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

onMounted(() => {
  loadConversations()
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
}

/* ── Conversation Sidebar ── */
.conv-sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
}

.conv-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.new-chat-btn {
  width: 100%;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 2px;
}

.conv-item:hover {
  background: #f5f7fa;
}

.conv-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.conv-title {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-delete {
  opacity: 0;
  color: #999;
  transition: opacity 0.2s;
}

.conv-item:hover .conv-delete {
  opacity: 1;
}

/* ── Main Chat ── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f8f9fc;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* ── Welcome Screen ── */
.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #666;
}

.welcome-screen h2 {
  margin: 16px 0 8px;
  color: #333;
}

.welcome-screen p {
  margin-bottom: 32px;
  max-width: 500px;
}

.example-questions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  max-width: 600px;
}

.example-q {
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
  text-align: left;
}

.example-q:hover {
  border-color: #409eff;
  color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

/* ── Messages ── */
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
}

.message.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: #409eff;
  color: #fff;
}

.message.assistant .message-avatar {
  background: #e94560;
  color: #fff;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.user-text {
  background: #409eff;
  color: #fff;
  padding: 10px 16px;
  border-radius: 12px 12px 4px 12px;
  font-size: 14px;
  line-height: 1.6;
}

.assistant-content {
  background: #fff;
  padding: 16px;
  border-radius: 12px 12px 12px 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

/* ── SQL Block ── */
.sql-block {
  background: #1e1e2e;
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}

.sql-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #2d2d44;
  color: #a8a8b3;
  font-size: 12px;
}

.sql-code {
  padding: 12px;
  margin: 0;
  color: #a6e3a1;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  overflow-x: auto;
  white-space: pre-wrap;
}

/* ── Answer Text ── */
.answer-text {
  font-size: 14px;
  line-height: 1.8;
  color: #333;
}

.answer-text :deep(strong) {
  color: #e94560;
}

.answer-text :deep(.sql-inline) {
  background: #1e1e2e;
  border-radius: 6px;
  padding: 8px 12px;
  margin: 8px 0;
}

.answer-text :deep(.sql-inline code) {
  color: #a6e3a1;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
}

/* ── Chart ── */
.chart-container {
  margin-top: 16px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
}

/* ── Loading ── */
.loading-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #666;
}

.step-icon {
  animation: spin 1s linear infinite;
  color: #409eff;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ── Input ── */
.input-area {
  padding: 16px 20px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
}

.chat-input :deep(.el-input__wrapper) {
  border-radius: 12px;
}

/* ── EXPLAIN Button ── */
.explain-btn {
  margin-left: auto;
  color: #a8a8b3;
  font-size: 12px;
}

.explain-btn:hover {
  color: #409eff;
}

/* ── Performance Panel Overlay ── */
.perf-overlay {
  position: fixed;
  bottom: 16px;
  right: 16px;
  width: 480px;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  border-radius: 12px;
}

.perf-close {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
}

/* ── Perf Toggle Button ── */
.perf-toggle {
  margin-top: auto;
  padding: 8px 16px;
  border-top: 1px solid #f0f0f0;
}
</style>
