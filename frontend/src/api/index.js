import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, // 5 min for agent
})

// ── Chat / Query ──
export const askQuestion = (question, conversationId = null) =>
  api.post('/ask', { question, conversation_id: conversationId })

export const askQuestionStream = (question, conversationId = null) => {
  // Returns a fetch-based SSE stream (axios doesn't support SSE natively)
  return fetch('/api/ask/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  })
}

// ── Conversations ──
export const listConversations = () => api.get('/conversations')
export const createConversation = (title = '新对话') => api.post('/conversations', { title })
export const getConversation = (id) => api.get(`/conversations/${id}`)
export const deleteConversation = (id) => api.delete(`/conversations/${id}`)

// ── History ──
export const getHistory = (page = 1, pageSize = 20) =>
  api.get('/history', { params: { page, page_size: pageSize } })

// ── Data Sources ──
export const listDataSources = () => api.get('/datasources')
export const createDataSource = (data) => api.post('/datasources', data)

// ── Chart / SQL Execution ──
export const executeSql = (sql) => api.post('/execute-sql', { sql })

// ── SQL Write Preview & Confirm ──
export const sqlPreview = (sql) => api.post('/sql/preview', { sql })
export const sqlConfirm = (sql) => api.post('/sql/confirm', { sql })

// ── SQL EXPLAIN ──
export const sqlExplain = (sql) => api.post('/sql/explain', { sql })

// ── Performance Stats ──
export const getPerformanceStats = (limit = 50) =>
  api.get('/performance/stats', { params: { limit } })

// ── Dashboard ──
export const getDashboardStats = () => api.get('/dashboard/stats')
export const getDashboardModule = (key) => api.get(`/dashboard/stats/${key}`)

// ── Health ──
export const healthCheck = () => api.get('/health')

export default api
