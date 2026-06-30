<template>
  <el-container class="app-container">
    <el-aside width="240px" class="app-sidebar">
      <div class="sidebar-header">
        <el-icon :size="24"><DataAnalysis /></el-icon>
        <span class="app-title">智能数据分析</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </el-menu-item>
        <el-menu-item index="/dashboard">
          <el-icon><TrendCharts /></el-icon>
          <span>数据看板</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <span>查询历史</span>
        </el-menu-item>
        <el-menu-item index="/datasource">
          <el-icon><Coin /></el-icon>
          <span>数据源管理</span>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-footer">
        <el-tag type="success" size="small">NL2SQL Agent</el-tag>
        <p class="version-text">v1.0.0</p>
      </div>
    </el-aside>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-container {
  height: 100vh;
}

.app-sidebar {
  background: #1a1a2e;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #16213e;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #e94560;
  border-bottom: 1px solid #16213e;
}

.app-title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.sidebar-menu {
  flex: 1;
  background: transparent;
  border-right: none;
  padding-top: 10px;
}

.sidebar-menu .el-menu-item {
  color: #a8a8b3;
  margin: 4px 8px;
  border-radius: 8px;
}

.sidebar-menu .el-menu-item:hover {
  background: #16213e;
  color: #fff;
}

.sidebar-menu .el-menu-item.is-active {
  background: #0f3460;
  color: #e94560;
}

.sidebar-footer {
  padding: 16px 20px;
  text-align: center;
  border-top: 1px solid #16213e;
}

.version-text {
  color: #666;
  font-size: 12px;
  margin-top: 8px;
}

.app-main {
  background: #f5f7fa;
  padding: 0;
  overflow: hidden;
}
</style>
