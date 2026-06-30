<template>
  <div class="datasource-page">
    <div class="page-header">
      <h2>数据源管理</h2>
      <el-button type="primary" @click="showAddDialog">
        <el-icon><Plus /></el-icon>
        添加数据源
      </el-button>
    </div>

    <!-- Current Data Source Info -->
    <el-card class="current-source" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>当前数据源</span>
          <el-tag type="success">已连接</el-tag>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="数据库">ecommerce_demo</el-descriptions-item>
        <el-descriptions-item label="主机">localhost:3306</el-descriptions-item>
        <el-descriptions-item label="数据表">
          <el-tag v-for="t in tables" :key="t" size="small" class="table-tag">{{ t }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="数据量">
          8,303 行（6 张表）
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- Table Details -->
    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>
        <span>数据表结构</span>
      </template>
      <el-collapse>
        <el-collapse-item v-for="t in tableDetails" :key="t.name" :title="`${t.name} - ${t.comment}`">
          <el-table :data="t.columns" size="small" stripe>
            <el-table-column prop="name" label="列名" width="160" />
            <el-table-column prop="type" label="类型" width="140" />
            <el-table-column prop="comment" label="注释" />
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- Other Data Sources -->
    <h3 style="margin: 24px 0 12px">其他数据源</h3>
    <el-table :data="dataSources" stripe v-loading="loading" empty-text="暂无其他数据源">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="host" label="主机" />
      <el-table-column prop="port" label="端口" width="80" />
      <el-table-column prop="database_name" label="数据库" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '活跃' : '离线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="table_count" label="表数量" width="80" />
    </el-table>

    <!-- Add Dialog -->
    <el-dialog v-model="addDialogVisible" title="添加数据源" width="500px">
      <el-form :model="newDs" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newDs.name" placeholder="例如：生产库" />
        </el-form-item>
        <el-form-item label="主机">
          <el-input v-model="newDs.host" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="newDs.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="newDs.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="newDs.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="数据库名">
          <el-input v-model="newDs.database_name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAdd" :loading="adding">测试连接并添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listDataSources, createDataSource } from '../api'

const tables = ['categories', 'products', 'customers', 'orders', 'order_items', 'reviews']

const tableDetails = [
  {
    name: 'categories', comment: '商品类目表',
    columns: [
      { name: 'id', type: 'INT AUTO_INCREMENT', comment: '主键' },
      { name: 'name', type: 'VARCHAR(50)', comment: '类目名称' },
      { name: 'description', type: 'VARCHAR(200)', comment: '类目描述' },
      { name: 'created_at', type: 'DATETIME', comment: '创建时间' },
    ],
  },
  {
    name: 'products', comment: '商品表',
    columns: [
      { name: 'id', type: 'INT AUTO_INCREMENT', comment: '主键' },
      { name: 'name', type: 'VARCHAR(150)', comment: '商品名称' },
      { name: 'description', type: 'TEXT', comment: '商品描述' },
      { name: 'price', type: 'DECIMAL(10,2)', comment: '价格(元)' },
      { name: 'stock', type: 'INT', comment: '库存数量' },
      { name: 'category_id', type: 'INT', comment: '类目ID' },
      { name: 'status', type: 'VARCHAR(20)', comment: '状态' },
      { name: 'created_at', type: 'DATETIME', comment: '上架时间' },
    ],
  },
  {
    name: 'customers', comment: '客户表',
    columns: [
      { name: 'id', type: 'INT AUTO_INCREMENT', comment: '主键' },
      { name: 'username', type: 'VARCHAR(50)', comment: '用户名' },
      { name: 'email', type: 'VARCHAR(100)', comment: '邮箱' },
      { name: 'phone', type: 'VARCHAR(20)', comment: '手机号' },
      { name: 'gender', type: 'VARCHAR(10)', comment: '性别' },
      { name: 'city', type: 'VARCHAR(50)', comment: '城市' },
      { name: 'province', type: 'VARCHAR(50)', comment: '省份' },
      { name: 'member_level', type: 'VARCHAR(20)', comment: '会员等级' },
      { name: 'created_at', type: 'DATETIME', comment: '注册时间' },
    ],
  },
  {
    name: 'orders', comment: '订单表',
    columns: [
      { name: 'id', type: 'INT AUTO_INCREMENT', comment: '主键' },
      { name: 'customer_id', type: 'INT', comment: '客户ID' },
      { name: 'total_amount', type: 'DECIMAL(10,2)', comment: '订单总金额' },
      { name: 'status', type: 'VARCHAR(20)', comment: '状态' },
      { name: 'payment_method', type: 'VARCHAR(20)', comment: '支付方式' },
      { name: 'created_at', type: 'DATETIME', comment: '下单时间' },
      { name: 'updated_at', type: 'DATETIME', comment: '更新时间' },
    ],
  },
  {
    name: 'order_items', comment: '订单明细表',
    columns: [
      { name: 'id', type: 'INT AUTO_INCREMENT', comment: '主键' },
      { name: 'order_id', type: 'INT', comment: '订单ID' },
      { name: 'product_id', type: 'INT', comment: '商品ID' },
      { name: 'quantity', type: 'INT', comment: '购买数量' },
      { name: 'unit_price', type: 'DECIMAL(10,2)', comment: '单价' },
      { name: 'subtotal', type: 'DECIMAL(10,2)', comment: '小计金额' },
    ],
  },
  {
    name: 'reviews', comment: '评价表',
    columns: [
      { name: 'id', type: 'INT AUTO_INCREMENT', comment: '主键' },
      { name: 'product_id', type: 'INT', comment: '商品ID' },
      { name: 'customer_id', type: 'INT', comment: '客户ID' },
      { name: 'order_id', type: 'INT', comment: '订单ID' },
      { name: 'rating', type: 'INT', comment: '评分(1-5)' },
      { name: 'content', type: 'TEXT', comment: '评价内容' },
      { name: 'created_at', type: 'DATETIME', comment: '评价时间' },
    ],
  },
]

const dataSources = ref([])
const loading = ref(false)
const addDialogVisible = ref(false)
const adding = ref(false)
const newDs = reactive({
  name: '',
  host: 'localhost',
  port: 3306,
  username: 'root',
  password: '',
  database_name: '',
})

const showAddDialog = () => {
  addDialogVisible.value = true
}

const handleAdd = async () => {
  adding.value = true
  try {
    const res = await createDataSource(newDs)
    if (res.data.status === 'connected') {
      ElMessage.success(`连接成功，发现 ${res.data.table_count} 张表`)
      addDialogVisible.value = false
      loadDataSources()
    } else {
      ElMessage.error(`连接失败: ${res.data.error}`)
    }
  } catch (e) {
    ElMessage.error('添加失败')
  } finally {
    adding.value = false
  }
}

const loadDataSources = async () => {
  loading.value = true
  try {
    const res = await listDataSources()
    dataSources.value = res.data
  } catch (e) {
    console.error('Failed to load data sources:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadDataSources())
</script>

<style scoped>
.datasource-page {
  padding: 24px;
  height: 100vh;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #333;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.table-tag {
  margin: 2px 4px 2px 0;
}
</style>
