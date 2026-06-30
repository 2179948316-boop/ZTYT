"""Custom LangChain tools for the SQL Agent.

These tools let the Agent interact with the business database:
- list_tables: discover available tables
- get_table_schema: inspect column definitions
- execute_query: run safe SELECT queries

Each tool is a plain Python function wrapped with @tool, making the
Agent's decision process transparent and debuggable — key for a resume project.
"""

from langchain_core.tools import tool
from sqlalchemy import text

from app.core.database import BizSessionLocal
from app.core.sql_validator import validator


@tool
def list_tables() -> str:
    """列出数据库中所有可用的表名。当你不确定有哪些表时，首先调用此工具。"""
    try:
        with BizSessionLocal() as session:
            result = session.execute(
                text("SELECT table_name FROM information_schema.tables "
                     "WHERE table_schema = DATABASE() ORDER BY table_name")
            )
            tables = [row[0] for row in result]
            return f"数据库包含 {len(tables)} 张表：\n" + "\n".join(f"  - {t}" for t in tables)
    except Exception as e:
        return f"获取表列表失败: {e}"


@tool
def get_table_schema(table_name: str) -> str:
    """获取指定表的列名、数据类型和注释信息。在写 SQL 之前，必须先调用此工具了解表结构。"""
    try:
        with BizSessionLocal() as session:
            result = session.execute(
                text("SELECT column_name, data_type, column_comment, is_nullable "
                     "FROM information_schema.columns "
                     "WHERE table_schema = DATABASE() AND table_name = :table_name "
                     "ORDER BY ordinal_position"),
                {"table_name": table_name},
            )
            rows = result.fetchall()
            if not rows:
                return f"表 '{table_name}' 不存在，请检查表名是否正确。"

            lines = [f"表: {table_name} ({len(rows)} 列)"]
            lines.append("-" * 50)
            for col, dtype, comment, nullable in rows:
                null_str = "" if nullable == "YES" else " NOT NULL"
                comment_str = f"  -- {comment}" if comment else ""
                lines.append(f"  {col:<20} {dtype:<20}{null_str}{comment_str}")

            # Also get row count
            count_result = session.execute(
                text(f"SELECT COUNT(*) FROM `{table_name}`")
            )
            count = count_result.scalar()
            lines.append(f"\n总行数: {count:,}")

            return "\n".join(lines)
    except Exception as e:
        return f"获取表 '{table_name}' 结构失败: {e}"


@tool
def execute_query(sql: str) -> str:
    """执行 SELECT 查询语句并返回结果。仅允许只读 SELECT 语句，会自动进行安全校验。

    Args:
        sql: 要执行的 SELECT SQL 查询语句
    """
    try:
        # Security validation
        sql = validator.validate(sql)

        with BizSessionLocal() as session:
            result = session.execute(text(sql))
            columns = list(result.keys())
            rows = result.fetchall()

        if not rows:
            return "查询成功，但没有返回数据（0 行）。可能条件不匹配，请检查 WHERE 条件。"

        # Format as readable text
        header = " | ".join(columns)
        separator = "-" * len(header)
        data_lines = []
        for row in rows:
            data_lines.append(" | ".join(str(v) if v is not None else "NULL" for v in row))

        output = (
            f"查询成功，返回 {len(rows)} 行数据：\n\n"
            f"列: {', '.join(columns)}\n"
            f"{header}\n"
            f"{separator}\n"
        )
        output += "\n".join(data_lines)

        if len(rows) >= validator.DEFAULT_LIMIT:
            output += f"\n\n（已截断到 {validator.DEFAULT_LIMIT} 行，实际数据可能更多）"

        return output

    except Exception as e:
        error_msg = str(e)
        if "1146" in error_msg:
            return f"表不存在，请先调用 get_table_schema 确认表名。错误: {error_msg}"
        elif "1054" in error_msg:
            return f"列名不存在，请先调用 get_table_schema 确认列名。错误: {error_msg}"
        elif "1064" in error_msg:
            return f"SQL 语法错误，请检查语句。错误: {error_msg}"
        else:
            return f"查询执行失败: {error_msg}"


# Export all tools
ALL_TOOLS = [list_tables, get_table_schema, execute_query]
