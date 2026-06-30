# 智能数据分析助手 (Smart Data Analyst)

> NL2SQL + Agent：用自然语言提问，AI 自动生成 SQL、执行查询、返回分析结论和可视化图表

## 技术栈

| 层       | 技术                                           |
|----------|------------------------------------------------|
| 后端     | FastAPI + LangChain + LangGraph + SQLAlchemy 2.0 |
| 前端     | Vue 3 + Element Plus + ECharts 5                |
| LLM     | DeepSeek API (OpenAI 兼容，可切换其他云端 API)    |
| 数据库   | MySQL 8.0 (业务库 + 应用库)                      |
| 缓存    | Redis (查询结果缓存 + 看板预计算，静默降级)        |
| 向量检索 | ChromaDB + jieba TF-IDF (Few-shot 示例匹配)      |
| 定时任务 | APScheduler (看板数据预计算)                      |

## 核心架构

```
用户自然语言提问
    ↓
Few-shot 动态示例检索 (ChromaDB + jieba TF-IDF)
    ↓ 注入 top-3 相似示例到 Prompt
LangGraph ReAct Agent (DeepSeek)
    ↓ Tool Calls
┌─────────────┬──────────────┬──────────────┐
│ list_tables │ get_schema   │ execute_query│  ← 自定义 LangChain Tools
└─────────────┴──────────────┴──────┬───────┘
                                     ↓
                         SQL 安全校验 (白名单)
                         + 写操作预览 (UPDATE/DELETE → SELECT)
                                     ↓
                           MySQL 执行 → 结果
                                     ↓
                     Agent 生成分析 + 图表推荐
                                     ↓
                    前端渲染: Markdown + SQL + ECharts
                    + 数据看板 (APScheduler 预计算 → Redis)
```

## 项目结构

```
smart-data-analyst/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + APScheduler 启动
│   │   ├── models.py            # ORM 模型 (对话/消息/查询日志)
│   │   ├── core/
│   │   │   ├── config.py        # 配置 (环境变量)
│   │   │   ├── database.py      # 双库连接 (业务库 + 应用库)
│   │   │   ├── llm_provider.py  # LLM 抽象层
│   │   │   └── sql_validator.py # SQL 安全校验
│   │   ├── agent/
│   │   │   ├── tools.py         # 自定义 LangChain Tools
│   │   │   ├── sql_agent.py     # Agent 编排 (LangGraph ReAct + Few-shot)
│   │   │   └── few_shot.py      # Few-shot 向量检索 (ChromaDB + jieba TF-IDF)
│   │   ├── services/
│   │   │   ├── query_service.py # 查询服务 + Redis 缓存
│   │   │   └── preview_service.py # SQL 写操作预览 (UPDATE/DELETE → SELECT)
│   │   ├── scheduler/
│   │   │   └── tasks.py         # 定时预计算任务 (7 个指标 → Redis)
│   │   └── api/
│   │       └── routes.py        # REST API 路由 (含 EXPLAIN + 性能对比)
│   ├── data/
│   │   ├── init_data.py         # Faker 电商数据生成器
│   │   └── seed_examples.py     # Few-shot 种子数据 (20 条问答对)
│   └── tests/                   # 单元测试 (70 个用例)
│       ├── test_sql_validator.py # SQL 校验测试 (24 cases)
│       ├── test_few_shot.py     # Few-shot 向量检索测试 (20 cases)
│       └── test_tools.py        # Agent 工具测试 (26 cases, Mock DB)
├── frontend/
│   └── src/
│       ├── views/Chat.vue       # 聊天界面 (含 EXPLAIN + 性能对比)
│       ├── views/Dashboard.vue  # 数据看板 (预计算可视化)
│       ├── views/History.vue    # 查询历史
│       ├── views/DataSource.vue # 数据源管理
│       ├── components/
│       │   ├── ChartRenderer.vue # ECharts 图表组件
│       │   ├── ExplainDialog.vue # SQL 执行计划可视化弹窗
│       │   └── PerformancePanel.vue # 查询性能对比面板
│       └── api/index.js         # Axios API 封装
└── README.md
```

## 依赖安装

### 系统环境

| 依赖           | 版本要求   | 说明                           |
|----------------|-----------|-------------------------------|
| Python         | >= 3.12   | 后端运行时                      |
| Node.js        | >= 20     | 前端构建工具链                   |
| MySQL          | 8.0       | 业务数据库 + 应用数据库           |
| Redis          | >= 5.0    | 查询缓存（可选，不可用时自动降级）  |

### 环境变量

