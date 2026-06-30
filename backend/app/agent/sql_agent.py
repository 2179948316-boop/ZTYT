"""SQL Agent — LangGraph ReAct agent with custom SQL tools.

This is the brain of the application. The agent:
1. Receives a natural language question
2. Decides which tools to call (list tables → get schema → write SQL → execute)
3. Returns SQL + results + natural language analysis

Using langgraph's create_react_agent for a clean, debuggable ReAct loop.
"""

import logging
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from app.agent.tools import ALL_TOOLS, execute_query
from app.agent.few_shot import few_shot_store
from app.core.llm_provider import get_llm
from app.core.sql_validator import validator

logger = logging.getLogger(__name__)

# ── System Prompt ──
SYSTEM_PROMPT = """\
你是一个专业的电商数据分析师 AI 助手。你连接了一个电商数据库，需要帮助用户回答数据分析问题。

## 可用的数据库表
- categories: 商品类目（id, name, description, created_at）
- products: 商品（id, name, description, price, stock, category_id, status, created_at）
- customers: 客户（id, username, email, phone, gender, city, province, member_level, created_at）
- orders: 订单（id, customer_id, total_amount, status, payment_method, created_at, updated_at）
- order_items: 订单明细（id, order_id, product_id, quantity, unit_price, subtotal）
- reviews: 评价（id, product_id, customer_id, order_id, rating, content, created_at）

## 工作流程
1. 首先调用 list_tables 了解有哪些表（如果你已经知道表结构可以跳过）
2. 调用 get_table_schema 获取相关表的列定义
3. 根据表结构和问题，构造准确的 SELECT SQL
4. 调用 execute_query 执行 SQL 并获取结果
5. 分析结果，用自然语言回答用户的问题

## SQL 编写规范
- 只写 SELECT 语句（UPDATE/DELETE/INSERT/DROP 等会被安全拦截）
- JOIN 时使用正确的关联字段
- 聚合查询使用 GROUP BY
- 排名查询使用 ORDER BY + LIMIT
- 时间筛选使用 WHERE created_at BETWEEN
- 使用中文列别名提高可读性（如 SELECT count(*) AS 订单数）

## 输出格式
在最终回答中，请严格按以下格式输出：

**SQL：**
```sql
你执行的SQL语句
```

**分析：**
对查询结果的自然语言解读，包含关键数据点

**建议图表：** bar / line / pie / number / table
（bar=柱状图对比, line=折线图趋势, pie=饼图占比, number=单一指标数字, table=明细表格）

如果数据适合可视化，额外输出：

**图表配置：**
```json
{
  "chart_type": "bar",
  "title": "图表标题",
  "x_field": "X轴字段名",
  "y_field": "Y轴字段名",
  "x_label": "X轴标签",
  "y_label": "Y轴标签"
}
```
"""


def _build_dynamic_prompt(question: str) -> str:
    """
    Build a dynamic system prompt with few-shot examples retrieved from the vector store.

    This is "context engineering" — dynamically injecting relevant examples
    into the prompt to improve SQL generation accuracy, without fine-tuning.
    """
    prompt = SYSTEM_PROMPT

    # Retrieve similar examples from the vector store
    examples = few_shot_store.get_similar(question, k=3)

    if examples:
        prompt += "\n\n## 参考示例（Few-shot）\n"
        prompt += "以下是与你当前问题相似的已验证问答，请参考其 SQL 模式来构造你的查询：\n\n"
        for i, ex in enumerate(examples, 1):
            prompt += f"### 示例 {i}\n"
            prompt += f"**问题：** {ex['question']}\n"
            prompt += f"```sql\n{ex['sql']}\n```\n"
            if ex.get("description"):
                prompt += f"*说明：{ex['description']}*\n"
            prompt += "\n"

    return prompt


@dataclass
class AgentResult:
    """Structured result from the agent."""
    answer: str          # Natural language answer
    sql: str = ""        # The SQL that was executed
    chart_config: dict = None  # Chart rendering config
    steps: list = None   # Intermediate reasoning steps


def _extract_sql_from_messages(messages: list) -> str:
    """Extract the last executed SQL from agent message history."""
    sql = ""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name == "execute_query":
            # Find the preceding AI message that called execute_query
            for prev in reversed(messages[:messages.index(msg)]):
                if isinstance(prev, AIMessage) and prev.tool_calls:
                    for tc in prev.tool_calls:
                        if tc["name"] == "execute_query":
                            return tc["args"].get("sql", "")
    return sql


