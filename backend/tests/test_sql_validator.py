"""Unit tests for SQL Safety Validator.

Covers:
- SELECT / WITH statements allowed
- DDL/DML keywords blocked (DROP, DELETE, UPDATE, INSERT, etc.)
- Auto LIMIT append
- Comment stripping
- Edge cases (empty, whitespace, semicolons)
"""

import pytest

from app.core.sql_validator import SQLValidator, SQLValidationError


@pytest.fixture
def v():
    return SQLValidator()


# ── Valid SQL ──

class TestValidSQL:
    """SELECT and WITH queries should pass validation."""

    def test_simple_select(self, v):
        sql = "SELECT * FROM products"
        result = v.validate(sql)
        assert "SELECT" in result
        assert "LIMIT 100" in result

    def test_select_with_where(self, v):
        sql = "SELECT name, price FROM products WHERE price > 100"
        result = v.validate(sql)
        assert "LIMIT 100" in result

    def test_select_with_join(self, v):
        sql = """
            SELECT p.name, SUM(oi.quantity)
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            GROUP BY p.name
            ORDER BY SUM(oi.quantity) DESC
        """
        result = v.validate(sql)
        assert "LIMIT 100" in result

    def test_with_cte(self, v):
        sql = """
            WITH monthly AS (
                SELECT MONTH(created_at) AS m, COUNT(*) AS cnt
                FROM orders GROUP BY m
            )
            SELECT * FROM monthly WHERE cnt > 100
        """
        result = v.validate(sql)
        assert "WITH" in result

    def test_select_with_existing_limit(self, v):
        sql = "SELECT * FROM products LIMIT 50"
        result = v.validate(sql)
        # Should NOT double-append LIMIT
        assert result.count("LIMIT") == 1
        assert "LIMIT 50" in result

    def test_select_with_limit_1000(self, v):
        sql = "SELECT * FROM orders LIMIT 1000"
        result = v.validate(sql)
        assert "LIMIT 1000" in result

    def test_semicolon_stripped(self, v):
        sql = "SELECT * FROM products;"
        result = v.validate(sql)
        # Semicolon is stripped, LIMIT appended
        assert result.endswith("LIMIT 100")
        assert ";;" not in result

    def test_subquery_select(self, v):
        sql = "SELECT * FROM (SELECT id, name FROM products) AS sub WHERE id < 10"
        result = v.validate(sql)
        assert "LIMIT 100" in result

    def test_case_insensitive_select(self, v):
        sql = "select * from products"
        result = v.validate(sql)
        assert "LIMIT 100" in result


# ── Blocked SQL ──

class TestBlockedSQL:
    """DDL/DML statements should be rejected."""

    def test_drop_table(self, v):
        with pytest.raises(SQLValidationError, match="DROP"):
            v.validate("DROP TABLE products")

    def test_delete(self, v):
        with pytest.raises(SQLValidationError, match="DELETE"):
            v.validate("DELETE FROM products WHERE id = 1")

    def test_update(self, v):
        with pytest.raises(SQLValidationError, match="UPDATE"):
            v.validate("UPDATE products SET price = 0 WHERE id = 1")

    def test_insert(self, v):
        with pytest.raises(SQLValidationError, match="INSERT"):
            v.validate("INSERT INTO products (name) VALUES ('test')")

    def test_alter_table(self, v):
        with pytest.raises(SQLValidationError, match="ALTER"):
            v.validate("ALTER TABLE products ADD COLUMN new_col INT")

    def test_truncate(self, v):
        with pytest.raises(SQLValidationError, match="TRUNCATE"):
            v.validate("TRUNCATE TABLE products")

    def test_create_table(self, v):
        with pytest.raises(SQLValidationError, match="CREATE"):
            v.validate("CREATE TABLE test (id INT)")

    def test_grant(self, v):
        with pytest.raises(SQLValidationError, match="GRANT"):
            v.validate("GRANT ALL PRIVILEGES ON *.* TO 'user'@'localhost'")

    def test_shutdown(self, v):
        with pytest.raises(SQLValidationError, match="SHUTDOWN"):
            v.validate("SELECT 1; SHUTDOWN")

    def test_into_outfile(self, v):
        with pytest.raises(SQLValidationError, match="INTO OUTFILE"):
            v.validate("SELECT * FROM products INTO OUTFILE '/tmp/test.csv'")


# ── Comment Handling ──

class TestComments:
    """Comments should be stripped before validation."""

    def test_line_comment(self, v):
        sql = "-- this is a comment\nSELECT * FROM products"
        result = v.validate(sql)
        assert "LIMIT 100" in result

    def test_block_comment(self, v):
        sql = "/* block comment */ SELECT * FROM products"
        result = v.validate(sql)
        assert "LIMIT 100" in result

    def test_comment_hiding_drop(self, v):
        """SELECT that hides DROP in a comment should still pass (comment is stripped)."""
        sql = "SELECT * FROM products -- DROP TABLE"
        result = v.validate(sql)
        assert "LIMIT 100" in result


# ── Edge Cases ──

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_sql(self, v):
        with pytest.raises(SQLValidationError):
            v.validate("")

    def test_whitespace_only(self, v):
        with pytest.raises(SQLValidationError):
            v.validate("   \n  \t  ")

    def test_show_tables_blocked(self, v):
        """SHOW is not SELECT/WITH, should be blocked."""
        with pytest.raises(SQLValidationError, match="SHOW"):
            v.validate("SHOW TABLES")

    def test_describe_blocked(self, v):
        with pytest.raises(SQLValidationError, match="DESCRIBE"):
            v.validate("DESCRIBE products")

    def test_sanitize_for_display(self):
        # strip() removes leading/trailing whitespace, rstrip(";") removes trailing semicolons
        result = SQLValidator.sanitize_for_display("  SELECT * FROM products  ;  ")
        assert result.endswith(";")
        assert "SELECT" in result
        assert "products" in result


# ── Keyword Boundary Tests ──

class TestKeywordBoundaries:
    """Ensure keywords are matched as whole words, not substrings."""

    def test_column_named_updated(self, v):
        """Column name 'updated_at' should not trigger UPDATE block."""
        sql = "SELECT id, updated_at FROM orders"
        result = v.validate(sql)
        assert "LIMIT 100" in result

    def test_column_named_insert_date(self, v):
        """Column containing 'insert' as substring should pass."""
        sql = "SELECT insert_date FROM orders"
        # 'INSERT' as whole word is blocked, but 'insert_date' is not a whole word match
        # Actually the regex \bINSERT\b would NOT match 'insert_date' because _ is a word boundary
        # Wait, underscore IS a word character in regex, so \bINSERT\b won't match INSERT_DATE
        result = v.validate(sql)
        assert "LIMIT 100" in result

    def test_table_named_deleted_items(self, v):
        """Table name 'deleted_items' should not trigger DELETE block."""
        sql = "SELECT * FROM deleted_items"
        # \bDELETE\b won't match 'deleted_items' (D is followed by D, not word boundary)
        # Actually 'DELETED' contains 'DELETE' + 'D', and \bDELETE\b matches 'DELETE' only if
        # followed by non-word char. 'DELETED' → DELETE is followed by D which is word char, so no match.
        result = v.validate(sql)
        assert "LIMIT 100" in result
