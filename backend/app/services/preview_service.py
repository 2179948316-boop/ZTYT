"""SQL Write Preview Service — safety net for UPDATE/DELETE operations.

When the Agent (or user) attempts a write operation:
1. The SQL validator intercepts it
2. This service converts it to a "preview SELECT" showing affected rows
3. The frontend displays the preview and asks for confirmation
4. On confirmation, the backend executes the actual write

This implements a "preview before execute" safety pattern, demonstrating
defense-in-depth for a resume project.
"""

import re
import logging
from dataclasses import dataclass

from sqlalchemy import text as sa_text

from app.core.database import BizSessionLocal

logger = logging.getLogger(__name__)


@dataclass
class PreviewResult:
    """Result of a write operation preview."""
    operation_type: str       # UPDATE / DELETE / INSERT
    preview_sql: str          # SELECT that shows affected rows
    affected_rows: int        # Number of rows that would be affected
    sample_data: list         # Sample rows (up to 10)
    columns: list             # Column names from preview
    original_sql: str         # The original write SQL


class PreviewService:
    """Converts write SQL into preview SELECT queries for safety confirmation."""

    # Regex patterns for parsing SQL
    UPDATE_PATTERN = re.compile(
        r"UPDATE\s+`?(\w+)`?\s+SET\s+(.+?)\s+WHERE\s+(.+)",
        re.IGNORECASE | re.DOTALL,
    )
    DELETE_PATTERN = re.compile(
        r"DELETE\s+FROM\s+`?(\w+)`?\s+WHERE\s+(.+)",
        re.IGNORECASE | re.DOTALL,
    )

    def detect_write(self, sql: str) -> str | None:
        """
        Detect if SQL is a write operation.
        Returns: 'UPDATE', 'DELETE', 'INSERT', or None (if read-only).
        """
        sql_clean = sql.strip().upper()
        # Remove comments
        sql_clean = re.sub(r"--[^\n]*", "", sql_clean)
        sql_clean = re.sub(r"/\*.*?\*/", "", sql_clean, flags=re.DOTALL)
        sql_clean = sql_clean.strip()

        first_word = sql_clean.split()[0] if sql_clean.split() else ""
        if first_word in ("UPDATE", "DELETE", "INSERT"):
            return first_word
        return None

    def generate_preview(self, sql: str) -> PreviewResult:
        """
        Convert a write SQL into a preview SELECT that shows affected rows.

        Strategy:
        - UPDATE ... WHERE condition → SELECT * FROM table WHERE condition
        - DELETE FROM table WHERE condition → SELECT * FROM table WHERE condition
        - INSERT ... → Preview the target table's current state
        """
        operation_type = self.detect_write(sql)
        if not operation_type:
            raise ValueError(f"Not a write operation: {sql[:50]}")

        if operation_type == "UPDATE":
            return self._preview_update(sql)
        elif operation_type == "DELETE":
            return self._preview_delete(sql)
        else:
            return self._preview_insert(sql)

    def _preview_update(self, sql: str) -> PreviewResult:
        """Convert UPDATE ... SET ... WHERE ... → SELECT * FROM ... WHERE ..."""
        match = self.UPDATE_PATTERN.match(sql.strip().rstrip(";"))
        if not match:
            # Fallback: try to extract table name and WHERE clause
            return self._fallback_preview(sql, "UPDATE")

        table_name = match.group(1)
        where_clause = match.group(3)
        preview_sql = f"SELECT * FROM `{table_name}` WHERE {where_clause} LIMIT 50"

        return self._execute_preview(preview_sql, sql, "UPDATE")

    def _preview_delete(self, sql: str) -> PreviewResult:
        """Convert DELETE FROM ... WHERE ... → SELECT * FROM ... WHERE ..."""
        match = self.DELETE_PATTERN.match(sql.strip().rstrip(";"))
        if not match:
            return self._fallback_preview(sql, "DELETE")

        table_name = match.group(1)
        where_clause = match.group(2)
        preview_sql = f"SELECT * FROM `{table_name}` WHERE {where_clause} LIMIT 50"

        return self._execute_preview(preview_sql, sql, "DELETE")

    def _preview_insert(self, sql: str) -> PreviewResult:
        """For INSERT, show the target table's current row count."""
        # Extract table name from INSERT INTO table_name
        match = re.search(r"INSERT\s+INTO\s+`?(\w+)`?", sql, re.IGNORECASE)
        if not match:
            return self._fallback_preview(sql, "INSERT")

        table_name = match.group(1)
        preview_sql = f"SELECT COUNT(*) AS current_rows FROM `{table_name}`"

        return self._execute_preview(preview_sql, sql, "INSERT")

    def _fallback_preview(self, sql: str, op_type: str) -> PreviewResult:
        """Fallback when SQL parsing fails — just return the info without preview."""
        return PreviewResult(
            operation_type=op_type,
            preview_sql="-- 无法自动解析，请人工确认",
            affected_rows=-1,
            sample_data=[],
            columns=[],
            original_sql=sql,
        )

    def _execute_preview(
        self, preview_sql: str, original_sql: str, op_type: str
    ) -> PreviewResult:
        """Execute the preview SELECT and return structured results."""
        try:
            with BizSessionLocal() as session:
                result = session.execute(sa_text(preview_sql))
                columns = list(result.keys())
                rows = [list(row) for row in result.fetchall()]

            # Convert non-serializable types
            for row in rows:
                for i, val in enumerate(row):
                    if hasattr(val, "__float__"):
                        row[i] = float(val)
                    elif hasattr(val, "isoformat"):
                        row[i] = val.isoformat()

            return PreviewResult(
                operation_type=op_type,
                preview_sql=preview_sql,
                affected_rows=len(rows),
                sample_data=rows[:10],  # Limit sample to 10 rows
                columns=columns,
                original_sql=original_sql,
            )
        except Exception as e:
            logger.warning(f"Preview execution failed: {e}")
            return PreviewResult(
                operation_type=op_type,
                preview_sql=preview_sql,
                affected_rows=-1,
                sample_data=[],
                columns=[],
                original_sql=original_sql,
            )

    def execute_write(self, sql: str) -> dict:
        """
        Execute a confirmed write operation.
        Only called after the user has reviewed the preview and confirmed.

        Returns: {"affected_rows": int, "success": bool, "message": str}
        """
        try:
            with BizSessionLocal() as session:
                result = session.execute(sa_text(sql))
                session.commit()
                affected = result.rowcount if hasattr(result, "rowcount") else 0

            return {
                "success": True,
                "affected_rows": affected,
                "message": f"操作成功，影响 {affected} 行",
            }
        except Exception as e:
            logger.error(f"Write execution failed: {e}")
            return {
                "success": False,
                "affected_rows": 0,
                "message": f"执行失败: {str(e)}",
            }


# Singleton
preview_service = PreviewService()