def _extract_chart_config(answer: str) -> dict | None:
    """Extract chart config from the agent's answer text."""
    import json
    import re

    # Look for JSON block after "图表配置"
    pattern = r'\*\*图表配置\*\*[：:]?\s*```json\s*(.*?)\s*```'
    match = re.search(pattern, answer, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Also try to find a standalone JSON block
    pattern2 = r'"chart_type"\s*:\s*"(\w+)"'
    match2 = re.search(pattern2, answer)
    if match2:
        try:
            # Find the full JSON object around chart_type
            json_pattern = r'\{[^{}]*"chart_type"[^{}]*\}'
            json_match = re.search(json_pattern, answer)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

    return None


class SQLAgentRunner:
    """Wraps the LangGraph ReAct agent for SQL analysis tasks."""

    def __init__(self):
        self.llm = get_llm()
        # Base agent (without few-shot) for fallback
        self.agent = create_react_agent(
            model=self.llm,
            tools=ALL_TOOLS,
            prompt=SYSTEM_PROMPT,
        )

    def _create_agent(self, question: str):
        """Create a per-query agent with dynamic few-shot prompt."""
        dynamic_prompt = _build_dynamic_prompt(question)
        return create_react_agent(
            model=self.llm,
            tools=ALL_TOOLS,
            prompt=dynamic_prompt,
        )

    def run(self, question: str) -> AgentResult:
        """Run the agent with a user question. Returns structured result."""
        try:
            # Create per-query agent with few-shot examples
            agent = self._create_agent(question)

            # Invoke the agent
            response = agent.invoke(
                {"messages": [HumanMessage(content=question)]}
            )

            messages = response.get("messages", [])

            # Extract the final answer (last AI message)
            answer = ""
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    answer = msg.content
                    break

            if not answer:
                answer = "抱歉，我未能生成分析结果。请尝试换个问法。"

            # Extract SQL from tool call history
            sql = _extract_sql_from_messages(messages)

            # Extract chart config
            chart_config = _extract_chart_config(answer)

            # Collect reasoning steps for debugging
            steps = []
            for msg in messages:
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        steps.append(f"[Tool Call] {tc['name']}({tc['args']})")
                elif isinstance(msg, ToolMessage):
                    steps.append(f"[Tool Result] {msg.name}: {msg.content[:200]}")

            return AgentResult(
                answer=answer,
                sql=sql,
                chart_config=chart_config,
                steps=steps,
            )

        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            return AgentResult(
                answer=f"分析过程中出现错误: {str(e)}",
                steps=[f"[Error] {str(e)}"],
            )

    def run_stream(self, question: str):
        """Stream agent execution for real-time feedback (SSE).

        Yields events: {"type": "step|sql|answer|chart|done", "data": ...}
        """
        import json as json_lib

        try:
            # Create per-query agent with few-shot examples
            agent = self._create_agent(question)
            response = agent.invoke(
                {"messages": [HumanMessage(content=question)]}
            )

            messages = response.get("messages", [])
            sql = ""
            answer = ""

            # Stream through messages
            for msg in messages:
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        yield {
                            "type": "step",
                            "data": f"正在调用 {tc['name']}...",
                        }

                elif isinstance(msg, ToolMessage):
                    if msg.name == "execute_query":
                        # Extract SQL from preceding AI message
                        for prev in reversed(messages[:messages.index(msg)]):
                            if isinstance(prev, AIMessage) and prev.tool_calls:
                                for tc in prev.tool_calls:
                                    if tc["name"] == "execute_query":
                                        sql = tc["args"].get("sql", "")
                                        yield {"type": "sql", "data": sql}
                                        break
                                break

                    yield {
                        "type": "step",
                        "data": f"{msg.name} 执行完成",
                    }

                elif isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    answer = msg.content

            # Send final answer
            if answer:
                yield {"type": "answer", "data": answer}
            else:
                yield {"type": "answer", "data": "抱歉，我未能生成分析结果。"}

            # Extract and send chart config
            chart_config = _extract_chart_config(answer)
            if chart_config:
                yield {"type": "chart", "data": chart_config}

            yield {"type": "done", "data": {"sql": sql}}

        except Exception as e:
            logger.error(f"Agent stream failed: {e}", exc_info=True)
            yield {"type": "error", "data": str(e)}


# Singleton
agent_runner = SQLAgentRunner()