```bash
# 必须设置
set DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# 可选（有默认值）
set BIZ_DB_HOST=localhost
set BIZ_DB_PORT=3306
set BIZ_DB_USER=root
set BIZ_DB_PASSWORD=123456
set BIZ_DB_NAME=ecommerce_demo
set APP_DB_NAME=smart_analyst
set REDIS_HOST=localhost
set REDIS_PORT=6379
```

### 后端 Python 依赖

```bash
cd backend
pip install -r requirements.txt
```

完整清单（requirements.txt）：

| 包名                | 版本     | 用途                          |
|---------------------|---------|-------------------------------|
| fastapi             | >=0.128 | Web 框架                      |
| uvicorn[standard]   | >=0.40  | ASGI 服务器                    |
| sqlalchemy          | >=2.0   | ORM / 数据库操作               |
| aiomysql            | >=0.3   | MySQL 异步驱动                 |
| pymysql             | >=1.2   | MySQL 同步驱动                 |
| redis               | >=8.0   | Redis 客户端（查询+看板缓存）   |
| langchain           | >=1.3   | LLM 编排框架                   |
| langchain-openai    | >=1.1   | OpenAI 兼容 API（DeepSeek）    |
| langchain-community | >=0.4   | LangChain 社区扩展             |
| langgraph           | >=0.5   | Agent 编排（ReAct）            |
| pydantic            | >=2.13  | 数据校验                       |
| pydantic-settings   | >=2.12  | 配置管理                       |
| faker               | >=37.0  | 生成示例电商数据                |
| chromadb            | >=1.0   | Few-shot 向量存储              |
| apscheduler         | >=3.11  | 定时预计算任务                  |
| jieba               | >=0.42  | 中文分词（Few-shot TF-IDF）     |

### 前端 npm 依赖

```bash
cd frontend
npm install
```

| 包名                      | 版本   | 用途                    |
|--------------------------|-------|-------------------------|
| vue                      | ^3.5  | 前端框架                 |
| vue-router               | ^4.5  | 路由管理                 |
| element-plus             | ^2.9  | UI 组件库                |
| @element-plus/icons-vue  | ^2.3  | Element Plus 图标        |
| axios                    | ^1.7  | HTTP 请求                |
| echarts                  | ^5.6  | 数据可视化图表            |
| highlight.js             | ^11.11| SQL 语法高亮              |
| markdown-it              | ^14.1 | Markdown 渲染             |
| @vitejs/plugin-vue       | ^5.2  | Vite Vue 插件（dev）      |
| vite                     | ^6.3  | 构建工具（dev）           |
| sass                     | ^1.80 | CSS 预处理器（dev）        |

## 快速启动

### 1. 生成示例数据

```bash
cd backend
python -X utf8 data/init_data.py
```

生成 6 张表、8300+ 行电商数据：
- categories (8 个类目)
- products (200 个商品)
- customers (500 个客户)
- orders (2,000 个订单)
- order_items (4,795 条明细)
- reviews (800 条评价)

### 2. 启动后端

