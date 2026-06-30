"""Scheduled pre-computation tasks for the analytics dashboard.

Uses APScheduler to periodically pre-compute common analytics queries
and store results in Redis. This improves dashboard load time from
seconds to milliseconds for frequently-accessed metrics.

Tasks:
1. Top-selling products (updated every 10 min)
2. Category sales breakdown (updated every 10 min)
3. Daily order trend (updated every 30 min)
4. Payment method distribution (updated every 30 min)
5. Customer city ranking (updated every 1 hour)
6. Member level analysis (updated every 1 hour)
"""

import json
import logging
from datetime import datetime

import redis
from sqlalchemy import text as sa_text

from app.core.config import settings
from app.core.database import BizSessionLocal

logger = logging.getLogger(__name__)

# ── Redis connection ──
_redis: redis.Redis | None = None

try:
    _redis = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        decode_responses=True,
        socket_connect_timeout=2,
        protocol=2,
    )
    _redis.ping()
    logger.info("Scheduler Redis connected")
except Exception as e:
    logger.warning(f"Scheduler Redis unavailable: {e}")
    _redis = None


DASHBOARD_CACHE_PREFIX = "dashboard:"
DASHBOARD_CACHE_TTL = 1800  # 30 minutes


def _store_result(key: str, data: dict):
    """Store computed result in Redis with timestamp."""
    if not _redis:
        return
    try:
        payload = {
            "data": data,
            "computed_at": datetime.now().isoformat(),
            "cache_ttl": DASHBOARD_CACHE_TTL,
        }
        _redis.setex(
            f"{DASHBOARD_CACHE_PREFIX}{key}",
            DASHBOARD_CACHE_TTL,
            json.dumps(payload, ensure_ascii=False, default=str),
        )
    except Exception as e:
        logger.warning(f"Failed to store dashboard cache [{key}]: {e}")


def _query(sql: str) -> dict:
    """Execute a SQL query and return structured columns + rows."""
    with BizSessionLocal() as session:
        result = session.execute(sa_text(sql))
        columns = list(result.keys())
        rows = []
        for row in result.fetchall():
            rows.append([
                float(v) if hasattr(v, "__float__") else
                v.isoformat() if hasattr(v, "isoformat") else
                v
                for v in row
            ])
    return {"columns": columns, "rows": rows, "count": len(rows)}


# ── Pre-computation Tasks ──

def compute_top_products():
    """Task: Top 10 selling products."""
    try:
        data = _query("""
            SELECT p.name AS 商品名称, c.name AS 类目,
                   SUM(oi.quantity) AS 总销量,
                   ROUND(SUM(oi.subtotal), 2) AS 总销售额
            FROM products p
            JOIN categories c ON p.category_id = c.id
            JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status != 'cancelled'
            GROUP BY p.id, p.name, c.name
            ORDER BY 总销量 DESC
            LIMIT 10
        """)
        _store_result("top_products", data)
        logger.info(f"Pre-computed top_products: {data['count']} rows")
    except Exception as e:
        logger.error(f"compute_top_products failed: {e}")


def compute_category_sales():
    """Task: Sales breakdown by category."""
    try:
        data = _query("""
            SELECT c.name AS 类目名称,
                   COUNT(DISTINCT p.id) AS 商品数,
                   SUM(oi.quantity) AS 总销量,
                   ROUND(SUM(oi.subtotal), 2) AS 销售总额
            FROM categories c
            JOIN products p ON c.id = p.category_id
            JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status != 'cancelled'
            GROUP BY c.id, c.name
            ORDER BY 销售总额 DESC
        """)
        _store_result("category_sales", data)
        logger.info(f"Pre-computed category_sales: {data['count']} rows")
    except Exception as e:
        logger.error(f"compute_category_sales failed: {e}")


def compute_daily_trend():
    """Task: Daily order trend for the last 30 days."""
    try:
        data = _query("""
            SELECT DATE(created_at) AS 日期,
                   COUNT(*) AS 订单数,
                   ROUND(SUM(total_amount), 2) AS 日销售额,
                   ROUND(AVG(total_amount), 2) AS 客单价
            FROM orders
            WHERE status != 'cancelled'
              AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(created_at)
            ORDER BY 日期
        """)
        _store_result("daily_trend", data)
        logger.info(f"Pre-computed daily_trend: {data['count']} rows")
    except Exception as e:
        logger.error(f"compute_daily_trend failed: {e}")


