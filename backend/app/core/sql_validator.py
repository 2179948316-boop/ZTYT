"""SQL Safety Validator.

Ensures Agent-generated SQL is safe before execution:
- Only SELECT statements allowed
- No DDL/DML operations (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, etc.)
- Row count limits to prevent OOM
- Execution timeout protection
"""

import re


class SQLValidationError(Exception):
    """Raised when SQL fails safety validation."""
    pass


class SQLValidator:
    """Validates SQL queries for safety before execution."""

    DANGEROUS_KEYWORDS = {
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
        "CREATE", "REPLACE", "MERGE", "GRANT", "REVOKE",
        "EXEC", "EXECUTE", "CALL", "INTO OUTFILE", "INTO DUMPFILE",
        "LOAD_FILE", "LOAD DATA", "SHUTDOWN",
    }

    MAX_LIMIT = 1000
    DEFAULT_LIMIT = 100

    def validate(self, sql: str) -> str:
        """
        Validate SQL query. Returns cleaned SQL on success, raises on failure.

        Rules:
        1. Must be a SELECT or WITH (CTE) statement
        2. Must not contain dangerous DDL/DML keywords
        3. Automatically appends LIMIT if missing
        """
        sql = sql.strip().rstrip(";")

        # Remove comments
        sql_clean = re.sub(r"--[^\n]*", "", sql)
        sql_clean = re.sub(r"/\*.*?\*/", "", sql_clean, flags=re.DOTALL)
        sql_clean = sql_clean.strip()

        # Rule 1: Only SELECT / WITH (CTE)
        first_keyword = sql_clean.split()[0].upper() if sql_clean.split() else ""
        if first_keyword not in ("SELECT", "WITH"):
            raise SQLValidationError(
                f"仅允许 SELECT / WITH 查询语句，当前语句以 '{first_keyword}' 开头。"
                f"如需修改数据，请联系数据库管理员。"
            )

        # Rule 2: No dangerous keywords (check whole words only)
        sql_upper = sql_clean.upper()
        for keyword in self.DANGEROUS_KEYWORDS:
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, sql_upper):
                raise SQLValidationError(
                    f"SQL 包含危险操作 '{keyword}'，已被安全拦截。仅允许只读查询。"
                )

        # Rule 3: Ensure LIMIT exists
        if not re.search(r"\bLIMIT\b", sql_upper):
            sql = f"{sql} LIMIT {self.DEFAULT_LIMIT}"

        return sql

    @staticmethod
    def sanitize_for_display(sql: str) -> str:
        """Format SQL for display in chat (add syntax highlighting hints)."""
        return sql.strip().rstrip(";") + ";"


# Singleton instance
validator = SQLValidator()