```bash
cd backend
python -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 4. 访问

打开 http://localhost:5173

## API 端点

| 方法   | 路径                      | 说明                    |
|--------|---------------------------|------------------------|
| GET    | /health                   | 健康检查               |
| POST   | /api/ask                  | 自然语言提问 (同步)     |
| POST   | /api/ask/stream           | 自然语言提问 (SSE 流式) |
| POST   | /api/execute-sql          | 执行 SQL 返回结构化数据 |
| GET    | /api/conversations        | 对话列表               |
| POST   | /api/conversations        | 创建对话               |
| GET    | /api/conversations/{id}   | 对话详情 + 消息        |
| DELETE | /api/conversations/{id}   | 删除对话               |
| GET    | /api/history              | 查询历史 (分页)         |
| GET    | /api/datasources          | 数据源列表             |
| POST   | /api/datasources          | 添加数据源             |
| GET    | /api/dashboard/stats      | 看板预计算数据（全部）  |
| GET    | /api/dashboard/stats/{key}| 看板单模块数据          |
| POST   | /api/sql/preview          | SQL 写操作预览         |
| POST   | /api/sql/confirm          | SQL 写操作确认执行      |
| POST   | /api/sql/explain          | SQL 执行计划 (EXPLAIN)  |
| GET    | /api/performance/stats    | 查询性能对比数据        |

## 关键设计

### SQL 安全校验
- 仅允许 SELECT / WITH (CTE)
- 拦截 DDL/DML 关键词 (DROP, DELETE, UPDATE, INSERT 等)
- 自动追加 LIMIT 防止 OOM

### Redis 缓存
- SHA-256 哈希 key，1 小时 TTL
- Redis 不可用时静默降级，不影响主流程
- 相同问题二次查询 < 2ms（对比首次 ~8s）

### Agent 工具调用
- 自定义 3 个 LangChain Tool (非黑盒 Toolkit)
- Agent 自主决定调用顺序：list_tables → get_schema → execute_query
- 工具层与 Agent 编排分离，便于测试和扩展

## 升级特性

### 1. Few-shot 动态示例检索

每次用户提问时，系统从 ChromaDB 向量库中检索 top-3 最相似的历史问答对，注入到 Agent 的 System Prompt 中，显著提升 SQL 生成准确率。

关键设计：
- 使用 jieba 分词 + TF-IDF 构建自定义 Embedding（零模型下载，纯 CPU 计算）
- ChromaDB 内存向量库，启动时加载 20 条种子示例
- 按相似度动态注入，每次请求生成独立的 Agent 实例（带定制 Prompt）
- 覆盖 7 大查询类型：销量排行、趋势分析、分布占比、客户分析、商品评价、库存、复合查询

### 2. SQL 写操作预览与确认

当 Agent 或用户尝试 UPDATE/DELETE 操作时，系统不直接执行，而是：
1. 拦截写 SQL，转换为等价的 SELECT 预览（展示将被影响的行）
2. 前端显示预览表格和受影响行数，要求用户二次确认
3. 确认后通过 `/api/sql/confirm` 接口执行实际操作

实现原理：
- `PreviewService.detect_write()` 检测 SQL 首关键词判断写操作类型
- `PreviewService.generate_preview()` 用正则提取表名和 WHERE 条件，构造 `SELECT * FROM table WHERE ... LIMIT 50`
- `PreviewService.execute_write()` 仅在用户确认后执行，带事务保护

### 3. 定时预计算数据看板

使用 APScheduler 定期执行 7 个常用分析查询，将结果存入 Redis，前端看板页面直接读取缓存数据，加载时间从秒级降至毫秒级。

预计算任务：

| 任务 ID          | 说明           | 刷新间隔 |
|-----------------|---------------|---------|
| overview        | 总览统计        | 10 分钟 |
| top_products    | 热销商品 TOP10  | 10 分钟 |
| category_sales  | 类目销售分布     | 10 分钟 |
| daily_trend     | 近 30 天订单趋势 | 30 分钟 |
| payment_dist    | 支付方式分布     | 30 分钟 |
| city_ranking    | 城市客户排名     | 60 分钟 |
| member_analysis | 会员消费分析     | 60 分钟 |

前端数据看板页面包含：6 个总览数字卡片、热销商品柱状图、类目销售饼图、订单趋势双轴图、支付方式饼图、城市排名横向柱状图、会员消费柱状图。

### 4. SQL 执行计划可视化

在聊天界面每条 SQL 旁增加 EXPLAIN 按钮，点击弹出执行计划面板：
- 将 EXPLAIN 结果按访问类型分级标注：`ALL`（全表扫描/红色）→ `INDEX/RANGE`（索引扫描/橙色）→ `REF/eq_ref/const`（高效索引/绿色）
- 显示每个执行步骤的表名、访问类型、可用索引、实际使用索引、预估扫描行数、附加信息
- 附带原始 EXPLAIN 表格（可折叠），方便面试时展示对 MySQL 查询优化的理解

### 5. 查询性能对比面板

侧边栏底部「性能对比」按钮展开浮动面板，实时展示 Agent 耗时 vs 缓存命中耗时：
- 汇总统计卡片：总查询数、Agent 平均耗时、缓存平均耗时、加速比
- 柱状图对比：蓝色柱 = Agent 执行，绿色柱 = 缓存命中
- 数据来源于 `query_logs` 表的历史记录，真实反映 Redis 缓存带来的性能提升（实测加速比 ~9000x）

### 6. 单元测试覆盖

`backend/tests/` 目录包含 70 个测试用例，覆盖三个核心模块：

| 模块 | 测试数 | 覆盖内容 |
|------|-------|---------|
| sql_validator | 24 | SELECT/WITH 放行、DDL/DML 拦截、自动 LIMIT、注释剥离、关键词边界、边缘情况 |
| few_shot | 20 | jieba 分词、停用词过滤、IDF 计算、向量输出、向量存储增删查、语义相似度质量 |
| tools | 26 | list_tables 返回表名、get_table_schema 列信息、execute_query 安全校验/错误处理/截断、Mock DB 隔离 |

运行测试：
```bash
cd backend
python -m pytest tests/ -v
```