def compute_payment_distribution():
    """Task: Payment method distribution."""
    try:
        data = _query("""
            SELECT payment_method AS 支付方式,
                   COUNT(*) AS 订单数量,
                   ROUND(SUM(total_amount), 2) AS 总金额,
                   ROUND(COUNT(*) * 100.0 / (
                       SELECT COUNT(*) FROM orders WHERE status != 'cancelled'
                   ), 1) AS 占比百分比
            FROM orders
            WHERE status != 'cancelled'
            GROUP BY payment_method
            ORDER BY 订单数量 DESC
        """)
        _store_result("payment_dist", data)
        logger.info(f"Pre-computed payment_dist: {data['count']} rows")
    except Exception as e:
        logger.error(f"compute_payment_distribution failed: {e}")


def compute_city_ranking():
    """Task: Top 15 cities by customer count."""
    try:
        data = _query("""
            SELECT city AS 城市, province AS 省份,
                   COUNT(*) AS 客户数量
            FROM customers
            GROUP BY city, province
            ORDER BY 客户数量 DESC
            LIMIT 15
        """)
        _store_result("city_ranking", data)
        logger.info(f"Pre-computed city_ranking: {data['count']} rows")
    except Exception as e:
        logger.error(f"compute_city_ranking failed: {e}")


def compute_member_analysis():
    """Task: Member level spending analysis."""
    try:
        data = _query("""
            SELECT c.member_level AS 会员等级,
                   COUNT(DISTINCT c.id) AS 客户数,
                   COUNT(o.id) AS 订单数,
                   ROUND(AVG(o.total_amount), 2) AS 平均订单金额,
                   ROUND(SUM(o.total_amount), 2) AS 总消费
            FROM customers c
            LEFT JOIN orders o ON c.id = o.customer_id AND o.status != 'cancelled'
            GROUP BY c.member_level
            ORDER BY 平均订单金额 DESC
        """)
        _store_result("member_analysis", data)
        logger.info(f"Pre-computed member_analysis: {data['count']} rows")
    except Exception as e:
        logger.error(f"compute_member_analysis failed: {e}")


def compute_overview_stats():
    """Task: High-level overview statistics."""
    try:
        data = _query("""
            SELECT
                (SELECT COUNT(*) FROM orders WHERE status != 'cancelled') AS 总订单数,
                (SELECT COUNT(*) FROM customers) AS 总客户数,
                (SELECT COUNT(*) FROM products WHERE status = 'active') AS 在售商品数,
                (SELECT ROUND(SUM(total_amount), 2) FROM orders WHERE status != 'cancelled') AS 总销售额,
                (SELECT ROUND(AVG(total_amount), 2) FROM orders WHERE status != 'cancelled') AS 平均客单价,
                (SELECT COUNT(*) FROM orders
                 WHERE status != 'cancelled'
                 AND created_at >= DATE_SUB(CURDATE(), INTERVAL 1 DAY)) AS 今日订单数
        """)
        _store_result("overview", data)
        logger.info(f"Pre-computed overview stats")
    except Exception as e:
        logger.error(f"compute_overview_stats failed: {e}")


# ── All tasks registry ──
ALL_TASKS = [
    {
        "id": "top_products",
        "name": "热销商品 TOP10",
        "func": compute_top_products,
        "interval_minutes": 10,
    },
    {
        "id": "category_sales",
        "name": "类目销售分布",
        "func": compute_category_sales,
        "interval_minutes": 10,
    },
    {
        "id": "daily_trend",
        "name": "日订单趋势",
        "func": compute_daily_trend,
        "interval_minutes": 30,
    },
    {
        "id": "payment_dist",
        "name": "支付方式分布",
        "func": compute_payment_distribution,
        "interval_minutes": 30,
    },
    {
        "id": "city_ranking",
        "name": "城市客户排名",
        "func": compute_city_ranking,
        "interval_minutes": 60,
    },
    {
        "id": "member_analysis",
        "name": "会员消费分析",
        "func": compute_member_analysis,
        "interval_minutes": 60,
    },
    {
        "id": "overview",
        "name": "总览统计",
        "func": compute_overview_stats,
        "interval_minutes": 10,
    },
]


def run_all_tasks():
    """Execute all pre-computation tasks immediately (for initial load)."""
    logger.info("Running all pre-computation tasks...")
    for task in ALL_TASKS:
        try:
            task["func"]()
        except Exception as e:
            logger.error(f"Task '{task['id']}' failed: {e}")
    logger.info("All pre-computation tasks completed")


def get_dashboard_data(key: str) -> dict | None:
    """Retrieve pre-computed dashboard data from Redis."""
    if not _redis:
        return None
    try:
        raw = _redis.get(f"{DASHBOARD_CACHE_PREFIX}{key}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"Failed to read dashboard cache [{key}]: {e}")
    return None


def get_all_dashboard_data() -> dict:
    """Retrieve all pre-computed dashboard data."""
    result = {}
    for task in ALL_TASKS:
        data = get_dashboard_data(task["id"])
        result[task["id"]] = data
    return result
