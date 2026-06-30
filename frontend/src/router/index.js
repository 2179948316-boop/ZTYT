import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Chat',
    component: () => import('../views/Chat.vue'),
    meta: { title: '智能问答' },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '数据看板' },
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/History.vue'),
    meta: { title: '查询历史' },
  },
  {
    path: '/datasource',
    name: 'DataSource',
    component: () => import('../views/DataSource.vue'),
    meta: { title: '数据源管理' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
