"""Unit tests for Agent Tools (list_tables, get_table_schema, execute_query).

Uses unittest.mock to patch database sessions, avoiding real MySQL connections.
Tests the tool logic: SQL construction, error handling, output formatting.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.core.sql_validator import SQLValidationError


# ── Fixtures ──

@pytest.fixture
def mock_biz_session():
    """Mock the BizSessionLocal context manager."""
    with patch("app.agent.tools.BizSessionLocal") as mock_cls:
        mock_session = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_session


# ── list_tables Tests ──

class TestListTables:
    """Test the list_tables tool."""

    def test_returns_table_names(self, mock_biz_session):
        from app.agent.tools import list_tables

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(
            return_value=iter([("products",), ("orders",), ("customers",)])
        )
        mock_biz_session.execute.return_value = mock_result

        result = list_tables.invoke({})
        assert "3 张表" in result
        assert "products" in result
        assert "orders" in result
        assert "customers" in result

    def test_handles_db_error(self, mock_biz_session):
        from app.agent.tools import list_tables

        mock_biz_session.execute.side_effect = Exception("Connection refused")
        result = list_tables.invoke({})
        assert "失败" in result

    def test_empty_database(self, mock_biz_session):
        from app.agent.tools import list_tables

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_biz_session.execute.return_value = mock_result

        result = list_tables.invoke({})
        assert "0 张表" in result


# ── get_table_schema Tests ──

class TestGetTableSchema:
    """Test the get_table_schema tool."""

    def test_returns_schema_with_columns(self, mock_biz_session):
        from app.agent.tools import get_table_schema

        # First call: column info
        col_result = MagicMock()
        col_result.fetchall.return_value = [
            ("id", "int", "主键", "NO"),
            ("name", "varchar(200)", "商品名称", "NO"),
            ("price", "decimal(10,2)", "单价", "NO"),
        ]

        # Second call: row count
        count_result = MagicMock()
        count_result.scalar.return_value = 200

        mock_biz_session.execute.side_effect = [col_result, count_result]

        result = get_table_schema.invoke({"table_name": "products"})
        assert "products" in result
        assert "3 列" in result
        assert "id" in result
        assert "name" in result
        assert "price" in result
        assert "200" in result

    def test_nonexistent_table(self, mock_biz_session):
        from app.agent.tools import get_table_schema

        col_result = MagicMock()
        col_result.fetchall.return_value = []
        mock_biz_session.execute.return_value = col_result

        result = get_table_schema.invoke({"table_name": "nonexistent_table"})
        assert "不存在" in result

    def test_handles_db_error(self, mock_biz_session):
        from app.agent.tools import get_table_schema

        mock_biz_session.execute.side_effect = Exception("Access denied")
        result = get_table_schema.invoke({"table_name": "products"})
        assert "失败" in result

    def test_not_null_display(self, mock_biz_session):
        from app.agent.tools import get_table_schema

        col_result = MagicMock()
        col_result.fetchall.return_value = [
            ("id", "int", "主键", "NO"),
            ("description", "text", "描述", "YES"),
        ]
        count_result = MagicMock()
        count_result.scalar.return_value = 10
        mock_biz_session.execute.side_effect = [col_result, count_result]

        result = get_table_schema.invoke({"table_name": "test"})
        assert "NOT NULL" in result


# ── execute_query Tests ──

class TestExecuteQuery:
    """Test the execute_query tool with safety validation."""

    def test_valid_select_returns_data(self, mock_biz_session):
        from app.agent.tools import execute_query

        mock_result = MagicMock()
        mock_result.keys.return_value = ["name", "price"]
        mock_result.fetchall.return_value = [
            ("Product A", 99.9),
            ("Product B", 199.5),
        ]
        mock_biz_session.execute.return_value = mock_result

        result = execute_query.invoke({"sql": "SELECT name, price FROM products LIMIT 5"})
        assert "2 行" in result
        assert "name" in result
        assert "price" in result
        assert "Product A" in result

    def test_empty_result(self, mock_biz_session):
        from app.agent.tools import execute_query

        mock_result = MagicMock()
        mock_result.keys.return_value = ["id"]
        mock_result.fetchall.return_value = []
        mock_biz_session.execute.return_value = mock_result

        result = execute_query.invoke({"sql": "SELECT id FROM products WHERE id = -1"})
        assert "没有返回数据" in result or "0 行" in result

    def test_dangerous_sql_blocked(self, mock_biz_session):
        from app.agent.tools import execute_query

        result = execute_query.invoke({"sql": "DROP TABLE products"})
        assert "安全拦截" in result or "仅允许" in result
        # Should NOT execute anything
        mock_biz_session.execute.assert_not_called()

    def test_delete_blocked(self, mock_biz_session):
        from app.agent.tools import execute_query

        result = execute_query.invoke({"sql": "DELETE FROM orders WHERE id = 1"})
        assert "安全拦截" in result or "仅允许" in result
        mock_biz_session.execute.assert_not_called()

    def test_update_blocked(self, mock_biz_session):
        from app.agent.tools import execute_query

        result = execute_query.invoke({"sql": "UPDATE products SET price = 0"})
        assert "安全拦截" in result or "仅允许" in result
        mock_biz_session.execute.assert_not_called()

    def test_table_not_found_error(self, mock_biz_session):
        from app.agent.tools import execute_query

        error = MagicMock()
        error.__str__ = MagicMock(return_value="(1146, Table 'test.xxx' doesn't exist)")
        mock_biz_session.execute.side_effect = Exception("(1146, Table 'test.xxx' doesn't exist)")

        result = execute_query.invoke({"sql": "SELECT * FROM xxx"})
        assert "表不存在" in result

    def test_column_not_found_error(self, mock_biz_session):
        from app.agent.tools import execute_query

        mock_biz_session.execute.side_effect = Exception("(1054, Unknown column 'xxx' in 'field list'")
        result = execute_query.invoke({"sql": "SELECT xxx FROM products"})
        assert "列名不存在" in result

    def test_syntax_error(self, mock_biz_session):
        from app.agent.tools import execute_query

        # Use a valid SELECT that passes the validator but fails at MySQL execution
        mock_biz_session.execute.side_effect = Exception("(1064, You have an error in your SQL syntax")
        result = execute_query.invoke({"sql": "SELECT * FORM products LIMIT 10"})
        assert "语法错误" in result

    def test_auto_limit_appended(self, mock_biz_session):
        """If SQL has no LIMIT, validator adds LIMIT 100."""
        from app.agent.tools import execute_query

        mock_result = MagicMock()
        mock_result.keys.return_value = ["id"]
        mock_result.fetchall.return_value = [(1,)]
        mock_biz_session.execute.return_value = mock_result

        execute_query.invoke({"sql": "SELECT id FROM products"})
        # Verify execute was called with SQL containing LIMIT
        call_args = mock_biz_session.execute.call_args
        executed_sql = str(call_args[0][0])
        assert "LIMIT" in executed_sql

    def test_result_truncation_warning(self, mock_biz_session):
        from app.agent.tools import execute_query

        mock_result = MagicMock()
        mock_result.keys.return_value = ["id"]
        # Simulate exactly DEFAULT_LIMIT (100) rows → truncation warning
        mock_result.fetchall.return_value = [(i,) for i in range(100)]
        mock_biz_session.execute.return_value = mock_result

        result = execute_query.invoke({"sql": "SELECT id FROM products"})
        assert "截断" in result


# ── Tool Metadata Tests ──

class TestToolMetadata:
    """Verify tools have proper LangChain metadata."""

    def test_all_tools_exported(self):
        from app.agent.tools import ALL_TOOLS
        assert len(ALL_TOOLS) == 3

    def test_tool_names(self):
        from app.agent.tools import ALL_TOOLS
        names = {t.name for t in ALL_TOOLS}
        assert "list_tables" in names
        assert "get_table_schema" in names
        assert "execute_query" in names

    def test_tools_have_descriptions(self):
        from app.agent.tools import ALL_TOOLS
        for t in ALL_TOOLS:
            assert t.description is not None
            assert len(t.description) > 10
